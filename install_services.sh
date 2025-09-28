#!/bin/bash
# Install BMS API Services for automatic startup
# This script installs both the background data collector and REST API services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_HOME="$(eval echo ~$SUDO_USER)"
SERVICE_USER="${SUDO_USER:-pi}"

echo "=== BMS API Services Installation ==="
echo "Installing services for user: $SERVICE_USER"
echo "Home directory: $USER_HOME"
echo "Script directory: $SCRIPT_DIR"
echo "====================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   echo "Usage: sudo ./install_services.sh"
   exit 1
fi

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "❌ Virtual environment not found. Run install.sh first."
    exit 1
fi

# Check if Flask is installed
if ! $SCRIPT_DIR/venv/bin/python -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask..."
    $SCRIPT_DIR/venv/bin/pip install flask>=2.3.0
fi

# Update service files with correct paths
echo "🔧 Configuring service files..."

# Update systemd service files with actual paths
sed -i "s|/home/pi/raspberry_pi_bms_reader|$SCRIPT_DIR|g" "$SCRIPT_DIR/systemd/bms-background.service"
sed -i "s|User=pi|User=$SERVICE_USER|g" "$SCRIPT_DIR/systemd/bms-background.service"
sed -i "s|Group=pi|Group=$SERVICE_USER|g" "$SCRIPT_DIR/systemd/bms-background.service"

sed -i "s|/home/pi/raspberry_pi_bms_reader|$SCRIPT_DIR|g" "$SCRIPT_DIR/systemd/bms-api.service"
sed -i "s|User=pi|User=$SERVICE_USER|g" "$SCRIPT_DIR/systemd/bms-api.service"
sed -i "s|Group=pi|Group=$SERVICE_USER|g" "$SCRIPT_DIR/systemd/bms-api.service"

# Create log directory
echo "📁 Creating log directory..."
mkdir -p /var/log/bms
chown $SERVICE_USER:$SERVICE_USER /var/log/bms

# Install systemd service files
echo "🔧 Installing systemd services..."
cp "$SCRIPT_DIR/systemd/bms-background.service" /etc/systemd/system/
cp "$SCRIPT_DIR/systemd/bms-api.service" /etc/systemd/system/

# Set permissions
chmod 644 /etc/systemd/system/bms-background.service
chmod 644 /etc/systemd/system/bms-api.service

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable services
echo "✅ Enabling services..."
systemctl enable bms-background.service
systemctl enable bms-api.service

# Start services
echo "🚀 Starting services..."
systemctl start bms-background.service
sleep 3
systemctl start bms-api.service

# Wait a moment for services to start
sleep 5

# Check service status
echo ""
echo "=== Service Status ==="
echo "Background Service:"
systemctl --no-pager -l status bms-background.service

echo ""
echo "API Service:" 
systemctl --no-pager -l status bms-api.service

echo ""
echo "=== Testing API ==="
echo "Waiting for services to initialize..."
sleep 10

# Test API endpoints
if command -v curl >/dev/null 2>&1; then
    echo "Testing API endpoints:"
    echo ""
    
    # Test health endpoint
    echo "🔍 Health Check:"
    curl -s http://localhost:5000/health | python3 -m json.tool || echo "Health endpoint not ready yet"
    
    echo ""
    echo "📊 Status Check:" 
    curl -s http://localhost:5000/status | python3 -m json.tool || echo "Status endpoint not ready yet"
    
    echo ""
    echo "🔋 BMS Summary:"
    curl -s http://localhost:5000/bms/summary | python3 -m json.tool || echo "BMS data not ready yet"
else
    echo "curl not available - install with: sudo apt install curl"
fi

echo ""
echo "=== Installation Complete ==="
echo "✅ Services installed and started successfully!"
echo ""
echo "📡 API Endpoints:"
echo "   http://localhost:5000/         - API documentation"
echo "   http://localhost:5000/health   - Health check"
echo "   http://localhost:5000/status   - Service status"
echo "   http://localhost:5000/bms      - Full BMS data"
echo "   http://localhost:5000/bms/summary - Key metrics only"
echo ""
echo "🛠️  Service Management:"
echo "   sudo systemctl status bms-background    - Check background service"
echo "   sudo systemctl status bms-api           - Check API service"
echo "   sudo systemctl restart bms-background   - Restart data collector"
echo "   sudo systemctl restart bms-api          - Restart API server"
echo "   sudo systemctl stop bms-background      - Stop background service"
echo "   sudo systemctl stop bms-api             - Stop API service"
echo ""
echo "📊 View Logs:"
echo "   sudo journalctl -u bms-background -f   - Follow background logs"
echo "   sudo journalctl -u bms-api -f          - Follow API logs"
echo ""
echo "📁 Data Files:"
echo "   /tmp/bms_latest.json - Latest BMS data"
echo "   /tmp/bms_status.json - Service status"
echo ""
echo "🌐 Access API from other devices:"
echo "   http://$(hostname -I | awk '{print $1}'):5000/"
echo ""
echo "🔧 The services will automatically start on boot"
echo "=============================="