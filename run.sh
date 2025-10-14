#!/bin/bash

# Color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================="
echo "  Starting Application"
echo "=================================="

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
        exit 1
    fi
    
    python3 -m venv venv
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}ERROR: Failed to create virtual environment${NC}"
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

# Run the application
echo ""
echo -e "${GREEN}Starting application...${NC}"
echo "=================================="
python main.py

# Capture exit code
EXIT_CODE=$?

echo "=================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Application exited successfully${NC}"
else
    echo -e "${RED}Application exited with error code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE