# Raspberry Pi Daly BMS BLE Reader v2.0

A comprehensive Python-based solution for reading battery data from Daly Smart BMS via Bluetooth Low Energy (BLE) using Raspberry Pi 4's built-in Bluetooth. This project provides both standalone BLE reading and a full REST API service with background data collection for production deployments.

## 🚀 Features

### Core Features
- **Native Raspberry Pi BLE Support**: Uses built-in Bluetooth without external hardware
- **Identical Protocol Implementation**: Same Daly BMS protocol parsing as ESP32 version
- **JSON-Compatible Output**: Structured data output for easy integration with ROS2 and other systems
- **Interactive Command Interface**: Terminal-based commands similar to ESP32 serial interface
- **Continuous Reading Mode**: Real-time monitoring with configurable intervals
- **Auto-discovery**: Automatic BMS device discovery and connection

### NEW in v2.0 - Production API Service
- **🔧 REST API Service**: Full HTTP API with multiple endpoints for fast data access
- **📊 Background Data Collection**: Continuous BMS data reading with file caching
- **🚀 Systemd Integration**: Auto-startup services that run on boot
- **⚡ Fast Response Times**: ~1ms API responses using cached data
- **🔍 Comprehensive Endpoints**: Health monitoring, status checks, formatted output
- **📁 Local Data Storage**: Production-ready data storage in dedicated folder
- **🔄 Enhanced Error Handling**: Robust connection recovery and logging
- **📡 Network Accessible**: HTTP API accessible from other devices on network

## 🔧 Hardware Requirements

- **Raspberry Pi 4 Model B** (or newer with built-in Bluetooth)
- **Daly Smart BMS** with BLE capability
- **Target BMS Configuration:**
  - Model: Daly Smart BMS
  - MAC Address: `41:18:12:01:18:9F`
  - Device Name: `DL-41181201189F`
  - Communication: Bluetooth Low Energy (BLE)

## 📦 Installation

### Quick Installation

Run the automated installation script:

```bash
cd raspberry_pi_bms_reader
chmod +x install.sh
./install.sh
```

The script will:
- Install system dependencies (Python, Bluetooth, etc.)
- Create a Python virtual environment
- Install required Python packages
- Configure Bluetooth services
- Add user to bluetooth group
- Create command shortcuts

### Manual Installation

If you prefer manual installation:

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev bluetooth bluez libbluetooth-dev pkg-config libglib2.0-dev

# Enable Bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x *.py
```

## 🚀 Usage

## NEW: REST API Service (Production Mode)

The v2.0 system includes a full REST API service with background data collection for production deployments.

### Quick Start - API Service

Install and start the production services:

```bash
cd raspberry_pi_bms_reader
sudo ./install_services.sh
```

This automatically:
- ✅ Installs and enables systemd services for auto-startup on boot
- ✅ Starts background BMS data collection service
- ✅ Starts REST API server on http://localhost:5000
- ✅ Creates local data storage in `bms_data/` folder
- ✅ Configures proper permissions and security

### API Endpoints

Once services are running, access BMS data via HTTP:

```bash
# Comprehensive BMS summary with all data
curl http://localhost:5000/bms/summary

# Human-readable formatted output
curl http://localhost:5000/bms/formatted

# Service health check
curl http://localhost:5000/health

# Complete raw BMS data
curl http://localhost:5000/bms

# Cell voltage details
curl http://localhost:5000/bms/cells

# Temperature information
curl http://localhost:5000/bms/temps
```

### Network Access

API is accessible from other devices on your network:

```bash
# Replace with your Raspberry Pi's IP address
curl http://192.168.1.186:5000/bms/summary
```

### Service Management

```bash
# Check service status
sudo systemctl status bms-background bms-api

# View real-time logs
sudo journalctl -u bms-background -f
sudo journalctl -u bms-api -f

# Restart services
sudo systemctl restart bms-background bms-api

# Stop services
sudo systemctl stop bms-background bms-api

# Disable auto-startup
sudo systemctl disable bms-background bms-api
```

### Data Files

The system stores data in the local `bms_data/` folder:

```bash
# View latest BMS data
cat raspberry_pi_bms_reader/bms_data/bms_latest.json

# View service status
cat raspberry_pi_bms_reader/bms_data/bms_status.json

