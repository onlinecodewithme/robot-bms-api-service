#!/usr/bin/env python3
"""
BMS REST API Service
Serves cached BMS data from file via HTTP endpoints for fast response
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from flask import Flask, jsonify, request, Response
from bms_data_formatter import BMSDataFormatter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bms_api')

# Flask app setup
app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Global configuration
DATA_FILE_PATH = Path("/tmp/bms_latest.json")
STATUS_FILE_PATH = Path("/tmp/bms_status.json")
MAX_DATA_AGE_SECONDS = 30  # Consider data stale after 30 seconds

class BMSAPIService:
    """BMS API Service for serving cached data"""
    
    def __init__(self, data_file: Path, status_file: Path):
        self.data_file = data_file
        self.status_file = status_file
        self.formatter = BMSDataFormatter(show_raw_data=False, show_all_cells=False)
    
    def read_latest_data(self) -> Optional[Dict[str, Any]]:
        """Read latest BMS data from cache file"""
        try:
            if not self.data_file.exists():
                return None
            
            # Check file age
            file_age = time.time() - self.data_file.stat().st_mtime
            if file_age > MAX_DATA_AGE_SECONDS:
                logger.warning(f"Data file is {file_age:.1f}s old (max: {MAX_DATA_AGE_SECONDS}s)")
            
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read data file: {e}")
            return None
    
    def read_service_status(self) -> Optional[Dict[str, Any]]:
        """Read service status from status file"""
        try:
            if not self.status_file.exists():
                return None
            
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read status file: {e}")
            return None
    
    def get_data_freshness(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate data freshness information"""
        current_time = int(time.time() * 1000)
        data_timestamp = data.get('timestamp', 0)
        
        age_ms = current_time - data_timestamp
        age_seconds = age_ms / 1000
        
        if age_seconds < 10:
            freshness = "fresh"
        elif age_seconds < 30:
            freshness = "recent"
        elif age_seconds < 60:
            freshness = "stale"
        else:
            freshness = "old"
        
        return {
            "age_seconds": round(age_seconds, 1),
            "age_ms": age_ms,
            "freshness": freshness,
            "is_fresh": age_seconds < MAX_DATA_AGE_SECONDS,
            "current_time": current_time
        }

# Global API service instance
api_service = BMSAPIService(DATA_FILE_PATH, STATUS_FILE_PATH)

