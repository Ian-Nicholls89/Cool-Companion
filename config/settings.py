"""
Application settings and configuration management.
Uses environment variables for sensitive data.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class Settings:
    """Application settings from environment variables"""
    
    # Bring API Configuration
    bring_email: str = os.getenv('BRING_EMAIL', '')
    bring_password: str = os.getenv('BRING_PASSWORD', '')
    
    # Database Configuration
    database_path: str = os.getenv('DATABASE_PATH', 'fridge.db')
    connection_pool_size: int = int(os.getenv('CONNECTION_POOL_SIZE', '5'))
    
    # Camera Configuration
    camera_index: int = int(os.getenv('CAMERA_INDEX', '0'))
    camera_width: int = int(os.getenv('CAMERA_WIDTH', '640'))
    camera_height: int = int(os.getenv('CAMERA_HEIGHT', '480'))
    camera_fps: int = int(os.getenv('CAMERA_FPS', '30'))
    scan_timeout: int = int(os.getenv('SCAN_TIMEOUT', '30'))
    
    # API Configuration
    openfoodfacts_url: str = "https://world.openfoodfacts.org/api/v0/product/"
    api_timeout: int = int(os.getenv('API_TIMEOUT', '5'))
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    api_verify_ssl: bool = os.getenv('API_VERIFY_SSL', 'true').lower() == 'true'
    
    # UI Configuration
    window_width: int = int(os.getenv('WINDOW_WIDTH', '400'))
    window_height: int = int(os.getenv('WINDOW_HEIGHT', '700'))
    window_fullscreen: bool = os.getenv('WINDOW_FULLSCREEN', 'false').lower() == 'true'
    theme_mode: str = os.getenv('THEME_MODE', 'light')
    
    # Feature Flags
    enable_barcode_scanning: bool = os.getenv('ENABLE_BARCODE_SCANNING', 'true').lower() == 'true'
    enable_shopping_list: bool = os.getenv('ENABLE_SHOPPING_LIST', 'true').lower() == 'true'
    enable_statistics: bool = os.getenv('ENABLE_STATISTICS', 'true').lower() == 'true'
    
    # Validation Configuration
    max_item_name_length: int = int(os.getenv('MAX_ITEM_NAME_LENGTH', '100'))
    max_barcode_length: int = int(os.getenv('MAX_BARCODE_LENGTH', '50'))
    days_before_expiry_warning: int = int(os.getenv('DAYS_BEFORE_EXPIRY_WARNING', '3'))
    
    def validate(self) -> bool:
        """Validate settings"""
        errors = []
        
        if self.enable_shopping_list and not (self.bring_email and self.bring_password):
            errors.append("Bring credentials required when shopping list is enabled")
        
        if self.connection_pool_size < 1:
            errors.append("Connection pool size must be at least 1")
        
        if self.api_timeout < 1:
            errors.append("API timeout must be at least 1 second")
        
        if errors:
            for error in errors:
                print(f"Configuration Error: {error}")
            return False
        
        return True
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    def get_database_path(self) -> str:
        """Get full database path"""
        if os.path.isabs(self.database_path):
            return self.database_path
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), self.database_path)

# Create global settings instance
settings = Settings()

# Validate settings on import
if not settings.validate():
    print("Warning: Configuration validation failed. Some features may not work correctly.")