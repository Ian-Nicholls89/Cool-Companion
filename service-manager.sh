#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SERVICE_NAME="cool-companion"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=================================="
echo "  Cool Companion Service Manager"
echo "=================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}This script is designed for Raspberry Pi${NC}"
    echo "Service management may not work on other systems."
    echo ""
fi

# Function to check if service exists
service_exists() {
    [ -f "$SERVICE_FILE" ]
}

# Function to install service
install_service() {
    if service_exists; then
        echo -e "${YELLOW}Service is already installed${NC}"
        return 1
    fi

    echo -e "${BLUE}Installing systemd service...${NC}"

    CURRENT_USER=$(whoami)
    APP_DIR=$(pwd)

    # Create systemd service file
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Cool Companion - Fridge Inventory Application
After=graphical.target network-online.target
Wants=graphical.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$APP_DIR
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/$CURRENT_USER/.Xauthority"
ExecStart=/usr/bin/python3 $APP_DIR/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

    if [ $? -eq 0 ]; then
        sudo systemctl daemon-reload
        sudo systemctl enable $SERVICE_NAME.service
        echo -e "${GREEN}✓ Service installed and enabled${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to install service${NC}"
        return 1
    fi
}

# Function to uninstall service
uninstall_service() {
    if ! service_exists; then
        echo -e "${YELLOW}Service is not installed${NC}"
        return 1
    fi

    echo -e "${BLUE}Uninstalling service...${NC}"

    # Stop service if running
    sudo systemctl stop $SERVICE_NAME.service 2>/dev/null

    # Disable service
    sudo systemctl disable $SERVICE_NAME.service 2>/dev/null

    # Remove service file
    sudo rm -f "$SERVICE_FILE"

    # Reload daemon
    sudo systemctl daemon-reload

    echo -e "${GREEN}✓ Service uninstalled${NC}"
    return 0
}

# Function to show service status
show_status() {
    if ! service_exists; then
        echo -e "${RED}Service is not installed${NC}"
        echo ""
        echo -e "Run: ${YELLOW}$0 install${NC} to install the service"
        return 1
    fi

    echo -e "${BLUE}Service Status:${NC}"
    sudo systemctl status $SERVICE_NAME.service --no-pager
}

# Function to show logs
show_logs() {
    if ! service_exists; then
        echo -e "${RED}Service is not installed${NC}"
        return 1
    fi

    echo -e "${BLUE}Recent logs (Ctrl+C to exit):${NC}"
    journalctl -u $SERVICE_NAME.service -f
}

# Function to show menu
show_menu() {
    echo -e "${CYAN}Available Commands:${NC}"
    echo ""
    echo -e "  ${YELLOW}install${NC}     - Install auto-start service"
    echo -e "  ${YELLOW}uninstall${NC}   - Remove auto-start service"
    echo -e "  ${YELLOW}start${NC}       - Start the service now"
    echo -e "  ${YELLOW}stop${NC}        - Stop the service"
    echo -e "  ${YELLOW}restart${NC}     - Restart the service"
    echo -e "  ${YELLOW}status${NC}      - Show service status"
    echo -e "  ${YELLOW}enable${NC}      - Enable auto-start on boot"
    echo -e "  ${YELLOW}disable${NC}     - Disable auto-start on boot"
    echo -e "  ${YELLOW}logs${NC}        - View service logs (live)"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  $0 install"
    echo -e "  $0 status"
    echo -e "  $0 restart"
}

# Main script logic
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        if service_exists; then
            sudo systemctl start $SERVICE_NAME.service
            echo -e "${GREEN}✓ Service started${NC}"
        else
            echo -e "${RED}Service not installed${NC}"
            exit 1
        fi
        ;;
    stop)
        if service_exists; then
            sudo systemctl stop $SERVICE_NAME.service
            echo -e "${GREEN}✓ Service stopped${NC}"
        else
            echo -e "${RED}Service not installed${NC}"
            exit 1
        fi
        ;;
    restart)
        if service_exists; then
            sudo systemctl restart $SERVICE_NAME.service
            echo -e "${GREEN}✓ Service restarted${NC}"
        else
            echo -e "${RED}Service not installed${NC}"
            exit 1
        fi
        ;;
    status)
        show_status
        ;;
    enable)
        if service_exists; then
            sudo systemctl enable $SERVICE_NAME.service
            echo -e "${GREEN}✓ Auto-start enabled${NC}"
        else
            echo -e "${RED}Service not installed${NC}"
            exit 1
        fi
        ;;
    disable)
        if service_exists; then
            sudo systemctl disable $SERVICE_NAME.service
            echo -e "${GREEN}✓ Auto-start disabled${NC}"
        else
            echo -e "${RED}Service not installed${NC}"
            exit 1
        fi
        ;;
    logs)
        show_logs
        ;;
    *)
        show_menu
        exit 0
        ;;
esac
