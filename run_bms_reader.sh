#!/bin/bash
# Simple wrapper script to run the BMS reader with virtual environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ "$1" = "interactive" ] || [ "$1" = "i" ]; then
    echo "Starting interactive BMS reader..."
    ./venv/bin/python interactive_bms_reader.py
else
    echo "Starting continuous BMS reader..."
    echo "Press Ctrl+C to stop"
    ./venv/bin/python daly_bms_reader.py
fi