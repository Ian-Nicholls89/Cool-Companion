"""
System compatibility checker for Raspberry Pi and GL context validation.
Ensures the application can run properly on Raspberry Pi OS.
"""
import os
import sys
import subprocess
from typing import Tuple, List, Optional
from loguru import logger


class SystemCompatibilityChecker:
    """Check system compatibility and GL context availability."""
    
    @staticmethod
    def is_raspberry_pi() -> bool:
        """Detect if running on Raspberry Pi."""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                return 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
        except FileNotFoundError:
            return False
    
    @staticmethod
    def check_gl_context() -> Tuple[bool, Optional[str]]:
        """
        Check if OpenGL context can be created.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Try to import OpenGL
            import OpenGL.GL as gl
            from OpenGL.GL import glGetString, GL_VERSION
            
            # Try to get GL version (requires context)
            try:
                version = glGetString(GL_VERSION)
                if version:
                    logger.info(f"OpenGL version: {version.decode() if isinstance(version, bytes) else version}")
                    return True, None
            except Exception as e:
                logger.warning(f"Could not get GL version: {e}")
                # Continue to other checks
        except ImportError:
            logger.warning("PyOpenGL not installed, skipping GL version check")
        
        # Check for X11 display
        if not os.environ.get('DISPLAY'):
            return False, "No DISPLAY environment variable set. Run 'export DISPLAY=:0' or enable desktop environment."
        
        # Check if running in Wayland (which may have GL issues)
        if os.environ.get('WAYLAND_DISPLAY'):
            logger.warning("Wayland detected - may have GL compatibility issues")
        
        # Check for GL driver on Raspberry Pi
        if SystemCompatibilityChecker.is_raspberry_pi():
            gl_driver_check = SystemCompatibilityChecker._check_raspberry_pi_gl_driver()
            if not gl_driver_check[0]:
                return gl_driver_check
        
        return True, None
    
    @staticmethod
    def _check_raspberry_pi_gl_driver() -> Tuple[bool, Optional[str]]:
        """
        Check Raspberry Pi specific GL driver configuration.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        issues = []
        
        # Check if GL driver is enabled in raspi-config
        try:
            result = subprocess.run(
                ['vcgencmd', 'get_config', 'int'],
                capture_output=True,
                text=True,
                timeout=5
            )
            config = result.stdout
            
            # Check for legacy GL driver (should be disabled for modern apps)
            if 'dtoverlay=vc4-fkms-v3d' not in config and 'dtoverlay=vc4-kms-v3d' not in config:
                issues.append("GL driver may not be enabled. Run 'sudo raspi-config' -> Advanced Options -> GL Driver -> Enable")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Could not check vcgencmd - may not be on Raspberry Pi")
        
        # Check for required libraries
        required_libs = [
            '/usr/lib/arm-linux-gnueabihf/libGLESv2.so',
            '/usr/lib/aarch64-linux-gnu/libGLESv2.so',
            '/opt/vc/lib/libGLESv2.so'
        ]
        
        lib_found = any(os.path.exists(lib) for lib in required_libs)
        if not lib_found:
            issues.append("OpenGL ES libraries not found. Install with: sudo apt-get install libgles2-mesa libgles2-mesa-dev")
        
        if issues:
            return False, " | ".join(issues)
        
        return True, None
    
    @staticmethod
    def check_system_requirements() -> Tuple[bool, List[str]]:
        """
        Check all system requirements for running the application.
        
        Returns:
            Tuple of (all_passed: bool, issues: List[str])
        """
        issues = []
        
        # Check Python version
        if sys.version_info < (3, 9):
            issues.append(f"Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        
        # Check GL context
        gl_ok, gl_error = SystemCompatibilityChecker.check_gl_context()
        if not gl_ok:
            issues.append(f"GL Context Error: {gl_error}")
        
        # Check if running on Raspberry Pi
        is_rpi = SystemCompatibilityChecker.is_raspberry_pi()
        if is_rpi:
            logger.info("Running on Raspberry Pi - applying optimizations")
            
            # Check memory
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    for line in meminfo.split('\n'):
                        if 'MemTotal' in line:
                            mem_kb = int(line.split()[1])
                            mem_mb = mem_kb / 1024
                            if mem_mb < 512:
                                issues.append(f"Low memory detected: {mem_mb:.0f}MB. Recommend 1GB+ for optimal performance")
                            logger.info(f"System memory: {mem_mb:.0f}MB")
                            break
            except Exception as e:
                logger.warning(f"Could not check memory: {e}")
        
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
                "Set FLET_FORCE_SOFTWARE_RENDERING=1 for better compatibility",
                "Use lower camera resolution (320x240 or 640x480)",
                "Enable GPU memory split: sudo raspi-config -> Performance -> GPU Memory -> 128MB+",
                "Disable desktop effects for better performance",
                "Consider using lite version of Raspberry Pi OS for headless operation"
            ])
        
        return recommendations
    
    @staticmethod
    def apply_raspberry_pi_optimizations():
        """Apply Raspberry Pi specific optimizations to environment."""
        if not SystemCompatibilityChecker.is_raspberry_pi():
            return
        
        logger.info("Applying Raspberry Pi optimizations...")
        
        # Force software rendering if GL context fails
        gl_ok, _ = SystemCompatibilityChecker.check_gl_context()
        if not gl_ok:
            os.environ['FLET_FORCE_SOFTWARE_RENDERING'] = '1'
            logger.info("Enabled software rendering mode")
        
        # Set optimal threading for Raspberry Pi
        os.environ['OMP_NUM_THREADS'] = '2'
        
        # Reduce OpenCV threading overhead
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
        
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