#!/bin/bash
# Installation script for Raspberry Pi Daly BMS Reader
# This script sets up the environment and installs dependencies

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=== Raspberry Pi Daly BMS Reader Installation ==="
echo "This script will install the BMS reader and its dependencies"
echo "=================================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "The installation will continue on standard Linux system."
fi

# Check for Python 3.8+
python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    echo "❌ Python 3.8+ is required. Found Python $python_version"
    echo "Please update your Python installation"
    exit 1
fi
echo "✅ Python $python_version detected"

# Update system packages
echo "📦 Updating system packages..."
sudo apt update

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    bluetooth \
    bluez \
    libbluetooth-dev \
    pkg-config \
    libglib2.0-dev

# Enable and start Bluetooth service
echo "🔵 Configuring Bluetooth service..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# Check Bluetooth status
if ! systemctl is-active --quiet bluetooth; then
    echo "❌ Bluetooth service is not running"
    echo "Please check your Bluetooth configuration"
    exit 1
fi
echo "✅ Bluetooth service is running"

# Add user to bluetooth group
echo "👤 Adding user to bluetooth group..."
sudo usermod -a -G bluetooth $USER

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel --index-url https://pypi.org/simple

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --index-url https://pypi.org/simple

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x daly_bms_reader.py
chmod +x interactive_bms_reader.py

# Create symlinks for easy access
echo "🔗 Creating command shortcuts..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/daly-bms-reader << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
source venv/bin/activate
python3 daly_bms_reader.py "\$@"
EOF

cat > ~/.local/bin/daly-bms-interactive << EOF
#!/bin/bash
cd "${SCRIPT_DIR}"
source venv/bin/activate
python3 interactive_bms_reader.py "\$@"
EOF

chmod +x ~/.local/bin/daly-bms-reader
chmod +x ~/.local/bin/daly-bms-interactive

# Add ~/.local/bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "🛤️  Adding ~/.local/bin to PATH..."
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
fi

echo ""
echo "✅ Installation completed successfully!"
echo ""
echo "=== Next Steps ==="
echo "1. Log out and log back in (or run 'newgrp bluetooth')"
echo "2. Make sure your BMS is powered and in range"
echo "3. Run the interactive version:"
echo "   ./interactive_bms_reader.py"
echo "   or: daly-bms-interactive"
echo ""
echo "4. Or run the continuous version:"
echo "   ./daly_bms_reader.py"
echo "   or: daly-bms-reader"
echo ""
echo "=== Troubleshooting ==="
echo "• If Bluetooth doesn't work, try: sudo systemctl restart bluetooth"
echo "• If permission denied, run: newgrp bluetooth"
echo "• Check BMS MAC address in the code matches your device"
echo "• Use 'hcitool lescan' to verify BLE scanning works"
echo "=================="

echo ""
echo "🎉 Ready to read BMS data!"