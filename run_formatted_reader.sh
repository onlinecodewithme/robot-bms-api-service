#!/bin/bash
# Enhanced BMS reader with automatic formatting
# Pipes the BMS reader output through the formatter for human-readable display

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default options
SHOW_RAW=""
SHOW_ALL_CELLS=""
MODE="continuous"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--raw)
            SHOW_RAW="--show-raw"
            shift
            ;;
        -c|--all-cells)
            SHOW_ALL_CELLS="--show-all-cells"
            shift
            ;;
        -i|--interactive)
            MODE="interactive"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -i, --interactive    Start interactive mode instead of continuous"
            echo "  -r, --raw           Show raw protocol information"
            echo "  -c, --all-cells     Show all cell voltages (not just sample)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Continuous reading with formatted output"
            echo "  $0 -c               # Show all cell voltages"  
            echo "  $0 -r               # Include raw protocol data"
            echo "  $0 -i               # Interactive mode"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

if [[ "$MODE" == "interactive" ]]; then
    echo "🎛️  Starting Interactive BMS Reader with formatting..."
    echo "Note: Use 'data' or 'continuous' commands for formatted output"
    echo "=================================================================================="
    ./venv/bin/python interactive_bms_reader.py
else
    echo "🔋 Starting Formatted BMS Reader..."
    echo "Press Ctrl+C to stop"
    echo "=================================================================================="
    echo ""
    
    # Start the BMS reader and pipe through formatter
    ./venv/bin/python daly_bms_reader.py | ./venv/bin/python bms_data_formatter.py --continuous $SHOW_RAW $SHOW_ALL_CELLS
fi