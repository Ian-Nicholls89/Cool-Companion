"""Service for camera operations with barcode scanning."""
import asyncio
import logging
import threading
import time
from typing import Optional, Callable
import cv2
from pyzbar import pyzbar
import numpy as np
import base64
from config.settings import settings

logger = logging.getLogger(__name__)

# Camera service configuration constants
BARCODE_DEBOUNCE_SECONDS = 2.0  # Seconds to wait before scanning same barcode again
CAMERA_KEEP_ALIVE_INTERVAL = 5.0  # Seconds between keep-alive frame reads
CAMERA_RELEASE_DELAY = 0.1  # Seconds to wait after releasing camera

class CameraError(Exception):
    """Exception for camera operations."""
    pass

def enumerate_cameras(max_cameras: int = 3) -> list:
    """Enumerate available camera devices.

    Args:
        max_cameras: Maximum number of cameras to check (default: 3 for performance)

    Returns:
        List of tuples (index, name) for available cameras
    """
    available_cameras = []
    consecutive_failures = 0

    for index in range(max_cameras):
        cap = None
        try:
            # Use V4L2 backend on Linux for better Raspberry Pi compatibility
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
            except Exception as e:
                logger.debug(f"V4L2 backend not available for camera {index}: {e}, using default backend")
                cap = cv2.VideoCapture(index)

            if cap and cap.isOpened():
                # Try to get camera name (backend-specific)
                backend = cap.getBackendName()

                # Get basic camera info
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # Create a descriptive name
                name = f"Camera {index} ({backend} - {width}x{height})"

                available_cameras.append((index, name))
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                # If we fail to open 2 cameras in a row, stop checking
                if consecutive_failures >= 2:
                    break
        except Exception as e:
            logger.debug(f"Error checking camera {index}: {e}")
            consecutive_failures += 1
            # Stop checking if we hit 2 errors in a row
            if consecutive_failures >= 2:
                break
        finally:
            # Always release camera, even on error
            if cap is not None:
                try:
                    cap.release()
                except Exception as e:
                    logger.debug(f"Error releasing camera {index}: {e}")

    # Small delay to ensure cameras are fully released
    time.sleep(CAMERA_RELEASE_DELAY)
    return available_cameras

