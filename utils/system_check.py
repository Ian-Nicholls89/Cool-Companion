"""
System compatibility checker for PySide6 application on Raspberry Pi.
Ensures the application can run properly with required dependencies.
"""
import os
import sys
import importlib.util
from typing import Tuple, List, Optional, Dict
from loguru import logger


class SystemCompatibilityChecker:
    """Check system compatibility for PySide6 application."""

    # Cache for Raspberry Pi detection (avoid repeated file reads)
    _is_rpi_cache: Optional[bool] = None

    @staticmethod
    def is_raspberry_pi() -> bool:
        """Detect if running on Raspberry Pi (cached)."""
        if SystemCompatibilityChecker._is_rpi_cache is not None:
            return SystemCompatibilityChecker._is_rpi_cache

        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                SystemCompatibilityChecker._is_rpi_cache = 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
                return SystemCompatibilityChecker._is_rpi_cache
        except FileNotFoundError:
            SystemCompatibilityChecker._is_rpi_cache = False
            return False

    @staticmethod
    def get_raspberry_pi_model() -> Optional[str]:
        """Get Raspberry Pi model information."""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                return f.read().strip('\x00')
        except FileNotFoundError:
            return None

    @staticmethod
    def check_python_version() -> Tuple[bool, Optional[str]]:
        """Check if Python version meets minimum requirements."""
        if sys.version_info < (3, 9):
            return False, f"Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}"
        logger.info(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        return True, None

    @staticmethod
    def check_required_packages() -> Tuple[bool, List[str]]:
        """Check if required Python packages are installed."""
        required_packages = {
            'PySide6': 'PySide6',
            'cv2': 'opencv-python or opencv-python-headless',
            'pyzbar': 'pyzbar',
            'dotenv': 'python-dotenv',
            'loguru': 'loguru',
        }

        missing = []
        for module, package_name in required_packages.items():
            if importlib.util.find_spec(module) is None:
                missing.append(package_name)
                logger.warning(f"Missing package: {package_name}")
            else:
                logger.info(f"Found package: {module}")

        return len(missing) == 0, missing

    @staticmethod
    def check_qt_platform() -> Tuple[bool, Optional[str]]:
        """Check Qt platform plugin availability."""
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QCoreApplication

            # Check available platform plugins
            platform_plugins = QCoreApplication.libraryPaths()
            logger.info(f"Qt plugin paths: {platform_plugins}")

            # Check QT_QPA_PLATFORM environment variable
            qpa_platform = os.environ.get('QT_QPA_PLATFORM', 'default')
            logger.info(f"Qt platform: {qpa_platform}")

            return True, None
        except ImportError as e:
            return False, f"PySide6 import failed: {e}"
        except Exception as e:
            logger.warning(f"Qt platform check warning: {e}")
            return True, None  # Non-critical warning

    @staticmethod
    def check_display_server() -> Tuple[bool, Optional[str]]:
        """Check if a display server is available."""
        display = os.environ.get('DISPLAY')
        wayland_display = os.environ.get('WAYLAND_DISPLAY')

        if wayland_display:
            logger.info(f"Wayland display server detected: {wayland_display}")
            return True, None
        elif display:
            logger.info(f"X11 display server detected: {display}")
            return True, None
        else:
            return False, "No display server found. Set DISPLAY or WAYLAND_DISPLAY environment variable."

    @staticmethod
    def check_camera_availability() -> Tuple[int, List[int]]:
        """
        Check available camera devices.

        Returns:
            Tuple of (count, list of camera indices)
        """
        available_cameras = []

        try:
            import cv2

            # Try up to 10 camera indices
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available_cameras.append(i)
                    cap.release()
                else:
                    break  # Stop checking after first unavailable camera

            logger.info(f"Found {len(available_cameras)} camera(s): {available_cameras}")
            return len(available_cameras), available_cameras

        except ImportError:
            logger.warning("OpenCV not available, cannot check cameras")
            return 0, []
        except Exception as e:
            logger.warning(f"Error checking cameras: {e}")
            return 0, []

    @staticmethod
    def check_memory() -> Tuple[bool, Dict[str, float]]:
        """
        Check system memory on Raspberry Pi.

        Returns:
            Tuple of (sufficient: bool, memory_info: dict)
        """
        memory_info = {}

        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                for line in meminfo.split('\n'):
                    if 'MemTotal' in line:
                        mem_kb = int(line.split()[1])
                        memory_info['total_mb'] = mem_kb / 1024
                    elif 'MemAvailable' in line:
                        mem_kb = int(line.split()[1])
                        memory_info['available_mb'] = mem_kb / 1024

            logger.info(f"System memory: {memory_info.get('total_mb', 0):.0f}MB total, "
                       f"{memory_info.get('available_mb', 0):.0f}MB available")

            # Recommend at least 512MB total
            is_sufficient = memory_info.get('total_mb', 0) >= 512
            return is_sufficient, memory_info

        except FileNotFoundError:
            # Not on Linux, skip check
            return True, {}
        except Exception as e:
            logger.warning(f"Could not check memory: {e}")
            return True, {}

    @staticmethod
    def check_system_requirements() -> Tuple[bool, List[str]]:
        """
        Check all system requirements for running the application.

        Returns:
            Tuple of (all_passed: bool, issues: List[str])
        """
        issues = []
        warnings = []

        # Check Python version
        py_ok, py_error = SystemCompatibilityChecker.check_python_version()
        if not py_ok:
            issues.append(py_error)

        # Check required packages
        pkg_ok, missing_packages = SystemCompatibilityChecker.check_required_packages()
        if not pkg_ok:
            issues.append(f"Missing required packages: {', '.join(missing_packages)}")
            issues.append("Install with: pip install -r requirements.txt")

        # Check Qt platform (non-critical)
        qt_ok, qt_error = SystemCompatibilityChecker.check_qt_platform()
        if not qt_ok:
            issues.append(qt_error)

        # Check display server
        display_ok, display_error = SystemCompatibilityChecker.check_display_server()
        if not display_ok:
            issues.append(display_error)

        # Check camera availability (warning only)
        camera_count, camera_indices = SystemCompatibilityChecker.check_camera_availability()
        if camera_count == 0:
            warnings.append("No cameras detected - barcode scanning will not work")

        # Check if running on Raspberry Pi
        is_rpi = SystemCompatibilityChecker.is_raspberry_pi()
        if is_rpi:
            model = SystemCompatibilityChecker.get_raspberry_pi_model()
            logger.info(f"Detected: {model}")

            # Check memory
            mem_ok, mem_info = SystemCompatibilityChecker.check_memory()
            if not mem_ok:
                warnings.append(f"Low memory: {mem_info.get('total_mb', 0):.0f}MB. "
                              "Recommend 1GB+ for optimal performance")

        # Log warnings
        for warning in warnings:
            logger.warning(warning)

        return len(issues) == 0, issues

    @staticmethod
    def get_optimization_recommendations() -> List[str]:
        """
        Get optimization recommendations for the current system.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if SystemCompatibilityChecker.is_raspberry_pi():
            recommendations.extend([
                "Use lower camera resolution (320x240 or 640x480) in .env file",
                "Enable fullscreen mode for better performance: WINDOW_FULLSCREEN=true",
                "Increase GPU memory: sudo raspi-config -> Performance -> GPU Memory -> 128MB+",
                "Reduce animations: REDUCE_ANIMATIONS=true",
                "Use Qt software rendering if performance issues: export QT_QUICK_BACKEND=software"
            ])

        return recommendations

    @staticmethod
    def apply_raspberry_pi_optimizations():
        """Apply Raspberry Pi specific optimizations to environment."""
        if not SystemCompatibilityChecker.is_raspberry_pi():
            return

        logger.info("Applying Raspberry Pi optimizations...")

        # Qt optimizations
        if not os.environ.get('QT_QPA_PLATFORM'):
            # Let Qt auto-detect the best platform (xcb for X11, wayland for Wayland)
            logger.info("Using Qt auto-detect for platform plugin")

        # Set optimal threading for Raspberry Pi
        if not os.environ.get('OMP_NUM_THREADS'):
            os.environ['OMP_NUM_THREADS'] = '2'
            logger.info("Set OMP_NUM_THREADS=2")

        # Reduce OpenCV threading overhead
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'

        # Qt rendering optimizations
        if not os.environ.get('QT_QUICK_BACKEND'):
            # Use default hardware rendering unless user specifies otherwise
            logger.info("Using Qt hardware rendering (default)")

        logger.info("Raspberry Pi optimizations applied")


def check_and_report_system() -> bool:
    """
    Check system compatibility and report issues.

    Returns:
        True if system is compatible, False otherwise
    """
    logger.info("Performing system compatibility check...")

    checker = SystemCompatibilityChecker()
    all_ok, issues = checker.check_system_requirements()

    if not all_ok:
        logger.error("System compatibility issues detected:")
        for issue in issues:
            logger.error(f"  - {issue}")

        # Show recommendations
        recommendations = checker.get_optimization_recommendations()
        if recommendations:
            logger.info("Recommendations:")
            for rec in recommendations:
                logger.info(f"  - {rec}")

        return False

    logger.info("System compatibility check passed!")

    # Apply optimizations if on Raspberry Pi
    checker.apply_raspberry_pi_optimizations()

    return True


def check_gl_context_for_qt() -> bool:
    """
    Legacy function for backwards compatibility.
    Qt handles GL context internally, so this is now a no-op.

    Returns:
        True (always)
    """
    logger.debug("GL context check skipped - Qt handles this internally")
    return True
