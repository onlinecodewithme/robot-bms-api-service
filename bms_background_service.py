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
    
    def __init__(self, data_file_path: str = "/tmp/bms_latest.json", read_interval: float = 5.0):
        self.data_file_path = Path(data_file_path)
        self.read_interval = read_interval
        self.reader = DalyBMSReader(scan_timeout=10.0, read_interval=read_interval)
        self.running = False
        self.last_successful_read = 0
        self.connection_retry_count = 0
        self.max_retry_attempts = 10
        
        # Ensure data directory exists
        self.data_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
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
        """Atomically write BMS data to file"""
        try:
            # Write to temporary file first for atomic operation
            temp_file = self.data_file_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, separators=(',', ':'))
            
            # Atomic move to final location
            temp_file.replace(self.data_file_path)
            
            self.last_successful_read = time.time()
            self.connection_retry_count = 0
            
            # Safely access parsed data for logging
            try:
                parsed_data = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
                pack_voltage = parsed_data.get('packVoltage', 0)
                soc = parsed_data.get('soc', 0)
                logger.debug(f"Updated BMS data: {pack_voltage:.3f}V, {soc:.1f}%")
            except Exception as e:
                logger.debug(f"Updated BMS data (logging error: {e})")
            
        except Exception as e:
            logger.error(f"Failed to write BMS data: {e}")
    
    def write_error_status(self, error: str):
        """Write error status when BMS reading fails"""
        error_data = {
            "timestamp": int(time.time() * 1000),
            "device": "DL-41181201189F",
            "mac_address": "41:18:12:01:18:9f",
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
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Start service
    service = BMSBackgroundService(args.data_file, args.interval)
    
    try:
        await service.run_service()
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())