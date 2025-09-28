#!/usr/bin/env python3
"""
BMS Data Formatter
Formats BMS_DATA JSON output into human-readable display
Based on the ESP32 reference test_json_output.py implementation
"""

import json
import sys
import re
from datetime import datetime
from typing import Dict, Any, Optional

class BMSDataFormatter:
    """Formats BMS JSON data for human-readable output"""
    
    def __init__(self, show_raw_data: bool = False, show_all_cells: bool = False):
        self.show_raw_data = show_raw_data
        self.show_all_cells = show_all_cells
    
    def format_timestamp(self, timestamp: int) -> str:
        """Convert timestamp to readable format"""
        try:
            # Handle both seconds and milliseconds timestamps
            if timestamp > 1000000000000:  # Milliseconds
                dt = datetime.fromtimestamp(timestamp / 1000)
            else:  # Seconds
                dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(timestamp)
    
    def format_cell_voltages(self, cell_voltages: list, pack_voltage: float) -> str:
        """Format cell voltage information"""
        if not cell_voltages:
            return "No cell voltage data"
        
        output = []
        output.append(f"📱 Cell Voltages ({len(cell_voltages)} cells):")
        
        # Calculate statistics
        voltages = [cell.get('voltage', 0) for cell in cell_voltages]
        min_v = min(voltages)
        max_v = max(voltages)
        avg_v = sum(voltages) / len(voltages)
        diff_v = max_v - min_v
        
        output.append(f"   Pack Total: {pack_voltage:.3f}V")
        output.append(f"   Average: {avg_v:.3f}V")
        output.append(f"   Min: {min_v:.3f}V")
        output.append(f"   Max: {max_v:.3f}V")
        output.append(f"   Difference: {diff_v:.3f}V ({diff_v*1000:.1f}mV)")
        
        # Balance status
        if diff_v > 0.05:
            balance_status = "⚠️  HIGH IMBALANCE"
        elif diff_v > 0.02:
            balance_status = "⚡ MINOR IMBALANCE" 
        else:
            balance_status = "✅ WELL BALANCED"
        output.append(f"   Balance: {balance_status}")
        
        # Show individual cells
        if self.show_all_cells:
            output.append("   Individual Cells:")
            for i in range(0, len(cell_voltages), 4):  # 4 cells per row
                row_cells = cell_voltages[i:i+4]
                row_str = "   "
                for cell in row_cells:
                    cell_num = cell.get('cellNumber', 0)
                    voltage = cell.get('voltage', 0)
                    row_str += f"  C{cell_num:2d}: {voltage:.3f}V"
                output.append(row_str)
        else:
            # Show only first few and last few cells
            output.append("   Sample Cells:")
            for i, cell in enumerate(cell_voltages[:4]):  # First 4
                cell_num = cell.get('cellNumber', 0)
                voltage = cell.get('voltage', 0)
                if i == 0:
                    output.append(f"      C{cell_num:2d}: {voltage:.3f}V  (first)")
                else:
                    output.append(f"      C{cell_num:2d}: {voltage:.3f}V")
            
            if len(cell_voltages) > 8:
                output.append("      ...")
            
            for i, cell in enumerate(cell_voltages[-4:]):  # Last 4
                cell_num = cell.get('cellNumber', 0)
                voltage = cell.get('voltage', 0)
                if i == 3:
                    output.append(f"      C{cell_num:2d}: {voltage:.3f}V  (last)")
                else:
                    output.append(f"      C{cell_num:2d}: {voltage:.3f}V")
        
        return "\n".join(output)
    
    def format_battery_status(self, soc: float, current: float, voltage: float) -> str:
        """Format battery status information"""
        output = []
        
        # SOC status
        if soc >= 80:
            soc_status = "🔋 HIGH"
            soc_icon = "🟢"
        elif soc >= 50:
            soc_status = "🔋 MEDIUM"
            soc_icon = "🟡"
        elif soc >= 20:
            soc_status = "🔋 LOW"
            soc_icon = "🟠"
        else:
            soc_status = "🔋 CRITICAL"
            soc_icon = "🔴"
        
        # Current status
        if abs(current) < 0.1:
            current_status = "⏸️  IDLE"
        elif current > 0.1:
            current_status = "⚡ CHARGING"
        else:
            current_status = "⬇️  DISCHARGING"
        
        # Power calculation
        power = voltage * abs(current)
        
        output.append(f"🔋 Battery Status:")
        output.append(f"   State of Charge: {soc_icon} {soc:.1f}% ({soc_status})")
        output.append(f"   Pack Voltage: ⚡ {voltage:.3f}V")
        output.append(f"   Current: {current_status} {current:.2f}A")
        output.append(f"   Power: 💡 {power:.2f}W")
        
        return "\n".join(output)
    
    def format_capacity_info(self, remaining: float, total: float, cycles: int) -> str:
        """Format capacity and cycle information"""
        percentage = (remaining / total * 100) if total > 0 else 0
        
        output = []
        output.append(f"📊 Capacity Information:")
        output.append(f"   Remaining: {remaining:.1f}Ah ({percentage:.1f}%)")
        output.append(f"   Total Capacity: {total:.1f}Ah")
        output.append(f"   Charge Cycles: {cycles:,}")
        
        # Health estimation based on cycles
        if cycles < 100:
            health = "🟢 EXCELLENT"
        elif cycles < 500:
            health = "🟡 GOOD"
        elif cycles < 1000:
            health = "🟠 FAIR"
        else:
            health = "🔴 AGED"
        
        output.append(f"   Battery Health: {health}")
        
        return "\n".join(output)
    
    def format_temperatures(self, temperatures: list) -> str:
        """Format temperature information"""
        if not temperatures:
            return "🌡️  Temperature: No data available"
        
        output = []
        output.append(f"🌡️  Temperature ({len(temperatures)} sensors):")
        
        temps = [t.get('temperature', 0) for t in temperatures]
        min_temp = min(temps)
        max_temp = max(temps)
        avg_temp = sum(temps) / len(temps)
        
        # Temperature status
        if max_temp >= 50:
            temp_status = "🔥 HOT - WARNING"
        elif max_temp >= 40:
            temp_status = "🌡️  WARM"
        elif min_temp <= 5:
            temp_status = "🧊 COLD"
        else:
            temp_status = "✅ NORMAL"
        
        output.append(f"   Status: {temp_status}")
        if len(temps) > 1:
            output.append(f"   Average: {avg_temp:.1f}°C")
            output.append(f"   Range: {min_temp:.1f}°C - {max_temp:.1f}°C")
        
        # Individual sensors
        for temp in temperatures:
            sensor = temp.get('sensor', 'Unknown')
            temp_val = temp.get('temperature', 0)
            output.append(f"   {sensor}: {temp_val:.1f}°C")
        
        return "\n".join(output)
    
    def format_mos_status(self, mos_status: dict) -> str:
        """Format MOS status information"""
        output = []
        output.append(f"🔌 MOS Status:")
        
        charging = mos_status.get('chargingMos', False)
        discharging = mos_status.get('dischargingMos', False)
        balancing = mos_status.get('balancing', False)
        
        charge_icon = "✅ ON" if charging else "❌ OFF"
        discharge_icon = "✅ ON" if discharging else "❌ OFF"
        balance_icon = "⚖️  ACTIVE" if balancing else "⏸️  INACTIVE"
        
        output.append(f"   Charging MOS: {charge_icon}")
        output.append(f"   Discharging MOS: {discharge_icon}")
        output.append(f"   Cell Balancing: {balance_icon}")
        
        # Overall status
        if charging and discharging:
            overall = "🟢 OPERATIONAL"
        elif not charging and not discharging:
            overall = "🔴 PROTECTION MODE"
        else:
            overall = "🟡 PARTIAL OPERATION"
        
        output.append(f"   Overall: {overall}")
        
        return "\n".join(output)
    
    def format_protocol_info(self, daly_protocol: dict) -> str:
        """Format protocol information"""
        output = []
        
        if self.show_raw_data:
            output.append(f"🔗 Protocol Information:")
            
            status = daly_protocol.get('status', 'Unknown')
            notifications = daly_protocol.get('notifications', 'Unknown')
            
            output.append(f"   Connection Status: {status}")
            output.append(f"   Notifications: {notifications}")
            
            commands = daly_protocol.get('commands', {})
            main_info = commands.get('main_info', {})
            
            if main_info:
                command_sent = main_info.get('command_sent', '')
                response_received = main_info.get('response_received', False)
                checksum = main_info.get('parsed_data', {}).get('checksum', '')
                
                output.append(f"   Command Sent: {command_sent}")
                output.append(f"   Response: {'✅ Received' if response_received else '❌ Failed'}")
                output.append(f"   Checksum: {checksum}")
        
        return "\n".join(output) if output else ""
    
    def parse_and_format(self, line: str) -> Optional[str]:
        """Parse BMS_DATA line and return formatted output"""
        if not line.startswith('BMS_DATA:'):
            return None
        
        try:
            # Extract JSON data
            json_data = line[9:]  # Remove 'BMS_DATA:' prefix
            data = json.loads(json_data)
            
            if not data.get('data_found', False):
                return "⚠️  No valid BMS data found"
            
            # Extract data sections
            timestamp = data.get('timestamp', 0)
            device = data.get('device', 'Unknown')
            mac_address = data.get('mac_address', 'Unknown')
            
            daly_protocol = data.get('daly_protocol', {})
            commands = daly_protocol.get('commands', {})
            main_info = commands.get('main_info', {})
            parsed_data = main_info.get('parsed_data', {})
            
            if not parsed_data:
                return "⚠️  No parsed BMS data available"
            
            # Build formatted output
            output = []
            
            # Header
            formatted_time = self.format_timestamp(timestamp)
            output.append("=" * 80)
            output.append(f"🔋 DALY BMS READER - {formatted_time}")
            output.append(f"📱 Device: {device} [{mac_address}]")
            output.append("=" * 80)
            
            # Battery status
            pack_voltage = parsed_data.get('packVoltage', 0)
            current = parsed_data.get('current', 0)
            soc = parsed_data.get('soc', 0)
            
            output.append(self.format_battery_status(soc, current, pack_voltage))
            output.append("")
            
            # Cell voltages
            cell_voltages = parsed_data.get('cellVoltages', [])
            output.append(self.format_cell_voltages(cell_voltages, pack_voltage))
            output.append("")
            
            # Capacity information
            remaining = parsed_data.get('remainingCapacity', 0)
            total = parsed_data.get('totalCapacity', 0)
            cycles = parsed_data.get('cycles', 0)
            
            output.append(self.format_capacity_info(remaining, total, cycles))
            output.append("")
            
            # Temperature information
            temperatures = parsed_data.get('temperatures', [])
            output.append(self.format_temperatures(temperatures))
            output.append("")
            
            # MOS status
            mos_status = parsed_data.get('mosStatus', {})
            output.append(self.format_mos_status(mos_status))
            output.append("")
            
            # Protocol info (if requested)
            protocol_info = self.format_protocol_info(daly_protocol)
            if protocol_info:
                output.append(protocol_info)
                output.append("")
            
            output.append("=" * 80)
            
            return "\n".join(output)
            
        except json.JSONDecodeError as e:
            return f"❌ JSON parsing failed: {e}"
        except Exception as e:
            return f"❌ Formatting failed: {e}"


