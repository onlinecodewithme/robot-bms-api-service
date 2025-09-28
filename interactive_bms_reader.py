#!/usr/bin/env python3
"""
Interactive Raspberry Pi Daly BMS Reader
Provides an interactive command-line interface for BMS operations
Similar to the ESP32 serial command interface
"""

import asyncio
import sys
import json
from daly_bms_reader import DalyBMSReader
import logging

# Configure logging for interactive mode
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise in interactive mode
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class InteractiveBMSReader:
    def __init__(self):
        self.reader = DalyBMSReader(scan_timeout=10.0, read_interval=5.0)
        self.auto_connect = True
        self.running = False
        
    def print_banner(self):
        """Print application banner"""
        print("=== Raspberry Pi Daly BMS BLE Reader v1.0 ===")
        print("Interactive Command Interface")
        print("Adapted from ESP32 implementation")
        print(f"Target BMS MAC: {self.reader.TARGET_BMS_MAC}")
        print(f"Target BMS Name: {self.reader.TARGET_BMS_NAME}")
        print("==============================================")
        print()
        self.print_available_commands()
    
    def print_available_commands(self):
        """Print available commands"""
        print("=== Available Commands ===")
        print("scan (s)     - Scan for BMS devices")
        print("connect (c)  - Connect to discovered BMS")
        print("data (d)     - Read BMS data once")
        print("status       - Show system status")
        print("auto         - Toggle auto-connect")
        print("reset (r)    - Reset and disconnect")
        print("services     - List BLE services/characteristics")
        print("continuous   - Start continuous reading (Ctrl+C to stop)")
        print("json         - Show last data in JSON format")
        print("help (h)     - Show this help")
        print("exit (q)     - Exit application")
        print("==========================")
        print()
    
    async def handle_scan_command(self):
        """Handle scan command"""
        print("Scanning for BMS devices...")
        device = await self.reader.scan_for_bms()
        if device:
            print(f"BMS device found: {device.name} [{device.address}]")
            if self.auto_connect:
                print("Auto-connect enabled, attempting connection...")
                await self.handle_connect_command()
        else:
            print("No BMS devices found in scan")
    
    async def handle_connect_command(self):
        """Handle connect command"""
        if not self.reader.device:
            print("No BMS device discovered. Run 'scan' first.")
            return
            
        if self.reader.connected:
            print("Already connected to BMS")
            return
            
        print(f"Connecting to: {self.reader.device.name} [{self.reader.device.address}]")
        success = await self.reader.connect_to_bms()
        if success:
            print("✅ Successfully connected to BMS!")
        else:
            print("❌ Failed to connect to BMS")
    
    async def handle_data_command(self):
        """Handle data command"""
        if not self.reader.connected:
            print("Not connected to BMS. Try 'scan' and 'connect' first.")
            return
            
        print("Reading BMS data...")
        success = await self.reader.read_bms_data()
        if success:
            data = self.reader.bms_data
            print("\n=== BMS Data ===")
            print(f"Pack Voltage: {data.pack_voltage:.3f} V")
            print(f"Current: {data.current:.2f} A")
            print(f"Power: {data.pack_voltage * data.current:.2f} W")
            print(f"SOC: {data.soc:.1f}%")
            print(f"Remaining Capacity: {data.remaining_capacity:.1f} Ah")
            print(f"Total Capacity: {data.total_capacity:.0f} Ah")
            print(f"Cycles: {data.cycles}")
            
            if data.cell_voltages:
                print("\n--- Cell Voltages ---")
                for cell in data.cell_voltages[:8]:  # Show first 8 cells
                    print(f"Cell {cell['cellNumber']:2d}: {cell['voltage']:.3f} V")
                if len(data.cell_voltages) > 8:
                    print("...")
                    for cell in data.cell_voltages[-4:]:  # Show last 4 cells
                        print(f"Cell {cell['cellNumber']:2d}: {cell['voltage']:.3f} V")
                        
                print(f"Max Cell: {data.max_cell_voltage} mV")
                print(f"Min Cell: {data.min_cell_voltage} mV")
                print(f"Cell Diff: {data.max_cell_voltage - data.min_cell_voltage} mV")
            
            if data.temperatures:
                print(f"\n--- Temperatures ---")
                for temp in data.temperatures:
                    print(f"{temp['sensor']}: {temp['temperature']}°C")
            
            print(f"\n--- MOS Status ---")
            mos = data.mos_status
            print(f"Charging MOS: {'✅ ON' if mos['chargingMos'] else '❌ OFF'}")
            print(f"Discharging MOS: {'✅ ON' if mos['dischargingMos'] else '❌ OFF'}")
            print(f"Balancing: {'⚖️ ACTIVE' if mos['balancing'] else '⏸️ INACTIVE'}")
            print("================")
        else:
            print("❌ Failed to read BMS data")
    
    def handle_status_command(self):
        """Handle status command"""
        print("\n=== System Status ===")
        print(f"Connected: {'✅ YES' if self.reader.connected else '❌ NO'}")
        print(f"BMS Found: {'✅ YES' if self.reader.device else '❌ NO'}")
        print(f"Auto Connect: {'✅ ON' if self.auto_connect else '❌ OFF'}")
        
        if self.reader.device:
            print(f"BMS Device: {self.reader.device.name} [{self.reader.device.address}]")
        
        if self.reader.bms_data.data_valid:
            data = self.reader.bms_data
            print(f"Last Update: {(data.timestamp / 1000)} seconds ago")
            print(f"Battery Status: {data.soc:.1f}% - {data.pack_voltage:.2f}V")
        else:
            print("No valid BMS data")
        print("====================\n")
    
    def handle_auto_command(self):
        """Handle auto-connect toggle"""
        self.auto_connect = not self.auto_connect
        print(f"Auto-connect: {'✅ ENABLED' if self.auto_connect else '❌ DISABLED'}")
    
    async def handle_reset_command(self):
        """Handle reset command"""
        print("Resetting connection...")
        await self.reader.disconnect()
        self.reader.device = None
        print("✅ Reset completed")
    
    async def handle_services_command(self):
        """Handle services command"""
        if not self.reader.connected:
            print("Not connected to BMS")
            return
            
        print("Listing BLE services and characteristics...")
        await self.reader.list_services()
    
    async def handle_continuous_command(self):
        """Handle continuous reading command"""
        if not self.reader.connected:
            print("Not connected to BMS. Attempting auto-scan and connect...")
            await self.handle_scan_command()
            if not self.reader.connected:
                return
        
        print("Starting continuous reading... (Press Ctrl+C to stop)")
        print("Data will be output in JSON format compatible with ROS2:")
        print()
        
        try:
            self.running = True
            while self.running:
                success = await self.reader.read_bms_data()
                if success:
                    json_output = self.reader.create_json_output()
                    print(f"BMS_DATA:{json_output}")
                else:
                    print("Failed to read BMS data")
                    
                await asyncio.sleep(self.reader.read_interval)
                
        except KeyboardInterrupt:
            print("\n⏹️ Continuous reading stopped")
            self.running = False
        except Exception as e:
            print(f"❌ Error in continuous reading: {e}")
            self.running = False
    
    def handle_json_command(self):
        """Handle JSON output command"""
        if not self.reader.bms_data.data_valid:
            print("No valid BMS data available")
            return
            
        json_output = self.reader.create_json_output()
        print("=== JSON Output ===")
        # Pretty print the JSON
        parsed = json.loads(json_output)
        print(json.dumps(parsed, indent=2))
        print("===================")
    
    async def handle_command(self, command: str):
        """Handle user commands"""
        command = command.strip().lower()
        
        if command in ['help', 'h']:
            self.print_available_commands()
        elif command in ['scan', 's']:
            await self.handle_scan_command()
        elif command in ['connect', 'c']:
            await self.handle_connect_command()
        elif command in ['data', 'd']:
            await self.handle_data_command()
        elif command == 'status':
            self.handle_status_command()
        elif command == 'auto':
            self.handle_auto_command()
        elif command in ['reset', 'r']:
            await self.handle_reset_command()
        elif command == 'services':
            await self.handle_services_command()
        elif command == 'continuous':
            await self.handle_continuous_command()
        elif command == 'json':
            self.handle_json_command()
        elif command in ['exit', 'quit', 'q']:
            return False
        elif command:
            print(f"❌ Unknown command: '{command}'. Type 'help' for available commands.")
        
        return True
    
    async def run(self):
        """Run the interactive interface"""
        self.print_banner()
        
        # Auto-scan on startup
        print("Performing initial scan...")
        await self.handle_scan_command()
        print()
        
        try:
            while True:
                try:
                    command = input("BMS> ").strip()
                    if not await self.handle_command(command):
                        break
                except EOFError:
                    break
                except KeyboardInterrupt:
                    if self.running:
                        self.running = False
                        print("\n⏹️ Stopping current operation...")
                    else:
                        print("\n👋 Goodbye!")
                        break
                        
        finally:
            print("Cleaning up...")
            await self.reader.disconnect()
            print("✅ Cleanup completed")


async def main():
    """Main function"""
    interactive_reader = InteractiveBMSReader()
    await interactive_reader.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Application terminated by user")
        sys.exit(0)