# Check data freshness
ls -la raspberry_pi_bms_reader/bms_data/
```

## Standalone Usage (Development Mode)

### Interactive Mode (Recommended)

Start the interactive interface:

```bash
# After installation
./interactive_bms_reader.py
# or
daly-bms-interactive
```

### Available Commands

```
scan (s)     - Scan for BMS devices
connect (c)  - Connect to discovered BMS
data (d)     - Read BMS data once
status       - Show system status
auto         - Toggle auto-connect
reset (r)    - Reset and disconnect
services     - List BLE services/characteristics
continuous   - Start continuous reading (Ctrl+C to stop)
json         - Show last data in JSON format
help (h)     - Show available commands
exit (q)     - Exit application
```

### Continuous Mode

For continuous data output (suitable for logging or ROS2 integration):

```bash
./daly_bms_reader.py
# or
daly-bms-reader
```

### Example Usage Session

```
=== Raspberry Pi Daly BMS BLE Reader v1.0 ===
Interactive Command Interface
Target BMS MAC: 41:18:12:01:18:9f
Target BMS Name: DL-41181201189F
==============================================

Performing initial scan...
Scanning for BLE devices...
Found 5 BLE devices
Device #3: DL-41181201189F [41:18:12:01:18:9f] RSSI: -45 dBm
*** Target BMS found! ***
BMS device found: DL-41181201189F [41:18:12:01:18:9f]
Auto-connect enabled, attempting connection...
Connecting to: DL-41181201189F [41:18:12:01:18:9f]
*** Successfully connected to BMS via BLE! ***

BMS> data
Reading BMS data...

=== BMS Data ===
Pack Voltage: 53.080 V
Current: 0.00 A
Power: 0.00 W
SOC: 90.4%
Remaining Capacity: 207.9 Ah
Total Capacity: 230 Ah
Cycles: 1

--- Cell Voltages ---
Cell  1: 3.318 V
Cell  2: 3.318 V
...
Cell 16: 3.316 V
Max Cell: 3319 mV
Min Cell: 3315 mV
Cell Diff: 4 mV

--- Temperatures ---
T1: 30°C
T2: 30°C

--- MOS Status ---
Charging MOS: ✅ ON
Discharging MOS: ✅ ON
Balancing: ⏸️ INACTIVE
================

BMS> continuous
Starting continuous reading... (Press Ctrl+C to stop)
Data will be output in JSON format compatible with ROS2:

