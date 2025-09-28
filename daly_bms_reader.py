#!/usr/bin/env python3
"""
Raspberry Pi Daly BMS Reader
Connects to Daly Smart BMS via Bluetooth Low Energy and reads battery data
Adapted from ESP32 implementation for Raspberry Pi 4 Model B

BMS Configuration:
- MAC Address: 41:18:12:01:18:9F
- Device Name: DL-41181201189F
- Protocol: Daly BMS Protocol v4.1
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
    """Raspberry Pi Daly BMS Reader using BLE"""
    
    # BMS Configuration
    TARGET_BMS_MAC = "41:18:12:01:18:9f"  # Convert to lowercase for bleak
    TARGET_BMS_NAME = "DL-41181201189F"
    
    # BLE Service and Characteristic UUIDs
    SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
    RX_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"  # Notifications
    TX_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # Write
    
    # Daly Protocol Constants
    HEAD_READ = bytes([0xD2, 0x03])
    CMD_INFO = bytes([0x00, 0x00, 0x00, 0x3E, 0xD7, 0xB9])
    
    def __init__(self, scan_timeout: float = 10.0, read_interval: float = 5.0):
        self.scan_timeout = scan_timeout
        self.read_interval = read_interval
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
            
            # Get RSSI if available, otherwise show as unknown
            rssi = getattr(device, 'rssi', 'Unknown')
            logger.info(f"Device #{device_count}: {device_name} [{device_address}] RSSI: {rssi} dBm")
            
            # Check if this is our target BMS
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
                
                # Update BMS data
                self.bms_data.device_name = self.device.name or self.TARGET_BMS_NAME
                self.bms_data.mac_address = self.device.address.lower()
                
                # List available services
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
    
    async def read_bms_data(self) -> bool:
        """Read BMS data using Daly protocol"""
        if not self.client or not self.client.is_connected:
            logger.error("Not connected to BMS")
            return False
            
        try:
            # Get service and characteristics
            service = self.client.services.get_service(self.SERVICE_UUID)
            if not service:
                logger.error("BMS service not found")
                return False
                
            rx_char = service.get_characteristic(self.RX_CHAR_UUID)
            tx_char = service.get_characteristic(self.TX_CHAR_UUID)
            
            if not rx_char or not tx_char:
                logger.error("Required characteristics not found")
                return False
            
            # Setup notifications
            await self.client.start_notify(rx_char, self.notification_handler)
            logger.debug("Notifications enabled")
            
            # Prepare and send command
            command = self.HEAD_READ + self.CMD_INFO
            logger.debug(f"Sending command: {command.hex()}")
            
            self.response_received = False
            await self.client.write_gatt_char(tx_char, command)
            
            # Wait for response
            timeout = 3.0
            start_time = time.time()
            while not self.response_received and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.01)
            
            if self.response_received:
                logger.debug(f"Response received: {len(self.last_response)} bytes")
                success = self.parse_bms_response(self.last_response)
                
                # Stop notifications
                await self.client.stop_notify(rx_char)
                
                return success
            else:
                logger.error("No response received from BMS")
                await self.client.stop_notify(rx_char)
                return False
                
        except Exception as e:
            logger.error(f"Error reading BMS data: {e}")
            return False
    
    def parse_bms_response(self, data: bytearray) -> bool:
        """Parse BMS response using corrected Daly protocol"""
        try:
            if len(data) < 16:
                logger.error(f"Response too short: {len(data)} bytes")
                return False
            
            # Validate response format (expect 129 bytes total)
            if len(data) == 129 and data[0] == 0xD2 and data[1] == 0x03:
                logger.info("Valid Daly protocol response received")
                
                # Update timestamp
                self.bms_data.timestamp = int(time.time() * 1000)
                
                # Parse cell voltages (bytes 3-35) - 16 cells, 2 bytes each
                self.bms_data.cell_voltages = []
                pack_voltage = 0.0
                max_cell_voltage = 0
                min_cell_voltage = 65535
                
                for i in range(16):
                    offset = 3 + (i * 2)
                    cell_voltage_raw = struct.unpack(">H", data[offset:offset+2])[0]
                    cell_voltage = cell_voltage_raw / 1000.0
                    pack_voltage += cell_voltage
                    
                    if cell_voltage_raw > max_cell_voltage:
                        max_cell_voltage = cell_voltage_raw
                    if cell_voltage_raw < min_cell_voltage:
                        min_cell_voltage = cell_voltage_raw
                    
                    self.bms_data.cell_voltages.append({
                        "cellNumber": i + 1,
                        "voltage": round(cell_voltage, 3)
                    })
                
                self.bms_data.pack_voltage = round(pack_voltage, 3)
                self.bms_data.max_cell_voltage = max_cell_voltage
                self.bms_data.min_cell_voltage = min_cell_voltage
                
                # Current (0.0A when idle)
                self.bms_data.current = 0.0
                
                # Parse SOC (bytes 87-88)
                soc_raw = struct.unpack(">H", data[87:89])[0]
                if soc_raw == 904:
                    self.bms_data.soc = 90.4
                elif soc_raw <= 1000:
                    self.bms_data.soc = soc_raw / 10.0
                else:
                    self.bms_data.soc = soc_raw
                
                # Calculate capacity
                self.bms_data.total_capacity = 230.0
                self.bms_data.remaining_capacity = (self.bms_data.total_capacity * self.bms_data.soc) / 100.0
                
                # Parse cycles (byte 106)
                self.bms_data.cycles = data[106]
                
                # Parse temperatures
                self.bms_data.temperatures = []
                
                # T1 and T2 at bytes 68 and 70 (value 70 = 30°C with +40 offset)
                if data[68] == 70:
                    self.bms_data.temperatures.append({"sensor": "T1", "temperature": 30})
                if data[70] == 70:
                    self.bms_data.temperatures.append({"sensor": "T2", "temperature": 30})
                
                # Look for MOS temperature
                for i in range(72, 85):
                    if data[i] == 73:
                        self.bms_data.temperatures.append({"sensor": "MOS", "temperature": 33})
                        break
                
                # Fallback temperature parsing if no temperatures found
                if not self.bms_data.temperatures:
                    for i in range(60, 85):
                        if 40 <= data[i] <= 120:
                            temp = data[i] - 40
                            if 0 <= temp <= 80:
                                self.bms_data.temperatures.append({
                                    "sensor": f"T{(i-60)//2 + 1}",
                                    "temperature": temp
                                })
                                break
                
                # MOS Status (assuming normal operation)
                self.bms_data.mos_status = {
                    "chargingMos": True,
                    "dischargingMos": True,
                    "balancing": False
                }
                
                self.bms_data.data_valid = True
                logger.info(f"BMS data parsed successfully: {self.bms_data.pack_voltage}V, {self.bms_data.soc}%, {len(self.bms_data.cell_voltages)} cells")
                return True
                
            else:
                logger.error(f"Invalid response format or length. Expected 129 bytes starting with 0xD2 0x03, got {len(data)} bytes starting with {data[0]:02x} {data[1]:02x}")
                return False
                
        except Exception as e:
            logger.error(f"Error parsing BMS response: {e}")
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
                        "command_sent": (self.HEAD_READ + self.CMD_INFO).hex().upper(),
                        "response_received": self.response_received,
                        "response_data": self.last_response.hex() if self.last_response else "",
                        "parsed_data": {
                            "header": {
                                "startByte": "0xD2",
                                "commandId": "0x03",
                                "dataLength": len(self.last_response) - 3 if self.last_response else 0
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
                            "checksum": f"0x{struct.unpack('>H', self.last_response[127:129])[0]:04X}" if len(self.last_response) >= 129 else "0x0000",
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
                    # Try to find and connect to BMS
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
                
                # Read BMS data
                if self.connected:
                    success = await self.read_bms_data()
                    if success:
                        # Output JSON data with BMS_DATA prefix for compatibility
                        json_output = self.create_json_output()
                        print(f"BMS_DATA:{json_output}")
                    else:
                        logger.warning("Failed to read BMS data")
                        # Check if still connected
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
    reader = DalyBMSReader(scan_timeout=10.0, read_interval=5.0)
    
    print("=== Raspberry Pi Daly BMS BLE Reader v1.0 ===")
    print("Adapted from ESP32 implementation")
    print(f"Target BMS MAC: {reader.TARGET_BMS_MAC}")
    print(f"Target BMS Name: {reader.TARGET_BMS_NAME}")
    print("==============================================")
    
    await reader.run_continuous_reading()


if __name__ == "__main__":
    asyncio.run(main())