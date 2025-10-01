#!/usr/bin/env python3
"""
Raspberry Pi Daly BMS Reader
Connects to Daly Smart BMS via Bluetooth Low Energy and reads battery data
Adapted from ESP32 implementation for Raspberry Pi 4 Model B

BMS Configuration:
- MAC Address: 41:18:12:01:18:9F
- Device Name: DL-41181201189F
- Protocol: Daly BMS Protocol v4.1 (using standard 0x90 commands)
"""

import asyncio
import json
import logging
import time
import struct
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BMSData:
    """BMS data structure matching ESP32 implementation"""
    timestamp: int
    device_name: str
    mac_address: str
    pack_voltage: float = 0.0
    current: float = 0.0
    soc: float = 0.0
    remaining_capacity: float = 0.0
    total_capacity: float = 0.0
    cycles: int = 0
    cell_voltages: List[Dict[str, float]] = None
    temperatures: List[Dict[str, int]] = None
    mos_status: Dict[str, bool] = None
    max_cell_voltage: int = 0
    min_cell_voltage: int = 0
    data_valid: bool = False
    
    def __post_init__(self):
        if self.cell_voltages is None:
            self.cell_voltages = []
        if self.temperatures is None:
            self.temperatures = []
        if self.mos_status is None:
            self.mos_status = {
                "chargingMos": True,
                "dischargingMos": True,
                "balancing": False
            }


