# Auto-Start Service Setup

Cool Companion can be configured to start automatically when your Raspberry Pi boots up using systemd.

## Quick Setup

When you run `./run.sh` on a Raspberry Pi, you'll be prompted to install the auto-start service. Simply answer "y" when asked:

```
Would you like Cool Companion to start automatically on boot? (y/n): y
```

## Manual Service Management

Use the included `service-manager.sh` script to manage the auto-start service:

### Install Service
```bash
./service-manager.sh install
```

### Check Status
```bash
./service-manager.sh status
```

### Start/Stop/Restart
```bash
./service-manager.sh start
./service-manager.sh stop
./service-manager.sh restart
```

### Enable/Disable Auto-Start
```bash
./service-manager.sh enable   # Start on boot
./service-manager.sh disable  # Don't start on boot
```

### View Live Logs
```bash
./service-manager.sh logs     # Press Ctrl+C to exit
```

### Uninstall Service
```bash
./service-manager.sh uninstall
```

## Direct systemd Commands

You can also use systemd commands directly:

```bash
# Start the service now
sudo systemctl start cool-companion

# Stop the service
sudo systemctl stop cool-companion

# Restart the service
sudo systemctl restart cool-companion

# Check service status
sudo systemctl status cool-companion

# Enable auto-start on boot
sudo systemctl enable cool-companion

# Disable auto-start
sudo systemctl disable cool-companion

# View logs (live)
journalctl -u cool-companion -f

# View last 50 log lines
journalctl -u cool-companion -n 50
```

## Service Configuration

The service is configured to:
- ✅ Start after the graphical environment is ready
- ✅ Automatically restart if it crashes
- ✅ Run with your user permissions (not root)
- ✅ Use the correct display server (`:0`)
- ✅ Wait 10 seconds before restarting after a failure

## Troubleshooting

### Service won't start
Check the logs for errors:
```bash
journalctl -u cool-companion -n 100
```

### Application crashes on boot
The service will automatically restart up to the systemd limit. Check logs to identify the issue.

### Display not working
Make sure you're logged into the graphical session when the service starts. The service expects `DISPLAY=:0`.

### Disable auto-start temporarily
```bash
sudo systemctl stop cool-companion
sudo systemctl disable cool-companion
```

### Permission issues
The service runs as your user (not root), so ensure:
- Your user has access to the camera
- Database file has correct permissions
- `.env` file is readable

## Service File Location

The systemd service is installed at:
```
/etc/systemd/system/cool-companion.service
```

To manually edit:
```bash
sudo nano /etc/systemd/system/cool-companion.service
sudo systemctl daemon-reload
sudo systemctl restart cool-companion
```

## Logs

Application logs are written to two places:

1. **Application log files**: `logs/cool-companion_*.log` (rotated daily)
2. **systemd journal**: View with `journalctl -u cool-companion`

For troubleshooting, check both locations.
