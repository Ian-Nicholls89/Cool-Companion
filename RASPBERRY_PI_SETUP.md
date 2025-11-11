# Raspberry Pi Setup Guide for Cool Companion

This guide will help you set up and optimize the Cool Companion Fridge Inventory application on a Raspberry Pi 3 Model B running Raspberry Pi OS.

## System Requirements

- **Hardware**: Raspberry Pi 3 Model B or newer
- **OS**: Raspberry Pi OS (latest version recommended)
- **Memory**: 1GB RAM minimum (Raspberry Pi 3 Model B has 1GB)
- **Storage**: 8GB SD card minimum, 16GB+ recommended
- **Camera**: USB webcam or Raspberry Pi Camera Module
- **Display**: HDMI monitor or touchscreen

## Initial System Setup

### 1. Update Your System

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get dist-upgrade -y
```

### 2. Enable GL Driver (Critical for GUI)

The application requires OpenGL support. Enable it using `raspi-config`:

```bash
sudo raspi-config
```

Navigate to:
- **Advanced Options** → **GL Driver** → **G2 GL (Fake KMS)**

Or use the command line:

```bash
sudo raspi-config nonint do_gldriver G2
```

**Reboot after enabling GL driver:**

```bash
sudo reboot
```

### 3. Install Required System Libraries

```bash
# OpenGL ES libraries (required for GL context)
sudo apt-get install -y libgles2-mesa libgles2-mesa-dev

# Additional graphics libraries
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0

# Camera and video libraries
sudo apt-get install -y libv4l-dev v4l-utils

# Barcode scanning dependencies
sudo apt-get install -y libzbar0

# Python development headers
sudo apt-get install -y python3-dev python3-pip

# Optional: For better performance
sudo apt-get install -y libatlas-base-dev
```

### 4. Configure GPU Memory

Allocate more memory to the GPU for better graphics performance:

```bash
sudo raspi-config
```

Navigate to:
- **Performance Options** → **GPU Memory** → Set to **128** or **256**

Or edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add or modify:
```
gpu_mem=128
```

**Reboot after changing GPU memory:**

```bash
sudo reboot
```

## Application Installation

### 1. Clone or Copy the Application

```bash
cd ~
# If using git:
git clone https://github.com/Ian-Nicholls89/Cool-Companion.git cool-companion
cd cool-companion

# Or copy files to Raspberry Pi using scp, USB, etc.
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install --upgrade pip && pip install -r requirements.txt
```

**Note**: The `requirements.txt` is optimized for Raspberry Pi and will automatically install `opencv-python-headless` instead of the full OpenCV package.

### 4. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
nano .env
```

**Recommended Raspberry Pi Settings:**

```bash
# Camera Configuration (lower resolution for better performance)
CAMERA_INDEX=0
CAMERA_WIDTH=320
CAMERA_HEIGHT=240
CAMERA_FPS=15

# Window Configuration (fullscreen recommended)
WINDOW_FULLSCREEN=true

# Performance Settings
ENABLE_HARDWARE_ACCELERATION=true
REDUCE_ANIMATIONS=true

# Bring API (optional)
BRING_EMAIL=your_email@example.com
BRING_PASSWORD=your_password
```

## Troubleshooting GL Context Errors

If you encounter the "unable to create a GL context" error, try these solutions in order:

### Solution 1: Verify GL Driver is Enabled

```bash
vcgencmd get_config int | grep dtoverlay
```

Should show: `dtoverlay=vc4-fkms-v3d` or `dtoverlay=vc4-kms-v3d`

If not, re-enable using `raspi-config` as described above.

### Solution 2: Set Display Environment Variable

```bash
export DISPLAY=:0
```

Add to `~/.bashrc` to make permanent:

```bash
echo 'export DISPLAY=:0' >> ~/.bashrc
source ~/.bashrc
```

### Solution 3: Adjust OpenGL Settings

If hardware acceleration fails, you can adjust Qt's OpenGL settings:

```bash
export QT_QUICK_BACKEND=software
```

Or disable hardware acceleration in your `.env` file:
```
ENABLE_HARDWARE_ACCELERATION=false
```

### Solution 4: Check X11 is Running

Ensure you're running in desktop mode, not headless:

```bash
ps aux | grep X
```

If X is not running, start the desktop environment:

```bash
startx
```

### Solution 5: Verify OpenGL Libraries

```bash
# Check if libraries are installed
ldconfig -p | grep libGLES
ldconfig -p | grep libGL
```

If missing, reinstall:

```bash
sudo apt-get install --reinstall libgles2-mesa libgl1-mesa-glx
```

## Running the Application

