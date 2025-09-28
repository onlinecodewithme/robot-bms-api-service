#!/usr/bin/env python3
"""
System Test Script for Raspberry Pi Daly BMS Reader
Tests system requirements, Bluetooth functionality, and basic operation
"""

import sys
import subprocess
import asyncio
import json
import time
from pathlib import Path

# Test data - simulated BMS response for protocol testing
TEST_BMS_RESPONSE = bytes.fromhex(
    "d2037c0cf60cf60cf60cf70cf50cf60cf60cf60cf60cf50cf30cf60cf60cf60cf60cf4"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000388000000000000000000000"
    "00000000000000000000000000000000006a2c73"
)

class SystemTester:
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.test_results = []

    def print_header(self):
        print("=== Raspberry Pi Daly BMS Reader System Test ===")
        print("This script tests system requirements and functionality")
        print("==================================================")
        print()

    def test_result(self, test_name: str, passed: bool, message: str = ""):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"     {message}")
        
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1
        print()

    def test_python_version(self):
        """Test Python version requirement"""
        version = sys.version_info
        required = (3, 8)
        
        passed = version >= required
        message = f"Python {version.major}.{version.minor}.{version.micro} (required: {required[0]}.{required[1]}+)"
        
        self.test_result("Python Version", passed, message)

    def test_system_platform(self):
        """Test if running on appropriate platform"""
        import platform
        
        system = platform.system()
        machine = platform.machine()
        
        # Check for Linux (Raspberry Pi runs Linux)
        is_linux = system == "Linux"
        is_arm = "arm" in machine.lower() or "aarch64" in machine.lower()
        
        message = f"{system} {machine}"
        if is_linux and is_arm:
            message += " (Raspberry Pi detected)"
        elif is_linux:
            message += " (Linux - compatible)"
        else:
            message += " (May not support Bluetooth properly)"
            
        self.test_result("System Platform", is_linux, message)

    def test_required_files(self):
        """Test if required files are present"""
        required_files = [
            "daly_bms_reader.py",
            "interactive_bms_reader.py", 
            "requirements.txt",
            "install.sh",
            "README.md"
        ]
        
        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)
        
        passed = len(missing_files) == 0
        message = f"All files present" if passed else f"Missing: {', '.join(missing_files)}"
        
        self.test_result("Required Files", passed, message)

    def test_python_dependencies(self):
        """Test if Python dependencies can be imported"""
        dependencies = [
            ("asyncio", "asyncio"),
            ("json", "json"),
            ("struct", "struct"),
            ("dataclasses", "dataclasses"),
            ("logging", "logging")
        ]
        
        # Test optional dependencies
        optional_deps = [
            ("bleak", "bleak")
        ]
        
        failed_deps = []
        
        # Test required dependencies
        for name, module in dependencies:
            try:
                __import__(module)
            except ImportError:
                failed_deps.append(name)
        
        passed = len(failed_deps) == 0
        message = "All core dependencies available" if passed else f"Missing: {', '.join(failed_deps)}"
        
        self.test_result("Python Core Dependencies", passed, message)
        
        # Test optional dependencies
        optional_failed = []
        for name, module in optional_deps:
            try:
                __import__(module)
            except ImportError:
                optional_failed.append(name)
        
        if optional_failed:
            message = f"Optional dependencies missing: {', '.join(optional_failed)} (install with: pip install -r requirements.txt)"
            self.test_result("Optional Dependencies", False, message)
        else:
            self.test_result("Optional Dependencies", True, "All optional dependencies available")

    def test_bluetooth_service(self):
        """Test if Bluetooth service is running"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "bluetooth"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            passed = result.returncode == 0 and result.stdout.strip() == "active"
            message = f"Bluetooth service is {'active' if passed else 'not active'}"
            
            if not passed:
                message += " (run: sudo systemctl start bluetooth)"
                
        except subprocess.TimeoutExpired:
            passed = False
            message = "Bluetooth service check timed out"
        except FileNotFoundError:
            passed = False
            message = "systemctl command not found (not systemd system?)"
        except Exception as e:
            passed = False
            message = f"Error checking Bluetooth service: {e}"
        
        self.test_result("Bluetooth Service", passed, message)

    def test_bluetooth_device(self):
        """Test if Bluetooth device is available"""
        try:
            result = subprocess.run(
                ["hciconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            has_hci = "hci0" in result.stdout
            is_up = "UP RUNNING" in result.stdout
            
            passed = has_hci and is_up
            
            if has_hci and is_up:
                message = "Bluetooth device (hci0) is UP and RUNNING"
            elif has_hci:
                message = "Bluetooth device found but not running (try: sudo hciconfig hci0 up)"
            else:
                message = "No Bluetooth device found"
                
        except subprocess.TimeoutExpired:
            passed = False
            message = "hciconfig check timed out"
        except FileNotFoundError:
            passed = False
            message = "hciconfig command not found (install: sudo apt install bluez)"
        except Exception as e:
            passed = False
            message = f"Error checking Bluetooth device: {e}"
        
        self.test_result("Bluetooth Device", passed, message)

    async def test_ble_scan(self):
        """Test BLE scanning capability"""
        try:
            # Import bleak here to test if it's available
            from bleak import BleakScanner
            
            print("Testing BLE scan (5 second timeout)...")
            devices = await asyncio.wait_for(
                BleakScanner.discover(timeout=5.0),
                timeout=10.0
            )
            
            device_count = len(devices)
            passed = True  # Scanning worked, even if no devices found
            
            message = f"Found {device_count} BLE devices"
            if device_count > 0:
                message += f" (first: {devices[0].name or 'Unknown'} [{devices[0].address}])"
            
        except ImportError:
            passed = False
            message = "bleak library not installed (run: pip install -r requirements.txt)"
        except asyncio.TimeoutError:
            passed = False
            message = "BLE scan timed out (check Bluetooth permissions)"
        except Exception as e:
            passed = False
            message = f"BLE scan failed: {e}"
        
        self.test_result("BLE Scanning", passed, message)

    def test_protocol_parsing(self):
        """Test BMS protocol parsing with test data"""
        try:
            # Import the BMS reader
            from daly_bms_reader import DalyBMSReader
            
            # Create reader instance
            reader = DalyBMSReader()
            
            # Test parsing with simulated data
            success = reader.parse_bms_response(TEST_BMS_RESPONSE)
            
            if success:
                data = reader.bms_data
                expected_cells = 16
                has_cells = len(data.cell_voltages) == expected_cells
                has_voltage = data.pack_voltage > 0
                has_valid_data = data.data_valid
                
                passed = has_cells and has_voltage and has_valid_data
                message = f"Parsed {len(data.cell_voltages)} cells, pack voltage: {data.pack_voltage:.3f}V"
            else:
                passed = False
                message = "Protocol parsing failed with test data"
                
        except ImportError as e:
            passed = False
            message = f"Cannot import BMS reader: {e}"
        except Exception as e:
            passed = False
            message = f"Protocol parsing error: {e}"
        
        self.test_result("Protocol Parsing", passed, message)

    def test_json_output(self):
        """Test JSON output generation"""
        try:
            from daly_bms_reader import DalyBMSReader
            
            # Create reader and parse test data
            reader = DalyBMSReader()
            reader.parse_bms_response(TEST_BMS_RESPONSE)
            
            # Generate JSON output
            json_output = reader.create_json_output()
            
            # Verify it's valid JSON
            parsed = json.loads(json_output)
            
            # Check required fields
            required_fields = ["timestamp", "device", "mac_address", "daly_protocol", "data_found"]
            missing_fields = [field for field in required_fields if field not in parsed]
            
            passed = len(missing_fields) == 0
            message = "Valid JSON with all required fields" if passed else f"Missing fields: {missing_fields}"
            
        except json.JSONDecodeError:
            passed = False
            message = "Generated invalid JSON"
        except Exception as e:
            passed = False
            message = f"JSON generation error: {e}"
        
        self.test_result("JSON Output", passed, message)

    def test_permissions(self):
        """Test user permissions for Bluetooth access"""
        try:
            import grp
            import os
            
            # Check if user is in bluetooth group
            user_groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
            in_bluetooth_group = "bluetooth" in user_groups
            
            if in_bluetooth_group:
                passed = True
                message = "User is in bluetooth group"
            else:
                passed = False
                message = "User not in bluetooth group (run: sudo usermod -a -G bluetooth $USER)"
                
        except Exception as e:
            passed = False
            message = f"Error checking permissions: {e}"
        
        self.test_result("Bluetooth Permissions", passed, message)

    async def run_all_tests(self):
        """Run all system tests"""
        self.print_header()
        
        print("🔍 Running system tests...")
        print()
        
        # Basic system tests
        self.test_python_version()
        self.test_system_platform()
        self.test_required_files()
        self.test_python_dependencies()
        
        # Bluetooth tests
        self.test_bluetooth_service()
        self.test_bluetooth_device()
        self.test_permissions()
        
        # BLE functionality test
        await self.test_ble_scan()
        
        # Application tests
        self.test_protocol_parsing()
        self.test_json_output()
        
        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        
        total_tests = self.tests_passed + self.tests_failed
        success_rate = (self.tests_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Tests Run: {total_tests}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        print()
        
        if self.tests_failed == 0:
            print("🎉 ALL TESTS PASSED!")
            print("Your system is ready for BMS communication.")
        else:
            print("⚠️  SOME TESTS FAILED")
            print("Please fix the issues above before using the BMS reader.")
            print()
            print("Common fixes:")
            print("• Install dependencies: ./install.sh")
            print("• Start Bluetooth: sudo systemctl start bluetooth") 
            print("• Add user to group: sudo usermod -a -G bluetooth $USER")
            print("• Enable Bluetooth device: sudo hciconfig hci0 up")
        
        print()
        print("For detailed setup instructions, see README.md")
        print("=" * 50)


async def main():
    """Main test function"""
    tester = SystemTester()
    await tester.run_all_tests()
    
    # Return exit code based on test results
    return 0 if tester.tests_failed == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        sys.exit(1)