BMS_DATA:{"timestamp":1640995200000,"device":"DL-41181201189F","mac_address":"41:18:12:01:18:9f","daly_protocol":{"status":"characteristics_found","notifications":"enabled","commands":{"main_info":{"command_sent":"D2030000003ED7B9","response_received":true,"response_data":"d2037c0cf60cf60cf60cf70cf50cf60cf60cf60cf60cf50cf30cf60cf60cf60cf60cf4...","parsed_data":{"header":{"startByte":"0xD2","commandId":"0x03","dataLength":124},"cellVoltages":[{"cellNumber":1,"voltage":3.318},{"cellNumber":2,"voltage":3.318}...],"packVoltage":53.080,"current":0.0,"soc":90.4,"remainingCapacity":207.9,"totalCapacity":230,"cycles":1,"temperatures":[{"sensor":"T1","temperature":30},{"sensor":"T2","temperature":30}],"mosStatus":{"chargingMos":true,"dischargingMos":true,"balancing":false},"checksum":"0x2C73","timestamp":"1640995200000"}}},"data_found":true}
```

## 🔌 ROS2 Integration

The output format is identical to the ESP32 version, making it fully compatible with existing ROS2 nodes:

### Serial Output Contract

```
BMS_DATA:{"timestamp":1234567890,"device":"DL-41181201189F","mac_address":"41:18:12:01:18:9f","daly_protocol":{"status":"characteristics_found","notifications":"enabled","commands":{"main_info":{"command_sent":"D2030000003ED7B9","response_received":true,"response_data":"d2037c0cf60cf60cf60cf70cf50cf60cf60cf60cf60cf50cf30cf60cf60cf60cf60cf4","parsed_data":{"header":{"startByte":"0xD2","commandId":"0x03","dataLength":124},"cellVoltages":[...],"packVoltage":53.080,"current":0.0,"soc":90.4,"remainingCapacity":207.9,"totalCapacity":230,"cycles":1,"temperatures":[...],"mosStatus":{...},"checksum":"0x2C73","timestamp":"1234567890"}}},"data_found":true}
```

### ROS2 Node Integration

You can use the same ROS2 node code from the ESP32 version, just change the input source:

```python
# Instead of reading from serial port
# self.serial_conn = serial.Serial(self.serial_port, self.baud_rate, timeout=1)

# Use subprocess to read from the Python script
import subprocess

class DalyBMSReader(Node):
    def __init__(self):
        super().__init__('daly_bms_reader')
        
        # Start the Python BMS reader as a subprocess
        self.bms_process = subprocess.Popen(
            ['python3', '/path/to/raspberry_pi_bms_reader/daly_bms_reader.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Start reading thread
        self.reading_thread = threading.Thread(target=self.read_bms_data)
        self.reading_thread.daemon = True
        self.reading_thread.start()
    
    def read_bms_data(self):
        while rclpy.ok():
            try:
                line = self.bms_process.stdout.readline().strip()
                if line.startswith('BMS_DATA:'):
                    json_data = line[9:]  # Remove 'BMS_DATA:' prefix
                    self.process_bms_data(json_data)
            except Exception as e:
                self.get_logger().warn(f'BMS read error: {e}')
```

## ⚙️ Configuration

### BMS Settings

Update the target BMS information in [`daly_bms_reader.py`](daly_bms_reader.py):

```python
# BMS Configuration
TARGET_BMS_MAC = "41:18:12:01:18:9f"  # Your BMS MAC address
TARGET_BMS_NAME = "DL-41181201189F"   # Your BMS device name
```

### Reading Interval

Adjust the data reading frequency:

```python
# In DalyBMSReader.__init__()
self.read_interval = 5.0  # Read every 5 seconds
```

### Scan Timeout

Adjust BLE scanning duration:

```python
# In DalyBMSReader.__init__()
self.scan_timeout = 10.0  # Scan for 10 seconds
```

## 🔧 Technical Details

### Protocol Implementation

This implementation uses the same corrected Daly BMS protocol as the ESP32 version:

- **Protocol Constants**: `HEAD_READ = [0xD2, 0x03]`, `CMD_INFO = [0x00, 0x00, 0x00, 0x3E, 0xD7, 0xB9]`
- **Cell Voltages**: Bytes 3-35 (16 cells × 2 bytes each)
- **Pack Voltage**: Calculated sum of all cell voltages  
- **SOC**: Bytes 87-88 (value 904 = 90.4%)
- **Temperature Sensors**: T1 & T2 at bytes 68 & 70 (30°C with +40 offset)
- **Cycles**: Byte 106
- **Response Validation**: 129-byte response with CRC checking

### BLE Implementation

- **Library**: Uses `bleak` for cross-platform BLE support
- **Service UUID**: `0000fff0-0000-1000-8000-00805f9b34fb`
- **RX Characteristic**: `0000fff1-0000-1000-8000-00805f9b34fb` (Notifications)
- **TX Characteristic**: `0000fff2-0000-1000-8000-00805f9b34fb` (Write)

### Data Structure

```python
@dataclass
class BMSData:
    timestamp: int
    device_name: str
    mac_address: str
    pack_voltage: float
    current: float
    soc: float
    remaining_capacity: float
    total_capacity: float
    cycles: int
    cell_voltages: List[Dict[str, float]]
    temperatures: List[Dict[str, int]]
    mos_status: Dict[str, bool]
    max_cell_voltage: int
    min_cell_voltage: int
    data_valid: bool
```

## 🐛 Troubleshooting

### Bluetooth Issues

1. **Check Bluetooth Status**:
   ```bash
   sudo systemctl status bluetooth
   hciconfig  # Should show hci0 UP RUNNING
   ```

2. **Restart Bluetooth Service**:
   ```bash
   sudo systemctl restart bluetooth
   ```

3. **Check BLE Scanning**:
   ```bash
   sudo hcitool lescan
   # Should show BLE devices including your BMS
   ```

### Permission Issues

1. **Add User to Bluetooth Group**:
   ```bash
   sudo usermod -a -G bluetooth $USER
   newgrp bluetooth  # Apply immediately
   ```

2. **Check Group Membership**:
   ```bash
   groups  # Should include 'bluetooth'
   ```

### Connection Issues

1. **Verify BMS is Powered**: Make sure your BMS is active and advertising
2. **Check MAC Address**: Verify the MAC address in the code matches your device
3. **Signal Strength**: Move closer to the BMS (within 5-10 meters)
4. **Interference**: Check for other BLE devices that might cause interference

### Common Errors

- **`BLE connection failed`**: BMS out of range or powered off
- **`Service not found`**: BMS may use different service UUIDs
- **`Characteristics not found`**: BMS protocol mismatch
- **`Invalid response format`**: Response parsing error or corrupted data
- **`Permission denied`**: User not in bluetooth group

## 📊 Data Output Examples

### Successful Reading
```json
{
  "timestamp": 1640995200000,
  "device": "DL-41181201189F",
  "mac_address": "41:18:12:01:18:9f",
  "daly_protocol": {
    "status": "characteristics_found",
    "notifications": "enabled",
    "commands": {
      "main_info": {
        "command_sent": "D2030000003ED7B9",
        "response_received": true,
        "parsed_data": {
          "cellVoltages": [
            {"cellNumber": 1, "voltage": 3.318},
            {"cellNumber": 2, "voltage": 3.318}
          ],
          "packVoltage": 53.080,
          "current": 0.0,
          "soc": 90.4,
          "remainingCapacity": 207.9,
          "totalCapacity": 230,
          "cycles": 1,
          "temperatures": [
            {"sensor": "T1", "temperature": 30},
            {"sensor": "T2", "temperature": 30}
          ],
          "mosStatus": {
            "chargingMos": true,
            "dischargingMos": true,
            "balancing": false
          }
        }
      }
    }
  },
  "data_found": true
}
```

## 🔄 Differences from ESP32 Version

| Feature | ESP32 | Raspberry Pi |
|---------|--------|-------------|
| **Language** | C++ | Python 3.8+ |
| **BLE Library** | ESP32 BLE Arduino | bleak |
| **Platform** | ESP32 microcontroller | Raspberry Pi Linux |
| **Memory Usage** | ~50KB RAM | ~10-20MB RAM |
| **Processing Power** | 240MHz dual-core | 1.5GHz quad-core |
| **Installation** | Arduino IDE/PlatformIO | pip + virtual environment |
| **Interface** | Serial monitor | Terminal + SSH |
| **Integration** | USB serial to ROS2 | Direct process/network |
| **Debugging** | Serial output | Python logging + terminal |

## 📁 Project Structure

```
raspberry_pi_bms_reader/
├── Core BMS Reading
│   ├── daly_bms_reader.py          # Main continuous reading script
│   ├── interactive_bms_reader.py   # Interactive command interface
│   └── bms_data_formatter.py       # Human-readable data formatting
├── NEW v2.0 - Production API Service
│   ├── bms_background_service.py   # Background BMS data collection service
│   ├── bms_api_service.py          # REST API server with multiple endpoints
│   ├── install_services.sh         # Production service installer
│   └── bms_data/                   # Local data storage directory
│       ├── bms_latest.json         # Latest BMS data (auto-updated)
│       └── bms_status.json         # Service status information
├── System Integration
│   └── systemd/                    # Systemd service configurations
│       ├── bms-background.service  # Background collection service
│       └── bms-api.service         # REST API service
├── Development Tools
│   ├── scan_debug.py              # BLE scanning and debugging
│   ├── test_system.py             # System testing utilities
│   ├── run_bms_reader.sh          # Convenience script for BMS reader
│   └── run_formatted_reader.sh    # Convenience script for formatted output
├── Configuration & Setup
│   ├── requirements.txt            # Python dependencies
│   ├── setup.py                   # Package setup configuration
│   ├── install.sh                 # Automated installation script
│   └── .gitignore                 # Git ignore patterns
└── Documentation
    ├── README.md                  # Main documentation (this file)
    ├── API_GUIDE.md               # Comprehensive API documentation
    ├── QUICK_START.md             # Quick start guide
    └── TROUBLESHOOTING.md         # Troubleshooting guide
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with actual hardware
4. Submit a pull request

## 📄 License

This project is open source. See LICENSE file for details.

## 🙏 Acknowledgments

- Original ESP32 implementation developers
- bleak library contributors  
- Daly BMS protocol documentation
- Raspberry Pi Foundation
- Python BLE community

## 📞 Support

For issues or questions:

1. Check this troubleshooting section
2. Verify your hardware setup
3. Test with known working BMS
4. Check the logs for detailed error messages

---

**Status**: ✅ Production Ready v2.0 - Complete REST API service with systemd integration, enhanced BMS data logging, and auto-startup capabilities. Fully compatible with ESP32 version and tested on Raspberry Pi 4.

## 🆕 What's New in v2.0

- **🔧 REST API Service**: Complete HTTP API with multiple endpoints
- **📊 Background Data Collection**: Continuous BMS monitoring service
- **🚀 Systemd Integration**: Auto-startup services that run on boot
- **⚡ Lightning Fast**: ~1ms API response times using cached data
- **📡 Network Accessible**: HTTP API available on network (port 5000)
- **🔍 Enhanced Logging**: Complete BMS_DATA JSON logging
- **📁 Local Storage**: Production-ready data storage in `bms_data/`
- **🔄 Robust Recovery**: Enhanced error handling and reconnection logic
- **📈 Multiple Endpoints**: Health, status, summary, formatted, cells, temps
- **🛡️ Production Security**: Proper systemd security and permissions

Perfect for production deployments requiring reliable, high-performance BMS monitoring with web-based access and automatic system integration.