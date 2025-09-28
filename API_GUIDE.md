# BMS API Service Guide

## 🚀 Quick Setup

```bash
# 1. Install the base system (if not already done)
./install.sh

# 2. Install API services for auto-startup
sudo ./install_services.sh
```

## 🌐 API Endpoints

Once installed, the API runs on port 5000 and provides these endpoints:

### 📋 Core Endpoints

| Endpoint | Description | Use Case |
|----------|-------------|----------|
| `/` | API documentation | Getting started |
| `/health` | Service health check | Monitoring/alerts |
| `/status` | Detailed service status | Troubleshooting |

### 🔋 BMS Data Endpoints

| Endpoint | Description | Response Time | Use Case |
|----------|-------------|---------------|----------|
| `/bms` | Full BMS data | ~1ms | Complete information |
| `/bms/summary` | Key metrics only | ~1ms | Fast polling/dashboards |
| `/bms/raw` | Raw with protocol details | ~1ms | Development/debugging |
| `/bms/formatted` | Human-readable text | ~1ms | Display/logging |
| `/bms/cells` | Cell voltage details | ~1ms | Cell monitoring |
| `/bms/temps` | Temperature information | ~1ms | Thermal monitoring |

## 🔥 Fast Response Times

**All API calls return in ~1ms** because they read from cached file instead of waiting for Bluetooth communication!

## 📊 Example API Calls

### Health Check
```bash
curl http://localhost:5000/health
```
```json
{
  "status": "healthy",
  "timestamp": 1759042409539,
  "data_available": true,
  "data_age": 2.1,
  "data_fresh": true
}
```

### BMS Summary (Fast Polling)
```bash
curl http://localhost:5000/bms/summary
```
```json
{
  "connected": true,
  "timestamp": 1759042409539,
  "device": "DL-41181201189F",
  "pack_voltage": 52.395,
  "current": 0.0,
  "soc": 49.4,
  "remaining_capacity": 113.62,
  "total_capacity": 230.0,
  "cycles": 1,
  "cell_count": 16,
  "min_cell_voltage": 3.273,
  "max_cell_voltage": 3.275,
  "cell_voltage_diff": 0.002,
  "avg_temperature": 29.0,
  "charging_mos": true,
  "discharging_mos": true,
  "balancing": false,
  "freshness": {
    "age_seconds": 2.1,
    "is_fresh": true
  }
}
```

### Full BMS Data
```bash
curl http://localhost:5000/bms
```
```json
{
  "timestamp": 1759042409539,
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
          "cellVoltages": [...],
          "packVoltage": 52.395,
          "current": 0.0,
          "soc": 49.4,
          "temperatures": [...],
          "mosStatus": {...}
        }
      }
    }
  },
  "data_found": true,
  "freshness": {
    "age_seconds": 2.1,
    "is_fresh": true
  }
}
```

### Human-Readable Format
```bash
curl http://localhost:5000/bms/formatted
```
```
================================================================================
🔋 DALY BMS READER - 2025-09-28 12:14:46
📱 Device: DL-41181201189F [41:18:12:01:18:9f]
================================================================================
🔋 Battery Status:
   State of Charge: 🟠 49.4% (🔋 LOW)
   Pack Voltage: ⚡ 52.395V
   Current: ⏸️  IDLE 0.00A
   Power: 💡 0.00W

📱 Cell Voltages (16 cells):
   Pack Total: 52.395V
   Average: 3.275V
   Min: 3.273V
   Max: 3.275V
   Difference: 0.002V (2.0mV)
   Balance: ✅ WELL BALANCED
...
```