@app.route('/')
def index():
    """API root endpoint"""
    return jsonify({
        "name": "BMS API Service",
        "version": "1.0",
        "description": "REST API for Daly BMS data from Raspberry Pi",
        "endpoints": {
            "/": "This help page",
            "/health": "Service health check",
            "/status": "Service status information",
            "/bms": "Latest BMS data (JSON)",
            "/bms/raw": "Raw BMS data with all details",
            "/bms/formatted": "Human-readable formatted data",
            "/bms/summary": "Key BMS metrics only",
            "/bms/cells": "Cell voltage information",
            "/bms/temps": "Temperature information"
        },
        "usage": {
            "fast_polling": "Use /bms/summary for frequent updates",
            "full_data": "Use /bms for complete information",
            "monitoring": "Use /health for service monitoring"
        }
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    data = api_service.read_latest_data()
    status = api_service.read_service_status()
    
    current_time = time.time()
    
    health_info = {
        "status": "healthy",
        "timestamp": int(current_time * 1000),
        "uptime": "unknown",
        "data_available": data is not None,
        "service_running": status is not None
    }
    
    if status:
        start_time = status.get('start_time', current_time)
        health_info["uptime"] = round(current_time - start_time, 1)
        health_info["service_status"] = status.get('status', 'unknown')
    
    if data:
        freshness = api_service.get_data_freshness(data)
        health_info["data_age"] = freshness["age_seconds"]
        health_info["data_fresh"] = freshness["is_fresh"]
        health_info["last_reading"] = data.get('timestamp', 0)
    
    # Determine overall health
    if not data:
        health_info["status"] = "unhealthy"
        health_info["issue"] = "No data available"
    elif not data.get('data_found', False):
        health_info["status"] = "degraded" 
        health_info["issue"] = "BMS not responding"
    elif not api_service.get_data_freshness(data)["is_fresh"]:
        health_info["status"] = "degraded"
        health_info["issue"] = "Data is stale"
    
    status_code = 200 if health_info["status"] == "healthy" else 503
    return jsonify(health_info), status_code

@app.route('/status')
def service_status():
    """Service status endpoint"""
    data = api_service.read_latest_data()
    status = api_service.read_service_status()
    
    response = {
        "api_service": {
            "status": "running",
            "data_file": str(api_service.data_file),
            "status_file": str(api_service.status_file),
            "max_data_age": MAX_DATA_AGE_SECONDS
        }
    }
    
    if status:
        response["background_service"] = status
    
    if data:
        freshness = api_service.get_data_freshness(data)
        response["data_info"] = freshness
        response["bms_connected"] = data.get('data_found', False)
        
        if data.get('data_found', False):
            parsed = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
            response["last_reading"] = {
                "pack_voltage": parsed.get('packVoltage', 0),
                "soc": parsed.get('soc', 0),
                "current": parsed.get('current', 0),
                "cell_count": len(parsed.get('cellVoltages', [])),
                "temp_sensors": len(parsed.get('temperatures', []))
            }
    
    return jsonify(response)

@app.route('/bms')
def get_bms_data():
    """Get latest BMS data (standard endpoint)"""
    data = api_service.read_latest_data()
    
    if not data:
        return jsonify({
            "error": "No BMS data available",
            "message": "Background service may not be running",
            "timestamp": int(time.time() * 1000)
        }), 404
    
    # Add freshness information
    freshness = api_service.get_data_freshness(data)
    data["freshness"] = freshness
    
    return jsonify(data)

@app.route('/bms/raw')
def get_bms_raw():
    """Get raw BMS data with all protocol details"""
    data = api_service.read_latest_data()
    
    if not data:
        return jsonify({"error": "No BMS data available"}), 404
    
    # Add extra metadata for raw endpoint
    data["api_info"] = {
        "endpoint": "/bms/raw",
        "retrieved_at": int(time.time() * 1000),
        "data_file": str(api_service.data_file)
    }
    
    freshness = api_service.get_data_freshness(data)
    data["freshness"] = freshness
    
    return jsonify(data)

@app.route('/bms/summary')
def get_bms_summary():
    """Get comprehensive BMS data in summary format (fast endpoint)"""
    data = api_service.read_latest_data()
    
    if not data:
        return jsonify({"error": "No BMS data available"}), 404
    
    # Log the complete BMS_DATA JSON as requested
    bms_data_json = json.dumps(data, separators=(',', ':'))
    logger.info(f"BMS_DATA:{bms_data_json}")
    
    if not data.get('data_found', False):
        return jsonify({
            "connected": False,
            "error": data.get('error', 'BMS not responding'),
            "timestamp": data.get('timestamp', 0),
            "device": data.get('device', 'Unknown'),
            "mac_address": data.get('mac_address', 'Unknown')
        })
    
    # Extract comprehensive data
    daly_protocol = data.get('daly_protocol', {})
    commands = daly_protocol.get('commands', {})
    main_info = commands.get('main_info', {})
    parsed = main_info.get('parsed_data', {})
    
    # Build comprehensive summary with all information
    summary = {
        # Basic connection info
        "connected": True,
        "timestamp": data.get('timestamp', 0),
        "device": data.get('device', 'Unknown'),
        "mac_address": data.get('mac_address', 'Unknown'),
        
        # Protocol information
        "protocol_status": daly_protocol.get('status', 'unknown'),
        "notifications_enabled": daly_protocol.get('notifications', 'unknown'),
        "command_sent": main_info.get('command_sent', ''),
        "response_received": main_info.get('response_received', False),
        "response_data_length": len(main_info.get('response_data', '')),
        
        # Header information
        "header": parsed.get('header', {}),
        
        # Core battery metrics
        "pack_voltage": parsed.get('packVoltage', 0),
        "current": parsed.get('current', 0),
        "power": parsed.get('packVoltage', 0) * parsed.get('current', 0),
        "soc": parsed.get('soc', 0),
        "remaining_capacity": parsed.get('remainingCapacity', 0),
        "total_capacity": parsed.get('totalCapacity', 0),
        "cycles": parsed.get('cycles', 0),
        
        # Cell information
        "cell_count": len(parsed.get('cellVoltages', [])),
        "cell_voltages": parsed.get('cellVoltages', []),
        
        # Temperature information
        "temp_count": len(parsed.get('temperatures', [])),
        "temperatures": parsed.get('temperatures', []),
        
        # MOS status
        "mos_status": parsed.get('mosStatus', {}),
        "charging_mos": parsed.get('mosStatus', {}).get('chargingMos', False),
        "discharging_mos": parsed.get('mosStatus', {}).get('dischargingMos', False),
        "balancing": parsed.get('mosStatus', {}).get('balancing', False),
        
        # Checksum
        "checksum": parsed.get('checksum', ''),
        
        # Calculated statistics
        "cell_statistics": {},
        "temperature_statistics": {},
        "battery_health": {},
        "system_status": {}
    }
    
    # Calculate cell voltage statistics
    cell_voltages = parsed.get('cellVoltages', [])
    if cell_voltages:
        voltages = [cell['voltage'] for cell in cell_voltages]
        summary["cell_statistics"] = {
            "min_voltage": min(voltages),
            "max_voltage": max(voltages),
            "avg_voltage": sum(voltages) / len(voltages),
            "voltage_diff": max(voltages) - min(voltages),
            "balance_status": "excellent" if (max(voltages) - min(voltages)) < 0.01 else
                             "good" if (max(voltages) - min(voltages)) < 0.02 else "needs_attention"
        }
    
    # Calculate temperature statistics
    temperatures = parsed.get('temperatures', [])
    if temperatures:
        temps = [t['temperature'] for t in temperatures]
        summary["temperature_statistics"] = {
            "min_temperature": min(temps),
            "max_temperature": max(temps),
            "avg_temperature": sum(temps) / len(temps),
            "temp_diff": max(temps) - min(temps) if len(temps) > 1 else 0,
            "thermal_status": "hot" if max(temps) >= 50 else
                             "warm" if max(temps) >= 40 else
                             "normal" if min(temps) > 5 else "cold"
        }
    
    # Battery health assessment
    soc = parsed.get('soc', 0)
    cycles = parsed.get('cycles', 0)
    summary["battery_health"] = {
        "soc_level": "critical" if soc < 20 else "low" if soc < 50 else "medium" if soc < 80 else "high",
        "cycle_health": "excellent" if cycles < 100 else "good" if cycles < 500 else "fair" if cycles < 1000 else "aged",
        "overall_status": "operational" if summary["charging_mos"] and summary["discharging_mos"] else "protection_mode"
    }
    
    # System status
    freshness = api_service.get_data_freshness(data)
    summary["system_status"] = {
        "data_freshness": freshness,
        "communication_quality": "excellent" if summary["response_received"] else "poor",
        "system_health": "healthy" if freshness["is_fresh"] and summary["response_received"] else "degraded"
    }
    
    return jsonify(summary)

@app.route('/bms/formatted')
def get_bms_formatted():
    """Get human-readable formatted BMS data"""
    data = api_service.read_latest_data()
    
    if not data:
        return Response("No BMS data available", status=404, mimetype='text/plain')
    
    # Convert to BMS_DATA format for formatter
    bms_line = f"BMS_DATA:{json.dumps(data, separators=(',', ':'))}"
    formatted = api_service.formatter.parse_and_format(bms_line)
    
    if not formatted:
        return Response("Failed to format BMS data", status=500, mimetype='text/plain')
    
    return Response(formatted, mimetype='text/plain')

@app.route('/bms/cells')
def get_cell_data():
    """Get cell voltage information"""
    data = api_service.read_latest_data()
    
    if not data or not data.get('data_found', False):
        return jsonify({"error": "No BMS data available"}), 404
    
    parsed = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
    cell_voltages = parsed.get('cellVoltages', [])
    
    if not cell_voltages:
        return jsonify({"error": "No cell voltage data"}), 404
    
    voltages = [cell['voltage'] for cell in cell_voltages]
    
    cell_info = {
        "timestamp": data.get('timestamp', 0),
        "cell_count": len(cell_voltages),
        "cells": cell_voltages,
        "pack_voltage": parsed.get('packVoltage', 0),
        "statistics": {
            "min_voltage": min(voltages),
            "max_voltage": max(voltages),
            "avg_voltage": sum(voltages) / len(voltages),
            "voltage_diff": max(voltages) - min(voltages),
            "balance_status": "good" if (max(voltages) - min(voltages)) < 0.02 else "needs_balancing"
        }
    }
    
    return jsonify(cell_info)

@app.route('/bms/temps')
def get_temperature_data():
    """Get temperature information"""
    data = api_service.read_latest_data()
    
    if not data or not data.get('data_found', False):
        return jsonify({"error": "No BMS data available"}), 404
    
    parsed = data.get('daly_protocol', {}).get('commands', {}).get('main_info', {}).get('parsed_data', {})
    temperatures = parsed.get('temperatures', [])
    
    temp_info = {
        "timestamp": data.get('timestamp', 0),
        "sensor_count": len(temperatures),
        "sensors": temperatures
    }
    
    if temperatures:
        temps = [t['temperature'] for t in temperatures]
        temp_info["statistics"] = {
            "min_temperature": min(temps),
            "max_temperature": max(temps),
            "avg_temperature": sum(temps) / len(temps),
            "temp_diff": max(temps) - min(temps) if len(temps) > 1 else 0
        }
    
    return jsonify(temp_info)

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found", "message": "Check / for available endpoints"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "message": str(error)}), 500

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='BMS REST API Service')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--data-file', default='/tmp/bms_latest.json', help='BMS data file path')
    parser.add_argument('--status-file', default='/tmp/bms_status.json', help='Status file path')
    
    args = parser.parse_args()
    
    # Update global paths
    global DATA_FILE_PATH, STATUS_FILE_PATH, api_service
    DATA_FILE_PATH = Path(args.data_file)
    STATUS_FILE_PATH = Path(args.status_file)
    api_service = BMSAPIService(DATA_FILE_PATH, STATUS_FILE_PATH)
    
    logger.info(f"Starting BMS API Service on {args.host}:{args.port}")
    logger.info(f"Data file: {DATA_FILE_PATH}")
    logger.info(f"Status file: {STATUS_FILE_PATH}")
    
    # Start Flask app
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        threaded=True
    )

if __name__ == '__main__':
    main()