def main():
    """Main function - can be used as a filter or standalone"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Format BMS_DATA JSON output for human reading')
    parser.add_argument('--show-raw', action='store_true', help='Show raw protocol information')
    parser.add_argument('--show-all-cells', action='store_true', help='Show all cell voltages')
    parser.add_argument('--input', '-i', help='Input file (default: stdin)')
    parser.add_argument('--continuous', '-c', action='store_true', help='Continuous mode - monitor stdin for new lines')
    
    args = parser.parse_args()
    
    formatter = BMSDataFormatter(show_raw_data=args.show_raw, show_all_cells=args.show_all_cells)
    
    if args.input:
        # Read from file
        try:
            with open(args.input, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BMS_DATA:'):
                        formatted = formatter.parse_and_format(line)
                        if formatted:
                            print(formatted)
                            print()
        except FileNotFoundError:
            print(f"❌ File not found: {args.input}")
            sys.exit(1)
    else:
        # Read from stdin
        try:
            if args.continuous:
                print("🔄 Monitoring for BMS_DATA lines... (Ctrl+C to exit)")
                print()
            
            for line in sys.stdin:
                line = line.strip()
                if line.startswith('BMS_DATA:'):
                    formatted = formatter.parse_and_format(line)
                    if formatted:
                        print(formatted)
                        print()
                elif not args.continuous:
                    # In non-continuous mode, pass through non-BMS lines
                    print(line)
        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            sys.exit(0)


if __name__ == '__main__':
    main()