### Cell Details
```bash
curl http://localhost:5000/bms/cells
```
```json
{
  "timestamp": 1759042409539,
  "cell_count": 16,
  "cells": [
    {"cellNumber": 1, "voltage": 3.275},
    {"cellNumber": 2, "voltage": 3.275},
    ...
  ],
  "pack_voltage": 52.395,
  "statistics": {
    "min_voltage": 3.273,
    "max_voltage": 3.275,
    "avg_voltage": 3.274,
    "voltage_diff": 0.002,
    "balance_status": "good"
  }
}
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   BMS Device    │◄──►│ Background      │───►│  /tmp/          │
│                 │BLE │ Service         │JSON│  bms_latest.json│
│ 41:18:12:01:18:9F│    │ (every 5s)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        ▲
                                                        │ read (~1ms)
                       ┌─────────────────┐              │
                       │   API Service   │◄─────────────┘
                       │   Port 5000     │
                       │                 │
                       └─────────────────┘
                                ▲
                                │ HTTP requests
                       ┌─────────────────┐
                       │    Clients      │
                       │ Dashboards, Apps│
                       │   Monitoring    │
                       └─────────────────┘
```

## 🔧 Service Management

### Check Status
```bash
sudo systemctl status bms-background  # Data collector
sudo systemctl status bms-api         # REST API server
```

### Restart Services
```bash
sudo systemctl restart bms-background
sudo systemctl restart bms-api
```

### View Logs
```bash
sudo journalctl -u bms-background -f  # Follow background logs
sudo journalctl -u bms-api -f         # Follow API logs
```

### Stop/Start Services
```bash
sudo systemctl stop bms-background
sudo systemctl stop bms-api
sudo systemctl start bms-background
sudo systemctl start bms-api
```

## 🌍 Remote Access

### From Same Network
```bash
# Replace with your Raspberry Pi's IP address
curl http://192.168.1.100:5000/bms/summary
```

### From Web Browser
Open: `http://192.168.1.100:5000/` (replace with your Pi's IP)

## 📱 Integration Examples

### Python Script
```python
import requests
import json

# Get BMS summary
response = requests.get('http://localhost:5000/bms/summary')
data = response.json()

if data['connected']:
    print(f"Battery: {data['soc']:.1f}% ({data['pack_voltage']:.2f}V)")
    print(f"Current: {data['current']:.2f}A")
    print(f"Cells: {data['cell_count']} ({data['cell_voltage_diff']:.3f}V diff)")
else:
    print("BMS not connected")
```

### Dashboard Integration
```javascript
// Fetch BMS data for dashboard
fetch('http://raspberry-pi:5000/bms/summary')
  .then(response => response.json())
  .then(data => {
    document.getElementById('soc').textContent = data.soc.toFixed(1) + '%';
    document.getElementById('voltage').textContent = data.pack_voltage.toFixed(2) + 'V';
    document.getElementById('current').textContent = data.current.toFixed(2) + 'A';
  });
```

### Monitoring Script
```bash
#!/bin/bash
# Simple monitoring script
while true; do
  STATUS=$(curl -s http://localhost:5000/health | jq -r '.status')
  if [ "$STATUS" != "healthy" ]; then
    echo "⚠️ BMS service unhealthy at $(date)"
    # Send alert notification here
  fi
  sleep 60
done
```

## 🛡️ Security

- API only accepts connections from local network ranges
- Services run as non-root user with restricted permissions
- Data files are in `/tmp` with appropriate access controls
- Resource limits prevent excessive CPU/memory usage

## 🔍 Troubleshooting

### API Not Responding
```bash
# Check if service is running
sudo systemctl status bms-api

# Check if port is open
netstat -tlnp | grep :5000

# Check logs
sudo journalctl -u bms-api --since "5 minutes ago"
```

### No BMS Data
```bash
# Check background service
sudo systemctl status bms-background

# Check data file
ls -la /tmp/bms_*.json
cat /tmp/bms_latest.json

# Check BMS connection
curl http://localhost:5000/status
```

### Service Won't Start
```bash
# Check service configuration
sudo systemctl daemon-reload
sudo systemctl enable bms-background
sudo systemctl enable bms-api

# Check service logs
sudo journalctl -u bms-background --since "10 minutes ago"
```

## 📈 Performance

- **API Response Time**: ~1ms (cached data)
- **Data Update Rate**: Every 5 seconds (configurable)
- **Memory Usage**: ~20MB total for both services
- **CPU Usage**: <5% on Raspberry Pi 4

## 🔗 Integration with Existing Systems

The API is fully compatible with existing ROS2 or other integrations - just change the data source from serial/direct connection to HTTP requests!