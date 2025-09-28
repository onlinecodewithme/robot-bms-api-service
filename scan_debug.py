#!/usr/bin/env python3
"""
BLE Scan Debug Tool
Helps diagnose BMS detection issues by showing all discoverable devices
"""

import asyncio
import sys
from bleak import BleakScanner
from bleak.backends.device import BLEDevice

async def detailed_scan():
    """Perform detailed BLE scan with extended timeout"""
    print("=== BLE Scan Debug Tool ===")
    print("This will scan for ALL BLE devices and show detailed information")
    print("Looking for your BMS device...")
    print("Target MAC: 41:18:12:01:18:9f")
    print("Target Name: DL-41181201189F")
    print()
    
    print("Scanning for 15 seconds with detailed info...")
    devices = await BleakScanner.discover(timeout=15.0)
    
    print(f"\n=== SCAN RESULTS ===")
    print(f"Found {len(devices)} BLE devices:")
    print()
    
    for i, device in enumerate(devices, 1):
        print(f"Device #{i}:")
        print(f"  Name: {device.name or 'Unknown'}")
        print(f"  Address: {device.address}")
        print(f"  RSSI: {getattr(device, 'rssi', 'Unknown')} dBm")
        
        # Check if this could be our BMS
        address_match = device.address.lower() == "41:18:12:01:18:9f"
        name_match = device.name == "DL-41181201189F" if device.name else False
        
        # Check for any Daly/BMS related names
        name_str = (device.name or "").lower()
        potential_bms = any(keyword in name_str for keyword in ["daly", "bms", "dl-", "41181201189f"])
        
        if address_match:
            print(f"  *** EXACT MAC ADDRESS MATCH! ***")
        if name_match:
            print(f"  *** EXACT NAME MATCH! ***")
        if potential_bms:
            print(f"  *** POTENTIAL BMS DEVICE ***")
        
        # Show advertisement data if available
        if hasattr(device, 'metadata') and device.metadata:
            print(f"  Metadata: {device.metadata}")
        
        print()
    
    # Summary
    print("=== ANALYSIS ===")
    target_found = any(d.address.lower() == "41:18:12:01:18:9f" for d in devices)
    name_found = any(d.name == "DL-41181201189F" for d in devices if d.name)
    potential_devices = []
    
    for device in devices:
        name_str = (device.name or "").lower()
        if any(keyword in name_str for keyword in ["daly", "bms", "dl-"]):
            potential_devices.append(device)
    
    if target_found:
        print("✅ Target MAC address found!")
    else:
        print("❌ Target MAC address NOT found")
        
    if name_found:
        print("✅ Target device name found!")
    else:
        print("❌ Target device name NOT found")
    
    if potential_devices:
        print(f"🔍 Found {len(potential_devices)} potential BMS devices:")
        for device in potential_devices:
            print(f"   - {device.name} [{device.address}]")
    else:
        print("⚠️  No obvious BMS devices detected")
    
    print("\n=== TROUBLESHOOTING SUGGESTIONS ===")
    if not target_found and not name_found:
        print("1. ❗ Check if BMS is powered ON")
        print("2. ❗ Make sure BMS is within 5-10 meters of Raspberry Pi") 
        print("3. ❗ Verify BMS is in discoverable mode")
        print("4. ❗ Try using the BMS mobile app to confirm it's advertising")
        print("5. ❗ Check if MAC address has changed (some devices rotate MACs)")
    
    if potential_devices:
        print("6. 🔧 Try updating the MAC/name in the code to match detected devices")
        print("7. 🔧 Use interactive mode to manually connect to potential devices")
    
    print("8. 🔧 Try running as root: sudo ./venv/bin/python scan_debug.py")
    print("9. 🔧 Check Bluetooth status: sudo systemctl status bluetooth")
    print("10. 🔧 Reset Bluetooth: sudo systemctl restart bluetooth")


if __name__ == "__main__":
    try:
        asyncio.run(detailed_scan())
    except KeyboardInterrupt:
        print("\nScan interrupted by user")
    except Exception as e:
        print(f"Error during scan: {e}")
        sys.exit(1)