class DalyBMSReader:
    """Raspberry Pi Daly BMS Reader using BLE with standard 0x90 commands"""
    
    # BMS Configuration
    TARGET_BMS_MAC = "41:18:12:01:18:9f"  # Convert to lowercase for bleak
    TARGET_BMS_NAME = "DL-41181201189F"
    
    # BLE Service and Characteristic UUIDs
    SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
    RX_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"  # Notifications
    TX_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # Write
    
    # Daly Protocol Constants - Using standard UART commands
    COMMANDS = {
        'PACK_MEASUREMENTS': 0x90,  # Voltage, Current, SOC (REAL-TIME)
        'CELL_MINMAX': 0x91,        # Min/Max cell voltages
        'TEMP_MINMAX': 0x92,        # Min/Max temperatures
        'MOSFET_STATUS': 0x93,      # Charge/Discharge MOS status
        'STATUS_INFO': 0x94,        # Status information
        'CELL_VOLTAGES': 0x95,      # Individual cell voltages
        'TEMPERATURES': 0x96,       # Temperature sensors
        'FAILURE_CODES': 0x98       # Alarms/failures
    }
    
    def __init__(self, scan_timeout: float = 10.0, read_interval: float = 5.0, invert_current: bool = False):
        self.scan_timeout = scan_timeout
        self.read_interval = read_interval
        self.invert_current = invert_current
        self.client: Optional[BleakClient] = None
        self.device: Optional[BLEDevice] = None
        self.connected = False
        self.last_response = bytearray()
        self.response_received = False
        self.bms_data = BMSData(
            timestamp=int(time.time() * 1000),
            device_name="",
            mac_address=""
        )
    
    def calculate_checksum(self, data: bytes) -> int:
        """Calculate Daly protocol checksum"""
        return sum(data) & 0xFF
    
    def build_command(self, cmd_id: int) -> bytes:
        """Build Daly UART command packet"""
        packet = bytes([
            0xA5,  # Start byte
            0x40,  # Host address
            cmd_id,  # Command ID
            0x08,  # Data length
            0x00, 0x00, 0x00, 0x00,  # Reserved
            0x00, 0x00, 0x00, 0x00   # Reserved
        ])
        checksum = self.calculate_checksum(packet)
        return packet + bytes([checksum])
        
    async def scan_for_bms(self) -> Optional[BLEDevice]:
        """Scan for BMS device"""
        logger.info("Scanning for BLE devices...")
        logger.info(f"Target BMS MAC: {self.TARGET_BMS_MAC}")
        logger.info(f"Target BMS Name: {self.TARGET_BMS_NAME}")
        
        devices = await BleakScanner.discover(timeout=self.scan_timeout)
        logger.info(f"Found {len(devices)} BLE devices")
        
        target_device = None
        device_count = 0
        
        for device in devices:
            device_count += 1
            device_name = device.name or "Unknown"
            device_address = device.address.lower()
            
            rssi = getattr(device, 'rssi', 'Unknown')
            logger.info(f"Device #{device_count}: {device_name} [{device_address}] RSSI: {rssi} dBm")
            
            if (device_address == self.TARGET_BMS_MAC or 
                device_name == self.TARGET_BMS_NAME or
                "daly" in device_name.lower() or
                "bms" in device_name.lower() or
                "dl-" in device_name.lower()):
                
                logger.info(f"*** Potential BMS device found! ***")
                logger.info(f"Name: {device_name}")
                logger.info(f"MAC: {device_address}")
                
                if (device_address == self.TARGET_BMS_MAC or 
                    device_name == self.TARGET_BMS_NAME):
                    logger.info("*** Target BMS found! ***")
                    target_device = device
                    break
                elif target_device is None:
                    logger.info("*** Stored as potential BMS ***")
                    target_device = device
        
        if target_device:
            self.device = target_device
            logger.info(f"Selected BMS device: {target_device.name} [{target_device.address}]")
        else:
            logger.warning("No BMS device found")
            
        return target_device
    
    async def connect_to_bms(self) -> bool:
        """Connect to BMS device"""
        if not self.device:
            logger.error("No BMS device to connect to")
            return False
            
        try:
            logger.info(f"Connecting to BMS: {self.device.name} [{self.device.address}]")
            
            self.client = BleakClient(self.device)
            await self.client.connect()
            
            if self.client.is_connected:
                logger.info("*** Successfully connected to BMS via BLE! ***")
                logger.info(f"Connected to: {self.device.name} [{self.device.address}]")
                
                self.bms_data.device_name = self.device.name or self.TARGET_BMS_NAME
                self.bms_data.mac_address = self.device.address.lower()
                
                await self.list_services()
                
                self.connected = True
                return True
            else:
                logger.error("Failed to establish BLE connection")
                return False
                
        except Exception as e:
            logger.error(f"BLE connection failed: {e}")
            return False
    
    async def list_services(self):
        """List available BLE services and characteristics"""
        if not self.client or not self.client.is_connected:
            return
            
        try:
            logger.info("Discovering services...")
            services = self.client.services
            
            for service in services:
                logger.info(f"Service UUID: {service.uuid}")
                
                for char in service.characteristics:
                    properties = []
                    if "read" in char.properties:
                        properties.append("R")
                    if "write" in char.properties or "write-without-response" in char.properties:
                        properties.append("W")
                    if "notify" in char.properties:
                        properties.append("N")
                    
                    logger.info(f"  Characteristic UUID: {char.uuid} Properties: {''.join(properties)}")
                    
        except Exception as e:
            logger.error(f"Error listing services: {e}")
    
    def notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle BLE notifications"""
        logger.debug(f"Notification received from {sender.uuid}: {data.hex()}")
        self.last_response = data
        self.response_received = True
    
    async def send_command(self, cmd_id: int, timeout: float = 2.0) -> Optional[bytearray]:
        """Send command and wait for response"""
        if not self.client or not self.client.is_connected:
            return None
        
        try:
            service = self.client.services.get_service(self.SERVICE_UUID)
            rx_char = service.get_characteristic(self.RX_CHAR_UUID)
            tx_char = service.get_characteristic(self.TX_CHAR_UUID)
            
            if not rx_char or not tx_char:
                return None
            
            response_data = bytearray()
            response_event = asyncio.Event()
            
            def handler(sender: BleakGATTCharacteristic, data: bytearray):
                nonlocal response_data
                response_data = data
                response_event.set()
            
            await self.client.start_notify(rx_char, handler)
            
            command = self.build_command(cmd_id)
            logger.debug(f"Sending command 0x{cmd_id:02X}: {command.hex()}")
            await self.client.write_gatt_char(tx_char, command)
            
            try:
                await asyncio.wait_for(response_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for command 0x{cmd_id:02X}")
                response_data = None
            
            await self.client.stop_notify(rx_char)
            return response_data
            
        except Exception as e:
            logger.error(f"Error sending command 0x{cmd_id:02X}: {e}")
            return None
    
    async def read_bms_data(self) -> bool:
        """Read BMS data using Daly protocol"""
        if not self.client or not self.client.is_connected:
            logger.error("Not connected to BMS")
            return False
        
        self.bms_data.timestamp = int(time.time() * 1000)
        self.bms_data.total_capacity = 230.0
        success = False
        
        try:
            # Command 0x90 - Pack measurements (REAL-TIME CURRENT)
            response_90 = await self.send_command(self.COMMANDS['PACK_MEASUREMENTS'])
            if response_90 and len(response_90) >= 13:
                if response_90[0] == 0xA5 and response_90[2] == 0x90:
                    # Pack voltage (bytes 4-5, 0.1V units)
                    pack_voltage_raw = struct.unpack(">H", response_90[4:6])[0]
                    self.bms_data.pack_voltage = round(pack_voltage_raw / 10.0, 3)
                    
                    # Current (bytes 8-9, 0.1A units with 30000 offset)
                    current_raw = struct.unpack(">H", response_90[8:10])[0]
                    current_amps = (current_raw - 30000) / 10.0
                    
                    # Invert if needed (negative = charging, positive = discharging)
                    if self.invert_current:
                        current_amps = -current_amps
                    
                    self.bms_data.current = round(current_amps, 2)
                    
                    # SOC (bytes 10-11, 0.1% units)
                    soc_raw = struct.unpack(">H", response_90[10:12])[0]
                    self.bms_data.soc = round(soc_raw / 10.0, 1)
                    
                    self.bms_data.remaining_capacity = round((self.bms_data.total_capacity * self.bms_data.soc) / 100.0, 1)
                    
                    logger.info(f"Pack: {self.bms_data.pack_voltage}V, {self.bms_data.current}A, {self.bms_data.soc}%")
                    success = True
            
            # Command 0x91 - Cell min/max
            response_91 = await self.send_command(self.COMMANDS['CELL_MINMAX'])
            if response_91 and len(response_91) >= 13:
                if response_91[0] == 0xA5 and response_91[2] == 0x91:
                    self.bms_data.max_cell_voltage = struct.unpack(">H", response_91[4:6])[0]
                    self.bms_data.min_cell_voltage = struct.unpack(">H", response_91[7:9])[0]
            
            # Command 0x92 - Temperatures
            response_92 = await self.send_command(self.COMMANDS['TEMP_MINMAX'])
            if response_92 and len(response_92) >= 13:
                if response_92[0] == 0xA5 and response_92[2] == 0x92:
                    self.bms_data.temperatures = []
                    max_temp = response_92[4] - 40
                    min_temp = response_92[6] - 40
                    if max_temp >= 0 and max_temp <= 100:
                        self.bms_data.temperatures.append({"sensor": "T1", "temperature": max_temp})
                    if min_temp >= 0 and min_temp <= 100:
                        self.bms_data.temperatures.append({"sensor": "T2", "temperature": min_temp})
            
            # Command 0x93 - MOSFET status
            response_93 = await self.send_command(self.COMMANDS['MOSFET_STATUS'])
            if response_93 and len(response_93) >= 13:
                if response_93[0] == 0xA5 and response_93[2] == 0x93:
                    mos_byte = response_93[4]
                    self.bms_data.mos_status = {
                        "chargingMos": bool(mos_byte & 0x01),
                        "dischargingMos": bool(mos_byte & 0x02),
                        "balancing": False
                    }
            
            # Command 0x95 - Individual cell voltages (read multiple frames)
            self.bms_data.cell_voltages = []
            for frame in range(6):  # 6 frames for 16 cells (3 per frame)
                response_95 = await self.send_command(self.COMMANDS['CELL_VOLTAGES'])
                if response_95 and len(response_95) >= 13:
                    if response_95[0] == 0xA5 and response_95[2] == 0x95:
                        frame_num = response_95[4]
                        for i in range(3):
                            offset = 5 + (i * 2)
                            cell_voltage_raw = struct.unpack(">H", response_95[offset:offset+2])[0]
                            cell_voltage = cell_voltage_raw / 1000.0
                            cell_num = frame_num * 3 + i + 1
                            if cell_num <= 16:
                                self.bms_data.cell_voltages.append({
                                    "cellNumber": cell_num,
                                    "voltage": round(cell_voltage, 3)
                                })
                await asyncio.sleep(0.05)
            
            # Set cycles to default value
            self.bms_data.cycles = 2
            
            self.bms_data.data_valid = success
            return success
                
        except Exception as e:
            logger.error(f"Error reading BMS data: {e}")
            return False
    
    def create_json_output(self) -> str:
        """Create JSON output matching ESP32 format"""
        output = {
            "timestamp": self.bms_data.timestamp,
            "device": self.bms_data.device_name,
            "mac_address": self.bms_data.mac_address,
            "daly_protocol": {
                "status": "characteristics_found",
                "notifications": "enabled",
                "commands": {
                    "main_info": {
                        "command_sent": "A540900800000000000000003D",
                        "response_received": self.response_received,
                        "response_data": self.last_response.hex() if self.last_response else "",
                        "parsed_data": {
                            "header": {
                                "startByte": "0xA5",
                                "commandId": "0x90",
                                "dataLength": len(self.last_response) - 5 if self.last_response else 0
                            },
                            "cellVoltages": self.bms_data.cell_voltages,
                            "packVoltage": self.bms_data.pack_voltage,
                            "current": self.bms_data.current,
                            "soc": self.bms_data.soc,
                            "remainingCapacity": self.bms_data.remaining_capacity,
                            "totalCapacity": self.bms_data.total_capacity,
                            "cycles": self.bms_data.cycles,
                            "temperatures": self.bms_data.temperatures,
                            "mosStatus": self.bms_data.mos_status,
                            "checksum": f"0x{struct.unpack('>H', self.last_response[-2:])[0]:04X}" if len(self.last_response) >= 2 else "0x0000",
                            "timestamp": str(self.bms_data.timestamp)
                        }
                    }
                }
            },
            "data_found": self.bms_data.data_valid
        }
        
        return json.dumps(output, separators=(',', ':'))
    
    async def disconnect(self):
        """Disconnect from BMS"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            logger.info("Disconnected from BMS")
        self.connected = False
    
    async def run_continuous_reading(self):
        """Run continuous BMS data reading"""
        logger.info("Starting continuous BMS reading...")
        
        try:
            while True:
                if not self.connected:
                    device = await self.scan_for_bms()
                    if device:
                        connected = await self.connect_to_bms()
                        if not connected:
                            logger.warning("Failed to connect, retrying in 10 seconds...")
                            await asyncio.sleep(10)
                            continue
                    else:
                        logger.warning("No BMS found, retrying scan in 30 seconds...")
                        await asyncio.sleep(30)
                        continue
                
                if self.connected:
                    success = await self.read_bms_data()
                    if success:
                        json_output = self.create_json_output()
                        print(f"BMS_DATA:{json_output}")
                    else:
                        logger.warning("Failed to read BMS data")
                        if not self.client.is_connected:
                            self.connected = False
                
                await asyncio.sleep(self.read_interval)
                
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error in continuous reading: {e}")
        finally:
            await self.disconnect()


async def main():
    """Main function"""
    reader = DalyBMSReader(scan_timeout=10.0, read_interval=5.0, invert_current=False)
    
    print("=== Raspberry Pi Daly BMS BLE Reader v2.0 ===")
    print("Protocol: Daly UART 0x90 (Real-time)")
    print(f"Target BMS MAC: {reader.TARGET_BMS_MAC}")
    print(f"Target BMS Name: {reader.TARGET_BMS_NAME}")
    print("==============================================")
    
    await reader.run_continuous_reading()


if __name__ == "__main__":
    asyncio.run(main())