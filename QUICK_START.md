# Quick Start Guide

## 1. Installation (30 seconds)
```bash
cd raspberry_pi_bms_reader
./install.sh
```

## 2. Test System (1 minute)
```bash
./test_system.py
```

## 3. Start Reading (immediately)
```bash
# Interactive mode
./interactive_bms_reader.py

# OR continuous mode
./daly_bms_reader.py
```

## 4. Basic Commands
In interactive mode:
- `scan` - Find your BMS
- `connect` - Connect to BMS  
- `data` - Read data once
- `continuous` - Start continuous reading
- `help` - Show all commands

## 5. Expected Output
```
BMS_DATA:{"timestamp":1640995200000,"device":"DL-41181201189F","mac_address":"41:18:12:01:18:9f","daly_protocol":{"status":"characteristics_found","notifications":"enabled","commands":{"main_info":{"command_sent":"D2030000003ED7B9","response_received":true,"response_data":"d2037c...","parsed_data":{"cellVoltages":[{"cellNumber":1,"voltage":3.318}...],"packVoltage":53.080,"current":0.0,"soc":90.4,"remainingCapacity":207.9,"totalCapacity":230,"cycles":1,"temperatures":[{"sensor":"T1","temperature":30}],"mosStatus":{"chargingMos":true,"dischargingMos":true,"balancing":false}}}},"data_found":true}
```

This output is identical to the ESP32 version and compatible with existing ROS2 integrations.

## Troubleshooting
- **Connection failed**: Check BMS is powered and in range
- **Permission denied**: Run `newgrp bluetooth` or logout/login
- **No devices found**: Try `sudo hciconfig hci0 up`
- **Dependencies missing**: Run `./install.sh` again

See README.md for detailed documentation.