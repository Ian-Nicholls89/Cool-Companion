#!/bin/bash

# Color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=================================="
echo "  Cool Companion - Starting"
echo "=================================="

echo -e "${BLUE}Optimized for Raspberry Pi OS (32-bit/64-bit)${NC}"

# Check if main.py exists first
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: main.py not found in current directory!${NC}"
    echo "Please make sure you're running this script from the correct location."
    exit 1
fi

# Check if git is available (required for auto-updates)
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}Git is not installed${NC}"
    echo -e "${BLUE}Git is required for automatic updates${NC}"
    echo "Attempting to install git..."

    if sudo apt update && sudo apt install -y git; then
        echo -e "${GREEN}✓ Git installed successfully${NC}"
    else
        echo -e "${RED}WARNING: Failed to install git${NC}"
        echo -e "${YELLOW}Auto-update feature will not work${NC}"
        echo -e "${YELLOW}You can manually install git with: sudo apt install git${NC}"
    fi
else
    echo -e "${GREEN}✓ Git found: $(git --version)${NC}"
fi

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: python3 is not installed or not in PATH${NC}"
    echo "Attempting to install python3..."
    sudo apt update && sudo apt install -y python3 python3-pip
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to install python3${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Python3 installed successfully${NC}"
else
    echo -e "${GREEN}✓ Python3 found: $(python3 --version)${NC}"
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
    echo -e "${YELLOW}pip not found, installing...${NC}"
    sudo apt update && sudo apt install -y python3-pip

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ pip installed successfully${NC}"
    fi
else
    echo -e "${GREEN}✓ pip found${NC}"
fi

# Create .env file on first run if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Creating .env file from template...${NC}"
        cp .env.example .env

        # Configure for production on Raspberry Pi
        if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
            sed -i 's/ENVIRONMENT=.*/ENVIRONMENT=production/' .env
            sed -i 's/SKIP_SYSTEM_CHECKS=.*/SKIP_SYSTEM_CHECKS=false/' .env
            sed -i 's/ENABLE_SHOPPING_LIST=.*/ENABLE_SHOPPING_LIST=false/' .env
            echo -e "${GREEN}Configured .env for Raspberry Pi${NC}"
        fi
    else
        echo -e "${RED}WARNING: No .env.example found. Please create .env manually.${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Check if dependencies need to be installed
MARKER_FILE=".dependencies_installed"

if [ ! -f "$MARKER_FILE" ]; then
    echo -e "${YELLOW}Checking dependencies...${NC}"

    if [ -f "requirements.txt" ]; then
        echo -e "${BLUE}Installing Python dependencies globally...${NC}"
        echo -e "${YELLOW}This may take some time.${NC}"

        # Try to install system-wide (requires sudo on some systems)
        if python3 -m pip install --upgrade pip --quiet --break-system-packages 2>/dev/null; then
            # Pip upgrade succeeded, now install requirements
            if python3 -m pip install -r requirements.txt --quiet --break-system-packages; then
                echo -e "${GREEN}✓ Dependencies installed successfully (system-wide)${NC}"
                touch "$MARKER_FILE"
            else
                echo -e "${YELLOW}System-wide install failed, trying user-level install...${NC}"

                # Fallback to user-level install
                if python3 -m pip install --user --upgrade pip --quiet && \
                   python3 -m pip install --user -r requirements.txt --quiet; then
                    echo -e "${GREEN}✓ Dependencies installed successfully (user-level)${NC}"
                    touch "$MARKER_FILE"
                else
                    echo -e "${RED}ERROR: Failed to install dependencies${NC}"
                    echo -e "${YELLOW}Trying with sudo (may require password)...${NC}"

                    # Last resort: use sudo
                    if sudo python3 -m pip install -r requirements.txt --break-system-packages; then
                        echo -e "${GREEN}✓ Dependencies installed successfully (with sudo)${NC}"
                        touch "$MARKER_FILE"
                    else
                        echo -e "${RED}ERROR: All installation attempts failed${NC}"
                        echo -e "${YELLOW}Please manually install: sudo pip3 install -r requirements.txt${NC}"
                        exit 1
                    fi
                fi
            fi
        else
            echo -e "${YELLOW}Cannot upgrade pip, trying installation anyway...${NC}"
            python3 -m pip install -r requirements.txt --break-system-packages --quiet

            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✓ Dependencies installed${NC}"
                touch "$MARKER_FILE"
            else
                echo -e "${RED}ERROR: Failed to install dependencies${NC}"
                exit 1
            fi
        fi
    else
        echo -e "${RED}ERROR: requirements.txt not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Raspberry Pi specific optimizations
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${GREEN}✓ Raspberry Pi detected${NC}"

    # Update .env settings for Raspberry Pi if needed
    if [ -f ".env" ]; then
        sed -i 's/SKIP_SYSTEM_CHECKS=.*/SKIP_SYSTEM_CHECKS=false/' .env 2>/dev/null
        sed -i 's/ENVIRONMENT=.*/ENVIRONMENT=production/' .env 2>/dev/null
    fi

    # Offer to install systemd service for auto-start on boot
    SERVICE_FILE="/etc/systemd/system/cool-companion.service"
    if [ ! -f "$SERVICE_FILE" ]; then
        echo ""
        echo -e "${BLUE}═══════════════════════════════════════════${NC}"
        echo -e "${BLUE}   Auto-Start on Boot Setup${NC}"
        echo -e "${BLUE}═══════════════════════════════════════════${NC}"
        echo -e "${YELLOW}Would you like Cool Companion to start automatically on boot?${NC}"
        echo -e "This will create a systemd service that runs the application"
        echo -e "when your Raspberry Pi starts up."
        echo ""
        read -p "Enable auto-start? (y/n): " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Installing systemd service...${NC}"

            # Get the current user and working directory
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
                # Reload systemd daemon
                sudo systemctl daemon-reload

                # Enable the service
                sudo systemctl enable cool-companion.service

                if [ $? -eq 0 ]; then
                    echo -e "${GREEN}✓ Auto-start service installed successfully!${NC}"
                    echo ""
                    echo -e "${BLUE}Service management commands:${NC}"
                    echo -e "  Start now:     ${YELLOW}sudo systemctl start cool-companion${NC}"
                    echo -e "  Stop:          ${YELLOW}sudo systemctl stop cool-companion${NC}"
                    echo -e "  Restart:       ${YELLOW}sudo systemctl restart cool-companion${NC}"
                    echo -e "  View status:   ${YELLOW}sudo systemctl status cool-companion${NC}"
                    echo -e "  View logs:     ${YELLOW}journalctl -u cool-companion -f${NC}"
                    echo -e "  Disable:       ${YELLOW}sudo systemctl disable cool-companion${NC}"
                    echo ""
                    echo -e "${GREEN}The application will start automatically on next boot.${NC}"
                else
                    echo -e "${RED}✗ Failed to enable service${NC}"
                fi
            else
                echo -e "${RED}✗ Failed to create service file${NC}"
            fi
        else
            echo -e "${YELLOW}Skipping auto-start setup${NC}"
            echo -e "You can run this script again to enable it later."
        fi
    else
        echo -e "${GREEN}✓ Auto-start service already installed${NC}"
    fi

    # Set GL-related environment variables for better compatibility
    export MESA_GL_VERSION_OVERRIDE=2.1
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export LIBGL_DRI3_DISABLE=1

    # Check if required GL packages are installed
    if ! dpkg -l | grep -q "libgl1-mesa-dri" 2>/dev/null; then
        echo -e "${YELLOW}Installing required GL packages...${NC}"
        sudo apt update && sudo apt install -y libgl1-mesa-dri libgl1-mesa-glx libglib2.0-0
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ GL packages installed${NC}"
        fi
    fi

    # Check for Qt/PySide6 system dependencies
    if ! dpkg -l | grep -q "libxcb-xinerama0" 2>/dev/null; then
        echo -e "${YELLOW}Installing Qt dependencies...${NC}"
        sudo apt install -y libxcb-xinerama0 libxcb-cursor0 libxkbcommon-x11-0
    fi
fi

# Enhanced display server detection and handling
echo ""
echo -e "${BLUE}Checking display environment...${NC}"

if [ "$XDG_SESSION_TYPE" = "x11" ]; then
    echo -e "${GREEN}✓ Running under X11${NC}"
    export SDL_VIDEODRIVER=x11
elif [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo -e "${GREEN}✓ Running under Wayland${NC}"
    export QT_QPA_PLATFORM=wayland
elif [ "$XDG_SESSION_TYPE" = "tty" ]; then
    echo -e "${YELLOW}Warning: Running from TTY${NC}"

    if [ -z "$DISPLAY" ]; then
        echo -e "${YELLOW}No display server detected${NC}"
        echo -e "${RED}Please run this from a desktop environment (X11/Wayland)${NC}"
        exit 1
    fi
else
    if [ -n "$DISPLAY" ]; then
        echo -e "${GREEN}✓ DISPLAY set: $DISPLAY${NC}"
        export SDL_VIDEODRIVER=x11
    else
        echo -e "${YELLOW}Warning: Unknown session type, trying anyway...${NC}"
    fi
fi

# Run the application
echo ""
echo "=================================="
echo -e "${GREEN}Starting Cool Companion...${NC}"
echo "=================================="
echo ""

# Try different GL configurations if the app fails
python3 main.py || {
    echo -e "${YELLOW}First attempt failed, trying with minimal GL...${NC}"
    export MESA_GL_VERSION_OVERRIDE=2.1
    export LIBGL_ALWAYS_SOFTWARE=1
    python3 main.py || {
        echo -e "${YELLOW}Second attempt failed, trying with software rendering...${NC}"
        export QT_XCB_GL_INTEGRATION=none
        python3 main.py
    }
}

# Capture exit code
EXIT_CODE=$?

echo ""
echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Application exited successfully${NC}"
else
    echo -e "${RED}✗ Application exited with error code: $EXIT_CODE${NC}"
    echo -e "${YELLOW}Check logs/ directory for error details${NC}"
fi
echo "=================================="

exit $EXIT_CODE
