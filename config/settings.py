"""
Application settings and configuration management.
Uses environment variables for sensitive data.
Includes Raspberry Pi specific optimizations.
"""
import os
import platform
from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file (override existing env vars)
load_dotenv(override=True)

# Cache for Raspberry Pi detection (avoid repeated file reads)
_IS_RPI_CACHE: Optional[bool] = None

def _is_raspberry_pi() -> bool:
    """Quick check if running on Raspberry Pi (cached)."""
    global _IS_RPI_CACHE

    if _IS_RPI_CACHE is not None:
        return _IS_RPI_CACHE

    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            _IS_RPI_CACHE = 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
            return _IS_RPI_CACHE
    except:
        _IS_RPI_CACHE = False
        return False

@dataclass
class Settings:
    """Application settings from environment variables"""
    
    # Bring API Configuration
    bring_email: str = os.getenv('BRING_EMAIL', '')
    bring_password: str = os.getenv('BRING_PASSWORD', '')
    
    # Database Configuration
    database_path: str = os.getenv('DATABASE_PATH', 'fridge.db')
    connection_pool_size: int = int(os.getenv('CONNECTION_POOL_SIZE', '5'))
    
    # Camera Configuration (with Raspberry Pi optimizations)
    camera_index: int = int(os.getenv('CAMERA_INDEX', '0') or '0')
    # Lower default resolution for Raspberry Pi
    _default_width = '320' if _is_raspberry_pi() else '640'
    _default_height = '240' if _is_raspberry_pi() else '480'
    _default_fps = '15' if _is_raspberry_pi() else '30'
    camera_width: int = int(os.getenv('CAMERA_WIDTH', _default_width))
    camera_height: int = int(os.getenv('CAMERA_HEIGHT', _default_height))
    camera_fps: int = int(os.getenv('CAMERA_FPS', _default_fps))
    scan_timeout: int = int(os.getenv('SCAN_TIMEOUT', '30'))
    
    # API Configuration
    openfoodfacts_url: str = "https://world.openfoodfacts.org/api/v0/product/"
    api_timeout: int = int(os.getenv('API_TIMEOUT', '5'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    api_verify_ssl: bool = os.getenv('API_VERIFY_SSL', 'true').lower() == 'true'
    
    # UI Configuration (with Raspberry Pi optimizations)
    window_width: int = int(os.getenv('WINDOW_WIDTH', '400'))
    window_height: int = int(os.getenv('WINDOW_HEIGHT', '700'))
    # Default to fullscreen on Raspberry Pi for better performance
    _default_fullscreen = 'true' if _is_raspberry_pi() else 'false'
    window_fullscreen: bool = os.getenv('WINDOW_FULLSCREEN', _default_fullscreen).lower() == 'true'
    theme_mode: str = os.getenv('THEME_MODE', 'light')
    
    # Raspberry Pi Performance Settings
    enable_hardware_acceleration: bool = os.getenv('ENABLE_HARDWARE_ACCELERATION', 'true').lower() == 'true'
    reduce_animations: bool = os.getenv('REDUCE_ANIMATIONS', str(_is_raspberry_pi()).lower()).lower() == 'true'
    
    # Development Settings
    skip_system_checks: bool = os.getenv('SKIP_SYSTEM_CHECKS', 'false').lower() == 'true'
    
    # Feature Flags
    enable_barcode_scanning: bool = os.getenv('ENABLE_BARCODE_SCANNING', 'true').lower() == 'true'
    enable_shopping_list: bool = os.getenv('ENABLE_SHOPPING_LIST', 'true').lower() == 'true'
    enable_statistics: bool = os.getenv('ENABLE_STATISTICS', 'true').lower() == 'true'

    # Update Configuration
    enable_update_check: bool = os.getenv('ENABLE_UPDATE_CHECK', 'true').lower() == 'true'
    update_check_frequency_hours: int = int(os.getenv('UPDATE_CHECK_FREQUENCY_HOURS', '24'))

    # Validation Configuration
    max_item_name_length: int = int(os.getenv('MAX_ITEM_NAME_LENGTH', '100'))
    max_barcode_length: int = int(os.getenv('MAX_BARCODE_LENGTH', '50'))
    days_before_expiry_warning: int = int(os.getenv('DAYS_BEFORE_EXPIRY_WARNING', '3'))

    statement = None

    # Check for default credentials and disable shopping list if found
    if bring_password == 'your_secure_password' and bring_email == 'your_email@example.com' and enable_shopping_list:
        statement = [
            "Warning: Default Bring! credentials detected. Shopping list has been disabled.",
            "Please update BRING_EMAIL and BRING_PASSWORD in your .env file or via Settings menu.",
            "Re-enable shopping list after updating credentials."
        ]
        # Disable in-memory only - don't modify .env file
        enable_shopping_list = False
    
    def validate(self, log_errors: bool = True) -> bool:
        """Validate settings.

        Args:
            log_errors: If True, errors are printed to stdout (for backwards compatibility)

        Returns:
            True if validation passed, False otherwise
        """
        errors = []

        if self.enable_shopping_list and not (self.bring_email and self.bring_password):
            errors.append("Bring credentials required when shopping list is enabled")

        if self.connection_pool_size < 1:
            errors.append("Connection pool size must be at least 1")

        if self.api_timeout < 1:
            errors.append("API timeout must be at least 1 second")

        if errors and log_errors:
            for error in errors:
                print(f"Configuration Error: {error}")

        return len(errors) == 0

    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors without logging.

        Returns:
            List of validation error messages
        """
        errors = []

        if self.enable_shopping_list and not (self.bring_email and self.bring_password):
            errors.append("Bring credentials required when shopping list is enabled")

        if self.connection_pool_size < 1:
            errors.append("Connection pool size must be at least 1")

        if self.api_timeout < 1:
            errors.append("API timeout must be at least 1 second")

        if self.camera_index < 0 or self.camera_index > 10:
            errors.append(f"Camera index must be between 0 and 10 (got {self.camera_index})")

        return errors
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    def is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi"""
        return _is_raspberry_pi()
    
    def get_database_path(self) -> str:
        """Get full database path"""
        if os.path.isabs(self.database_path):
            return self.database_path
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), self.database_path)
    
    def get_optimized_settings_info(self) -> dict:
        """Get information about current optimization settings"""
        return {
            'is_raspberry_pi': self.is_raspberry_pi(),
            'camera_resolution': f"{self.camera_width}x{self.camera_height}",
            'camera_fps': self.camera_fps,
            'fullscreen': self.window_fullscreen,
            'hardware_acceleration': self.enable_hardware_acceleration,
            'reduced_animations': self.reduce_animations
        }

# Create global settings instance
settings = Settings()

# Note: Settings validation is now performed in main.py after logger initialization
# This prevents race conditions and ensures proper error reporting