### Standard Run

```bash
cd ~/cool-companion && chmod +x run.sh && ./run.sh
```

### Run with Logging

```bash
python main.py 2>&1 | tee app.log
```

### Auto-start on Boot (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/cool-companion.service
```

Add:

```ini
[Unit]
Description=Cool Companion Fridge Inventory
After=graphical.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/cool-companion
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/home/pi/.Xauthority"
ExecStart=/home/pi/cool-companion/venv/bin/python /home/pi/cool-companion/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cool-companion.service
sudo systemctl start cool-companion.service
```

Check status:

```bash
sudo systemctl status cool-companion.service
```

## Performance Optimization Tips

### 1. Reduce Camera Resolution

Lower resolution = better performance:

```bash
CAMERA_WIDTH=320
CAMERA_HEIGHT=240
CAMERA_FPS=15
```

### 2. Use Fullscreen Mode

Fullscreen mode reduces window management overhead:

```bash
WINDOW_FULLSCREEN=true
```

### 3. Disable Desktop Effects

```bash
# Disable compositor for better performance
sudo apt-get remove --purge xcompmgr
```

### 4. Overclock (Advanced)

**Warning**: Overclocking may void warranty and cause instability.

Edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add (for Raspberry Pi 3):

```
# Overclock settings (use at your own risk)
over_voltage=2
arm_freq=1300
gpu_freq=500
```

### 5. Use Lite OS for Headless Operation

For production deployments without GUI, consider Raspberry Pi OS Lite and run in web browser mode.

## Camera Setup

### USB Webcam

1. Connect USB webcam
2. List available cameras:

```bash
v4l2-ctl --list-devices
```

3. Test camera:

```bash
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

4. Set `CAMERA_INDEX` in `.env` (usually 0)

### Raspberry Pi Camera Module

1. Enable camera in `raspi-config`:

```bash
sudo raspi-config
```

Navigate to: **Interface Options** → **Camera** → **Enable**

2. Reboot:

```bash
sudo reboot
```

3. Test camera:

```bash
raspistill -o test.jpg
```

4. The application will auto-detect the camera

## Monitoring and Maintenance

### Check System Resources

```bash
# CPU temperature
vcgencmd measure_temp

# Memory usage
free -h

# Disk usage
df -h

# Running processes
htop
```

### View Application Logs

```bash
# If running as service
sudo journalctl -u cool-companion.service -f

# If running manually
tail -f app.log
```

### Update Application

```bash
cd ~/cool-companion
git pull  # If using git
cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

## Common Issues and Solutions

### Issue: Application is Slow

**Solutions:**
- Lower camera resolution (320x240)
- Reduce FPS (10-15)
- Enable fullscreen mode
- Close other applications
- Check CPU temperature (should be < 80°C)

### Issue: Camera Not Detected

**Solutions:**
- Check camera connection
- Run `v4l2-ctl --list-devices`
- Try different USB port
- Check camera permissions: `sudo usermod -a -G video $USER`
- Reboot

### Issue: Barcode Scanning Not Working

**Solutions:**
- Ensure good lighting
- Hold barcode steady
- Try different distances (10-30cm)
- Clean camera lens
- Check barcode is not damaged

### Issue: High CPU Usage

**Solutions:**
- Lower camera FPS
- Reduce camera resolution
- Enable `REDUCE_ANIMATIONS=true`
- Close background applications
- Check for runaway processes: `htop`

## Support and Resources

- **Application Issues**: Check application logs and GitHub issues
- **Raspberry Pi Issues**: Visit [Raspberry Pi Forums](https://forums.raspberrypi.com/)
- **OpenGL Issues**: Check `/var/log/Xorg.0.log`

## Quick Reference Commands

```bash
# Start application
cd ~/cool-companion && ./run.sh

# Check GL driver
vcgencmd get_config int | grep dtoverlay

# Check temperature
vcgencmd measure_temp

# List cameras
v4l2-ctl --list-devices

# View logs (if service)
sudo journalctl -u cool-companion.service -f

# Restart service
sudo systemctl restart cool-companion.service
```

## Performance Benchmarks

Expected performance on Raspberry Pi 3 Model B:

- **Startup Time**: 10-15 seconds
- **Camera FPS**: 10-15 fps (at 320x240)
- **Barcode Scan Time**: 1-3 seconds
- **UI Responsiveness**: Good with optimizations
- **Memory Usage**: 200-400 MB
- **CPU Usage**: 30-60% during camera operation

---

**Last Updated**: 2025-10-14
**Version**: 1.0
**Tested On**: Raspberry Pi 3 Model B, Raspberry Pi OS (Bookworm)