#!/bin/bash

# First try to list all available displays
displays=$(DISPLAY=:0 xrandr --query 2>/dev/null)
if [ $? -eq 0 ]; then
    export DISPLAY=:0
    exit 0
fi

# Try other common display numbers
for display in 1 2 3; do
    if DISPLAY=:$display xrandr --query >/dev/null 2>&1; then
        export DISPLAY=:$display
        exit 0
    fi
done

# Check for non-standard displays
for tty in $(ls /dev/tty*); do
    if DISPLAY=:0.$tty xrandr --query >/dev/null 2>&1; then
        export DISPLAY=:0.$tty
        exit 0
    fi
done

# If no display found, default to :0
export DISPLAY=:0
exit 1