class CameraService:
    """Service for camera operations with proper resource management."""

    def __init__(self, camera_index: int = None, settings=None):
        """Initialize camera service.

        Args:
            camera_index: Camera device index
            settings: Application settings
        """
        self.settings = settings or globals()['settings']
        self.camera_index = camera_index if camera_index is not None else self.settings.camera_index
        self.cap = None
        self.is_running = False
        self._lock = threading.RLock()  # Use RLock for reentrant locking
        self._scan_thread = None
        self._scan_callback = None
        self._last_barcode = None
        self._last_barcode_time = 0
        self._debounce_time = BARCODE_DEBOUNCE_SECONDS
        self._keep_alive_thread = None
        self._keep_alive_running = False
        self._scan_in_progress = False  # Flag to prevent keep-alive during scan

    def _open_camera(self, index: int) -> Optional[cv2.VideoCapture]:
        """Open camera with proper backend selection.

        Args:
            index: Camera index

        Returns:
            VideoCapture object or None
        """
        try:
            # Try V4L2 backend first (better for Raspberry Pi)
            try:
                cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
                if cap.isOpened():
                    logger.debug(f"Opened camera {index} with V4L2 backend")
                    return cap
            except Exception as e:
                logger.debug(f"V4L2 backend not available for camera {index}: {e}")

            # Fallback to default backend
            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                logger.debug(f"Opened camera {index} with default backend")
                return cap

            return None
        except Exception as e:
            logger.error(f"Error opening camera {index}: {e}")
            return None

    def start_camera(self) -> bool:
        """Initialize camera with error handling.

        Returns:
            True if camera started successfully
        """
        with self._lock:
            if self.cap and self.cap.isOpened():
                return True

            try:
                # Release any existing camera
                if self.cap:
                    try:
                        self.cap.release()
                    except Exception as e:
                        logger.debug(f"Error releasing camera: {e}")
                    self.cap = None
                    time.sleep(CAMERA_RELEASE_DELAY)  # Give camera time to fully release

                # Try to open camera
                self.cap = self._open_camera(self.camera_index)

                if not self.cap or not self.cap.isOpened():
                    # Try alternative camera indices
                    logger.warning(f"Camera {self.camera_index} not available, trying alternatives")
                    for idx in [0, 1, 2]:
                        if idx != self.camera_index:
                            self.cap = self._open_camera(idx)
                            if self.cap and self.cap.isOpened():
                                self.camera_index = idx
                                logger.info(f"Using camera index {idx}")
                                break

                if self.cap and self.cap.isOpened():
                    # Set camera properties with error handling
                    try:
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera_width)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera_height)
                        self.cap.set(cv2.CAP_PROP_FPS, self.settings.camera_fps)

                        # Set buffer size to 1 to reduce latency
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception as e:
                        logger.warning(f"Could not set camera properties: {e}")

                    self.is_running = True
                    logger.info(f"Camera {self.camera_index} started successfully")
                    return True
                else:
                    raise CameraError("No camera available")

            except Exception as e:
                logger.error(f"Camera initialization failed: {e}")
                if self.cap:
                    try:
                        self.cap.release()
                    except Exception as e2:
                        logger.debug(f"Error releasing camera after init failure: {e2}")
                    self.cap = None
                raise CameraError(f"Failed to initialize camera: {e}")

    def start_keep_alive(self):
        """Start keep-alive mode to keep camera warm without scanning.

        This keeps the camera initialized and periodically reads frames to prevent
        it from timing out or releasing, but doesn't perform barcode detection.
        This eliminates initialization delay when scanning is requested.
        """
        with self._lock:
            if self._keep_alive_running:
                logger.debug("Keep-alive already running, skipping start")
                return

            if not self.start_camera():
                logger.warning("Failed to start camera for keep-alive")
                return

            self._keep_alive_running = True
            logger.info("Starting camera keep-alive thread")

        def keep_alive_loop():
            logger.info("Camera keep-alive started")
            while self._keep_alive_running:
                try:
                    # Wait if scan is in progress
                    if self._scan_in_progress:
                        time.sleep(0.5)
                        continue

                    with self._lock:
                        if self.cap and self.cap.isOpened():
                            # Read a frame to keep camera active
                            ret, frame = self.cap.read()
                            if not ret:
                                logger.warning("Failed to read frame in keep-alive, will retry")
                        else:
                            # Camera closed, try to restart
                            logger.warning("Camera closed in keep-alive, attempting restart")
                            time.sleep(0.5)
                            try:
                                self.start_camera()
                            except Exception as e:
                                logger.error(f"Failed to restart camera in keep-alive: {e}")

                    time.sleep(1.0)  # Check every second
                except Exception as e:
                    logger.error(f"Error in keep-alive loop: {e}")
                    time.sleep(1.0)

            logger.info("Camera keep-alive stopped")

        self._keep_alive_thread = threading.Thread(target=keep_alive_loop, daemon=True)
        self._keep_alive_thread.start()

    def stop_keep_alive(self):
        """Stop keep-alive mode."""
        if self._keep_alive_running:
            self._keep_alive_running = False
            if self._keep_alive_thread:
                self._keep_alive_thread.join(timeout=2.0)
            logger.info("Camera keep-alive stopped")

    def stop_camera(self):
        """Properly release camera resources."""
        # Stop keep-alive first
        self.stop_keep_alive()

        with self._lock:
            self.is_running = False

            # Stop scan thread if running
            if self._scan_thread and self._scan_thread.is_alive():
                self._scan_thread.join(timeout=1.0)

            # Release camera
            if self.cap:
                try:
                    self.cap.release()
                    logger.info("Camera released")
                except Exception as e:
                    logger.error(f"Error releasing camera: {e}")
                finally:
                    self.cap = None

    async def stop(self):
        """Async version of stop_camera."""
        await asyncio.to_thread(self.stop_camera)

    def scan_barcode_sync(self, timeout: int = None, frame_callback: Callable[[str, int], None] = None, stop_flag: Callable[[], bool] = None) -> Optional[str]:
        """Synchronously scan for barcode with optional frame callback.

        Args:
            timeout: Timeout in seconds
            frame_callback: Optional callback function(base64_frame, remaining_seconds) for live feed
            stop_flag: Optional callable that returns True when scanning should stop

        Returns:
            Barcode string or None if timeout
        """
        timeout = timeout or self.settings.scan_timeout

        # Signal keep-alive to pause
        self._scan_in_progress = True

        # Wait a bit for keep-alive to pause
        time.sleep(0.2)

        try:
            with self._lock:
                if not self.start_camera():
                    raise CameraError("Failed to start camera")

            start_time = time.time()

            # Check both camera state and optional stop flag
            while self.is_running and (time.time() - start_time) < timeout:
                # Allow external cancellation
                if stop_flag and stop_flag():
                    logger.info("Barcode scan cancelled by user")
                    break

                with self._lock:
                    if not self.cap or not self.cap.isOpened():
                        logger.error("Camera not available during scan")
                        break

                    ret, frame = self.cap.read()

                if not ret:
                    time.sleep(0.1)
                    continue

                # Calculate remaining time
                remaining = int(timeout - (time.time() - start_time))

                # Add visual guide overlay
                h, w = frame.shape[:2]
                guide_color = (0, 255, 0)  # Green
                margin = 50

                # Draw guide rectangle
                cv2.rectangle(frame, (margin, margin), (w - margin, h - margin), guide_color, 2)

                # Add instruction text
                text = "Align barcode within frame"
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frame, text, (margin, margin - 10), font, 0.7, guide_color, 2)

                # Send frame to callback if provided
                if frame_callback:
                    try:
                        # Encode frame to base64
                        _, buffer = cv2.imencode('.jpg', frame)
                        frame_base64 = base64.b64encode(buffer).decode('utf-8')
                        frame_callback(frame_base64, remaining)
                    except Exception as e:
                        logger.error(f"Error in frame callback: {e}")

                # Decode barcodes
                barcodes = pyzbar.decode(frame)
                if barcodes:
                    barcode_data = barcodes[0].data.decode('utf-8')

                    # Check debounce
                    current_time = time.time()
                    if (barcode_data != self._last_barcode or
                        current_time - self._last_barcode_time > self._debounce_time):

                        self._last_barcode = barcode_data
                        self._last_barcode_time = current_time

                        logger.info(f"Barcode detected: {barcode_data}")
                        return barcode_data

                # Small delay to prevent CPU overload
                time.sleep(0.1)  # ~10 FPS for UI updates

            return None

        except Exception as e:
            logger.error(f"Error during barcode scanning: {e}")
            raise

        finally:
            # Resume keep-alive
            self._scan_in_progress = False

    async def scan_barcode(self, timeout: int = None) -> Optional[str]:
        """Asynchronously scan for barcode.

        Args:
            timeout: Timeout in seconds

        Returns:
            Barcode string or None if timeout
        """
        return await asyncio.to_thread(self.scan_barcode_sync, timeout)

    def start_continuous_scan(self, callback: Callable[[str], None]):
        """Start continuous barcode scanning.

        Args:
            callback: Function to call when barcode is detected
        """
        if self._scan_thread and self._scan_thread.is_alive():
            logger.warning("Scan already in progress")
            return

        self._scan_callback = callback
        self._scan_thread = threading.Thread(target=self._continuous_scan_loop, daemon=True)
        self._scan_thread.start()
        logger.info("Started continuous barcode scanning")

    def _continuous_scan_loop(self):
        """Internal loop for continuous scanning."""
        # Signal keep-alive to pause
        self._scan_in_progress = True
        time.sleep(0.2)

        try:
            with self._lock:
                if not self.start_camera():
                    logger.error("Failed to start camera for continuous scan")
                    return
        except Exception as e:
            logger.error(f"Error starting camera for continuous scan: {e}")
            return

        try:
            while self.is_running:
                with self._lock:
                    if not self.cap or not self.cap.isOpened():
                        break
                    ret, frame = self.cap.read()

                if not ret:
                    time.sleep(0.1)
                    continue

                # Decode barcodes
                barcodes = pyzbar.decode(frame)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')

                    # Check debounce
                    current_time = time.time()
                    if (barcode_data != self._last_barcode or
                        current_time - self._last_barcode_time > self._debounce_time):

                        self._last_barcode = barcode_data
                        self._last_barcode_time = current_time

                        logger.info(f"Continuous scan detected: {barcode_data}")

                        # Call callback
                        if self._scan_callback:
                            try:
                                self._scan_callback(barcode_data)
                            except Exception as e:
                                logger.error(f"Error in scan callback: {e}")

                time.sleep(0.033)  # ~30 FPS

        except Exception as e:
            logger.error(f"Error in continuous scan loop: {e}")
        finally:
            self._scan_in_progress = False

    def stop_continuous_scan(self):
        """Stop continuous barcode scanning."""
        self.is_running = False
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=1.0)
        self._scan_callback = None
        self._scan_in_progress = False
        logger.info("Stopped continuous barcode scanning")

    def get_frame(self) -> Optional[np.ndarray]:
        """Get current camera frame.

        Returns:
            Frame as numpy array or None
        """
        with self._lock:
            if not self.cap or not self.cap.isOpened():
                return None

            ret, frame = self.cap.read()
            if ret:
                return frame
            return None

    def get_frame_base64(self) -> Optional[str]:
        """Get current camera frame as base64 string.

        Returns:
            Base64 encoded JPEG or None
        """
        frame = self.get_frame()
        if frame is None:
            return None

        try:
            # Add scanning guide overlay
            h, w = frame.shape[:2]

            # Draw guide rectangle
            guide_color = (0, 255, 0)  # Green
            guide_thickness = 2
            margin = 50

            cv2.rectangle(
                frame,
                (margin, margin),
                (w - margin, h - margin),
                guide_color,
                guide_thickness
            )

            # Add instruction text
            text = "Align barcode within frame"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.7
            font_thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
            text_x = (w - text_size[0]) // 2
            text_y = margin - 10

            # Draw text background
            cv2.rectangle(
                frame,
                (text_x - 5, text_y - text_size[1] - 5),
                (text_x + text_size[0] + 5, text_y + 5),
                (255, 255, 255),
                -1
            )

            # Draw text
            cv2.putText(
                frame,
                text,
                (text_x, text_y),
                font,
                font_scale,
                guide_color,
                font_thickness
            )

            # Encode to JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            return base64.b64encode(buffer).decode('utf-8')

        except Exception as e:
            logger.error(f"Error encoding frame to base64: {e}")
            return None

    def is_available(self) -> bool:
        """Check if camera service is available.

        Returns:
            True if camera is available
        """
        if not self.settings.enable_barcode_scanning:
            return False

        # If camera is already open by this service, it's available
        with self._lock:
            if self.cap and self.cap.isOpened():
                return True

        # Don't try to open camera if service is running (would conflict)
        if self.is_running or self._keep_alive_running:
            return True  # Assume available if service is running

        # Quick test to see if camera can be opened
        test_cap = None
        try:
            test_cap = self._open_camera(self.camera_index)
            available = test_cap is not None and test_cap.isOpened()
            return available
        except Exception:
            return False
        finally:
            if test_cap:
                try:
                    test_cap.release()
                except Exception as e:
                    logger.debug(f"Error releasing test camera: {e}")
            time.sleep(0.1)  # Give camera time to release

    def get_status(self) -> dict:
        """Get camera service status.

        Returns:
            Dictionary with status information
        """
        return {
            "enabled": self.settings.enable_barcode_scanning,
            "camera_index": self.camera_index,
            "is_running": self.is_running,
            "is_scanning": self._scan_thread and self._scan_thread.is_alive(),
            "keep_alive_running": self._keep_alive_running,
            "scan_in_progress": self._scan_in_progress,
            "available": self.is_available()
        }
