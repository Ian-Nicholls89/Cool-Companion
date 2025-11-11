#!/bin/bash

# Color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================="
echo "  Starting Application"
echo "=================================="

echo "${YELLOW}it is recommended that this script is run on a Raspberry Pi OS full 32-bit installation for best compatibility.${NC}" 

# Check if main.py exists first
if [ ! -f "main.py" ]; then
    echo -e "${RED}ERROR: main.py not found in current directory!${NC}"
    echo "Please make sure you're running this script from the correct location."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "./venv" ]; then
    echo -e "${YELLOW}No virtual environment found. Creating one...${NC}"
    
    # Check if python3 is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}ERROR: python3 is not installed or not in PATH${NC}"
        echo "Attempting to install python3 and python3-venv..."
        sudo apt install python3 python3-venv -y
        if [ $? -ne 0 ]; then
            echo -e "${RED}ERROR: Failed to install python3 and python3-venv${NC}"
            exit 1
        fi
    fi
    
    python3 -m venv venv
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to create virtual environment${NC}"
        for num in {1..3}; do
            echo -e "${YELLOW}Further attempt ${num} of 3.${NC}"
            python3 -m venv venv
            if [ $? -eq 0 ]; then
                break
            fi
        done
        echo -e "${RED}All attempts to create virtual environment failed${NC}"
        echo -e "${RED}Please try to run \"python3 -m venv venv\" (without quotations) manually in a terminal.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Virtual environment created successfully!${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source ./venv/bin/activate

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to activate virtual environment${NC}"
    exit 1
fi

# Check if this is a fresh venv that needs dependencies installed
if [ ! -f "./venv/installed.marker" ]; then
    cp ./.env.example ./.env
    sed -i 's/ENVIRONMENT=.*/ENVIRONMENT=production/' .env
    sed -i 's/SKIP_SYSTEM_CHECKS=.*/SKIP_SYSTEM_CHECKS=False/' .env
    sed -i 's/ENABLE_SHOPPING_LIST=.*/ENABLE_SHOPPING_LIST=False/' .env


    echo -e "${YELLOW}Installing dependencies...${NC}"
    
    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip --quiet
        pip install -r requirements.txt
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}ERROR: Failed to install dependencies${NC}"
            exit 1
        fi
        
        # Create marker file so we don't reinstall every time
        touch ./venv/installed.marker
        echo -e "${GREEN}Dependencies installed successfully!${NC}"
    else
        echo -e "${YELLOW}WARNING: No requirements.txt found, skipping dependency installation${NC}"
    fi
fi

# Check if running on Raspberry Pi and set appropriate GL settings
if grep -q "Raspberry Pi" /proc/cpuinfo; then
    # on raspi make the setting in the .env file SKIP_SYSTEM_CHECKS to false and the ENVIRONMENT to production
    sed -i 's/SKIP_SYSTEM_CHECKS=.*/SKIP_SYSTEM_CHECKS=False/' .env
    sed -i 's/ENVIRONMENT=.*/ENVIRONMENT=production/' .env
    echo -e "${GREEN}Raspberry Pi detected, updated .env settings accordingly${NC}"
    
    # Set GL-related environment variables for better compatibility
    export MESA_GL_VERSION_OVERRIDE=2.1
    export LIBGL_ALWAYS_SOFTWARE=1
    export GALLIUM_DRIVER=llvmpipe
    export LIBGL_DRI3_DISABLE=1
    
    # Check if required GL packages are installed
    if ! dpkg -l | grep -q "libgl1-mesa-dri"; then
        echo -e "${YELLOW}Installing required GL packages...${NC}"
        sudo apt update && sudo apt install -y libgl1-mesa-dri libgl1-mesa-glx
    fi
fi

# Run the application
echo ""
echo -e "${GREEN}Starting application...${NC}"
echo "=================================="

# Enhanced display server detection and handling
if [ "$XDG_SESSION_TYPE" = "x11" ]; then
    export SDL_VIDEODRIVER=x11
elif [ "$XDG_SESSION_TYPE" = "tty" ]; then
    echo -e "${YELLOW}Warning: Running from TTY. Checking for display server...${NC}"
    if [ -z "$DISPLAY" ]; then
        echo -e "${YELLOW}No display server detected. Attempting to start X11...${NC}"
        if command -v startx &> /dev/null; then
            startx /usr/bin/openbox -- &
            if [ $? -eq 0 ]; then
                for i in {10..1}; do
                    echo -ne "\r${YELLOW}Starting X server in $i seconds...${NC}"
                    sleep 1
                done
                echo -e "\n"
                export SDL_VIDEODRIVER=x11
                export DISPLAY=:0
            else
                echo -e "${RED}Failed to start X server.${NC}"
            fi
        else
            echo -e "${RED}X server not available.${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Unknown session type. Setting fallback options...${NC}"
    export SDL_VIDEODRIVER=x11
fi

# Try different GL configurations if the app fails
(python3 main.py) || {
    echo -e "${YELLOW}First attempt failed. Trying with minimal GL...${NC}"
    (python3 main.py) || {
        echo -e "${YELLOW}Second attempt failed. Trying with minimal GL...${NC}"
        export MESA_GL_VERSION_OVERRIDE=2.1
        export LIBGL_ALWAYS_SOFTWARE=1
        python3 main.py
    }
}

# Capture exit code
EXIT_CODE=$?

echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Application exited successfully${NC}"
else
    echo -e "${RED}Application exited with error code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE