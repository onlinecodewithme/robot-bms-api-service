#!/usr/bin/env python3
"""
BMS Background Data Collection Service
Continuously reads BMS data and writes latest record to file for API consumption
"""

import asyncio
import json
import logging
import time
import os
import tempfile
import signal
import sys
from pathlib import Path
from daly_bms_reader import DalyBMSReader
from daly_uart_reader import DalyUARTReader, DEFAULT_PORT as DEFAULT_UART_PORT, DEFAULT_BAUD as DEFAULT_UART_BAUD

# Configure logging
log_handlers = [logging.StreamHandler(sys.stdout)]

# Try to use log directory created by install script
if os.path.exists('/var/log/bms') and os.access('/var/log/bms', os.W_OK):
    log_handlers.append(logging.FileHandler('/var/log/bms/background.log'))
elif os.path.exists('/tmp'):
    # Fallback to /tmp if /var/log/bms not available
    log_handlers.append(logging.FileHandler('/tmp/bms_background.log'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('bms_background')

class BMSBackgroundService:
    """Background service for collecting BMS data"""
    
    def __init__(self, data_file_path: str = "./bms_data/bms_latest.json", read_interval: float = 5.0,
                 simulation: bool = False, transport: str = "ble",
                 uart_port: str = DEFAULT_UART_PORT, uart_baud: int = DEFAULT_UART_BAUD):
        self.data_file_path = Path(data_file_path)
        self.read_interval = read_interval
        self.simulation = simulation or os.getenv('BMS_SIMULATION', 'false').lower() == 'true'
        self.transport = transport
        if transport == "uart":
            # Daly 13-byte UART protocol over a USB serial adapter (no BLE needed)
            self.reader = DalyUARTReader(port=uart_port, baudrate=uart_baud, read_interval=read_interval)
        else:
            self.reader = DalyBMSReader(scan_timeout=10.0, read_interval=read_interval)
        self.running = False
        self.last_successful_read = 0
        self.connection_retry_count = 0
        self.max_retry_attempts = 10
        
        # Simulation parameters
        self._sim_soc = 87.0
        self._sim_charging = True
        
        # Ensure data directory exists
        self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def generate_mock_bms_data(self) -> dict:
        """Generate perfect mock BMS data matching the Daly BMS BLE protocol structure"""
        # Simulate charging/discharging SOC behavior
        if self._sim_charging:
            self._sim_soc += 0.05
            if self._sim_soc >= 98.0:
                self._sim_charging = False
        else:
            self._sim_soc -= 0.02
            if self._sim_soc <= 25.0:
                self._sim_charging = True
                
        # Generate cell voltages (16 cells, average ~3.3V)
        base_cell = 3.25 + (self._sim_soc / 100.0) * 0.15  # 3.25V to 3.4V
        cell_voltages = []
        for i in range(16):
            # Add small random variance to cell voltages
            variance = ((i * 7 + 13) % 11 - 5) * 0.002
            cell_voltages.append({
                "cellNumber": i + 1,
                "voltage": round(base_cell + variance, 3)
            })
            
        pack_voltage = round(sum(c['voltage'] for c in cell_voltages), 3)
        current = round(4.5 + (time.time() % 10) * 0.2, 2) if self._sim_charging else -1.5
        remaining_capacity = round(230.0 * (self._sim_soc / 100.0), 1)
        
        timestamp_ms = int(time.time() * 1000)
        
        mock_data = {
            "timestamp": timestamp_ms,
            "device": "DL-41181201189F",
            "mac_address": "41:18:12:01:18:9f",
            "daly_protocol": {
                "status": "characteristics_found",
                "notifications": "enabled",
                "commands": {
                    "main_info": {
                        "command_sent": "A540900800000000000000003D",
                        "response_received": True,
                        "response_data": "a5409008" + "00" * 8 + "3d",
                        "parsed_data": {
                            "header": {
                                "startByte": "0xA5",
                                "commandId": "0x90",
                                "dataLength": 8
                            },
                            "cellVoltages": cell_voltages,
                            "packVoltage": pack_voltage,
                            "current": current,
                            "soc": round(self._sim_soc, 1),
                            "remainingCapacity": remaining_capacity,
                            "totalCapacity": 230.0,
                            "cycles": 5,
                            "temperatures": [
                                {"sensor": "T1", "temperature": round(28.5 + (current * 0.2 if current > 0 else 0), 1)},
                                {"sensor": "T2", "temperature": round(29.0 + (current * 0.2 if current > 0 else 0), 1)}
                            ],
                            "mosStatus": {
                                "chargingMos": self._sim_charging,
                                "dischargingMos": True,
                                "balancing": False
                            },
                            "checksum": "0x0000",
                            "timestamp": str(timestamp_ms)
                        }
                    }
                }
            },
            "data_found": True
        }
        return mock_data
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def write_status_file(self, status: dict):
        """Write status information to separate file"""
        status_file = self.data_file_path.parent / "bms_status.json"
        try:
            with open(status_file, 'w') as f:
                json.dump(status, f, separators=(',', ':'))
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")
    
    def write_bms_data(self, data: dict):
        """Atomically write BMS data to file with robust error handling"""
        try:
            # Ensure directory exists and is writable
            self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if we can write to the directory
            if not os.access(self.data_file_path.parent, os.W_OK):
                logger.error(f"No write permission to directory: {self.data_file_path.parent}")
                return
            
            # Create JSON content
            json_content = json.dumps(data, separators=(',', ':'))
            
            # Write to temporary file first for atomic operation
            temp_file = self.data_file_path.with_suffix('.tmp')
            
            # Explicit file writing with error handling
            logger.debug(f"Attempting to write BMS data to: {temp_file}")
            with open(temp_file, 'w') as f:
                f.write(json_content)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force write to disk
            
            logger.debug(f"Temporary file written successfully: {temp_file}")
            
            # Atomic move to final location
            temp_file.replace(self.data_file_path)
            logger.debug(f"File moved to final location: {self.data_file_path}")
            
            # Verify file was created and has content
            if self.data_file_path.exists():
                file_size = self.data_file_path.stat().st_size
                logger.debug(f"File verification: {self.data_file_path} exists, size: {file_size} bytes")
            else:
                logger.error(f"File verification failed: {self.data_file_path} does not exist after write")
            
            self.last_successful_read = time.time()
            self.connection_retry_count = 0
            
            # Safely access parsed data for logging
            try:
                parsed_data = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
                pack_voltage = parsed_data.get('packVoltage', 0)
                soc = parsed_data.get('soc', 0)
                logger.info(f"Successfully updated BMS data file: {pack_voltage:.3f}V, {soc:.1f}%")
            except Exception as e:
                logger.info(f"Successfully updated BMS data file (logging error: {e})")
            
        except PermissionError as e:
            logger.error(f"Permission denied writing BMS data: {e}")
            logger.error(f"Current user: {os.getenv('USER', 'unknown')}")
            logger.error(f"Data file path: {self.data_file_path}")
            logger.error(f"Directory permissions: {oct(self.data_file_path.parent.stat().st_mode)[-3:]}")
        except Exception as e:
            logger.error(f"Failed to write BMS data: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Working directory: {os.getcwd()}")
            logger.error(f"Data file path: {self.data_file_path}")
            logger.error(f"Directory exists: {self.data_file_path.parent.exists()}")
            logger.error(f"Directory writable: {os.access(self.data_file_path.parent, os.W_OK)}")
    
    def write_error_status(self, error: str):
        """Write error status when BMS reading fails"""
        error_data = {
            "timestamp": int(time.time() * 1000),
            "device": getattr(self.reader, 'DEVICE_NAME', "DL-41181201189F") if self.transport == 'uart' else "DL-41181201189F",
            "mac_address": self.reader.port if self.transport == 'uart' else "41:18:12:01:18:9f",
            "error": error,
            "data_found": False,
            "service_status": "error",
            "last_successful_read": self.last_successful_read * 1000 if self.last_successful_read else None,
            "retry_count": self.connection_retry_count
        }
        
        try:
            temp_file = self.data_file_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(error_data, f, separators=(',', ':'))
            temp_file.replace(self.data_file_path)
        except Exception as e:
            logger.error(f"Failed to write error status: {e}")
    
    async def run_service(self):
        """Main service loop"""
        logger.info("Starting BMS Background Service...")
        logger.info(f"Data file: {self.data_file_path}")
        logger.info(f"Read interval: {self.read_interval}s")
        logger.info(f"Transport: {self.transport}" + (f" ({self.reader.port} @ {self.reader.baudrate} baud)" if self.transport == 'uart' else ''))
        
        self.running = True
        
        # Initial status
        self.write_status_file({
            "service": "bms_background",
            "status": "starting",
            "start_time": time.time(),
            "data_file": str(self.data_file_path),
            "read_interval": self.read_interval
        })
        
        while self.running:
            try:
                if self.simulation:
                    data = self.generate_mock_bms_data()
                    self.write_bms_data(data)
                    self.write_status_file({
                        "service": "bms_background",
                        "status": "reading",
                        "last_read": time.time(),
                        "pack_voltage": data['daly_protocol']['commands']['main_info']['parsed_data']['packVoltage'],
                        "soc": data['daly_protocol']['commands']['main_info']['parsed_data']['soc'],
                        "current": data['daly_protocol']['commands']['main_info']['parsed_data']['current'],
                        "mode": "simulation"
                    })
                    await asyncio.sleep(self.read_interval)
                    continue

                # Check connection status
                if not self.reader.connected:
                    if self.connection_retry_count >= self.max_retry_attempts:
                        logger.warning(f"Max retry attempts ({self.max_retry_attempts}) reached, waiting longer...")
                        await asyncio.sleep(30)  # Wait 30 seconds before trying again
                        self.connection_retry_count = 0
                    
                    # Try to find and connect to BMS
                    logger.info("Scanning for BMS device...")
                    device = await self.reader.scan_for_bms()
                    if device:
                        logger.info(f"Found BMS: {device.name} [{device.address}]")
                        connected = await self.reader.connect_to_bms()
                        if connected:
                            logger.info("Successfully connected to BMS")
                            
                            # Update status
                            self.write_status_file({
                                "service": "bms_background", 
                                "status": "connected",
                                "device": device.name,
                                "mac_address": device.address,
                                "connected_at": time.time()
                            })
                        else:
                            self.connection_retry_count += 1
                            logger.warning(f"Failed to connect to BMS (attempt {self.connection_retry_count})")
                            self.write_error_status("Connection failed")
                    else:
                        self.connection_retry_count += 1
                        logger.warning(f"No BMS device found (attempt {self.connection_retry_count})")
                        self.write_error_status("BMS device not found")
                
                # Read BMS data if connected
                if self.reader.connected:
                    success = await self.reader.read_bms_data()
                    if success:
                        # Create the complete data structure
                        json_output = self.reader.create_json_output()
                        data = json.loads(json_output)
                        
                        # Write to file
                        self.write_bms_data(data)
                        
                        # Update status
                        parsed_data = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
                        self.write_status_file({
                            "service": "bms_background",
                            "status": "reading", 
                            "last_read": time.time(),
                            "pack_voltage": parsed_data.get('packVoltage', 0),
                            "soc": parsed_data.get('soc', 0),
                            "current": parsed_data.get('current', 0)
                        })
                    else:
                        logger.warning("Failed to read BMS data")
                        self.write_error_status("Failed to read BMS data")
                        # Check if still connected
                        if not self.reader.client or not self.reader.client.is_connected:
                            logger.warning("Lost connection to BMS")
                            self.reader.connected = False
                
                # Wait for next reading
                await asyncio.sleep(self.read_interval)
                
            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                self.write_error_status(f"Service error: {str(e)}")
                await asyncio.sleep(self.read_interval)
        
        # Cleanup on shutdown
        logger.info("Service shutting down...")
        if self.reader.connected:
            await self.reader.disconnect()
        
        # Write final status
        self.write_status_file({
            "service": "bms_background",
            "status": "stopped",
            "stopped_at": time.time()
        })
        
        logger.info("BMS Background Service stopped")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='BMS Background Data Collection Service')
    parser.add_argument('--data-file', default='/tmp/bms_latest.json', help='Output data file path')
    parser.add_argument('--interval', type=float, default=5.0, help='Read interval in seconds')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO', help='Log level')
    parser.add_argument('--simulation', action='store_true', help='Enable simulation mode')
    parser.add_argument('--transport', choices=['ble', 'uart'], default=os.getenv('BMS_TRANSPORT', 'ble'),
                        help='How to talk to the BMS: ble (built-in Bluetooth) or uart (USB serial adapter)')
    parser.add_argument('--port', default=os.getenv('BMS_UART_PORT', DEFAULT_UART_PORT),
                        help='Serial port for --transport uart')
    parser.add_argument('--baud', type=int, default=int(os.getenv('BMS_UART_BAUD', DEFAULT_UART_BAUD)),
                        help='Baud rate for --transport uart')
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Start service
    service = BMSBackgroundService(args.data_file, args.interval, args.simulation,
                                   transport=args.transport, uart_port=args.port, uart_baud=args.baud)
    
    try:
        await service.run_service()
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())