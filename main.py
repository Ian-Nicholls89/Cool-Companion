"""
Fridge Inventory Application - Main Entry Point
Refactored with proper architecture, security, and best practices.
Now using PySide6 instead of Flet for better compatibility with Raspberry Pi.
"""
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
import logging
from dotenv import load_dotenv
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables (override existing env vars)
load_dotenv(override=True)

# Configure logging
from loguru import logger
logger.remove()  # Remove default handler

# Console logging (with colors)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# File logging (without colors, with rotation)
logger.add(
    "logs/cool-companion_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",  # More verbose for file logs
    rotation="00:00",  # Rotate daily at midnight
    retention="30 days",  # Keep logs for 30 days
    compression="zip"  # Compress old logs
)

# Perform system compatibility check before importing heavy dependencies
from utils.system_check import check_and_report_system, SystemCompatibilityChecker

logger.info("=" * 60)
logger.info("Cool Companion - Fridge Inventory Application")
logger.info("=" * 60)

# Import configuration
from config.settings import settings

# Import database and models
from models.database import db_pool, init_database
from models.item import Item

# Import repositories
from repositories.item_repository import ItemRepository
from repositories.barcode_repository import BarcodeRepository

# Import services
from services.barcode_service import BarcodeService
from services.shopping_service import ShoppingListService
from services.inventory_service import InventoryService
from services.camera_service import CameraService

# Import views
from views.main_window import MainWindow

# Import UI theme
from components.theme_qt import UITheme

# Check system compatibility (can be skipped for development)
if settings.skip_system_checks:
    logger.info("System checks skipped (SKIP_SYSTEM_CHECKS=true)")
else:
    if not check_and_report_system():
        logger.warning("System compatibility issues detected - attempting to continue with fallbacks")

if settings.statement:
    for line in settings.statement:
        logger.warning(line)

# Application constants
BACKGROUND_TASK_INTERVAL_MS = 86400000  # milliseconds - interval for background cleanup tasks (24 hours)

class FridgeInventoryApp:
    """Main application class with dependency injection."""

    def __init__(self, qt_app: QApplication):
        """Initialize application with all dependencies.

        Args:
            qt_app: QApplication instance
        """
        logger.info("Initializing Cool Companion...")

        self.qt_app = qt_app

        # Check if running on Raspberry Pi and log system info
        if SystemCompatibilityChecker.is_raspberry_pi():
            logger.info("Detected Raspberry Pi - optimizations enabled")

        # Enumerate available cameras at startup
        logger.info("Enumerating available cameras...")
        from services.camera_service import enumerate_cameras
        self.available_cameras = enumerate_cameras()
        logger.info(f"Found {len(self.available_cameras)} camera(s): {self.available_cameras}")

        # Validate settings (after logger is initialized)
        validation_errors = settings.get_validation_errors()
        if validation_errors:
            logger.warning("Settings validation failed:")
            for error in validation_errors:
                logger.warning(f"  - {error}")
            logger.warning("Some features may not work correctly")

        # Initialize database
        logger.info("Initializing database...")
        init_database()

        # Initialize repositories
        self.item_repository = ItemRepository(db_pool)
        self.barcode_repository = BarcodeRepository(db_pool)

        # Initialize services
        self.barcode_service = BarcodeService(
            barcode_repository=self.barcode_repository,
            settings=settings
        )

        self.shopping_service = ShoppingListService(settings=settings)

        self.camera_service = CameraService(
            camera_index=settings.camera_index,
            settings=settings
        )

        self.inventory_service = InventoryService(
            item_repository=self.item_repository,
            barcode_service=self.barcode_service,
            shopping_service=self.shopping_service
        )

        # Start camera keep-alive in background if barcode scanning is enabled
        if settings.enable_barcode_scanning and len(self.available_cameras) > 0:
            logger.info("Starting camera keep-alive mode...")
            try:
                self.camera_service.start_keep_alive()
            except Exception as e:
                logger.warning(f"Failed to start camera keep-alive: {e}")

        logger.info("Cool Companion initialized successfully!")
    
    def start(self):
        """Start the application."""
        try:
            # Check system compatibility (unless skipped for development)
            if not settings.skip_system_checks:
                from utils.system_check import check_gl_context_for_qt
                # Note: We don't need GL context for Qt as it handles this internally
                logger.info("Using Qt's built-in rendering - no manual GL check needed")
            else:
                logger.info("System checks skipped (SKIP_SYSTEM_CHECKS=true)")

            # Apply theme
            UITheme.apply_to_app(self.qt_app)

            # Set application icon
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
            if os.path.exists(icon_path):
                from PySide6.QtGui import QIcon
                self.qt_app.setWindowIcon(QIcon(icon_path))

            # Initialize main window with dependencies
            self.main_window = MainWindow(
                inventory_service=self.inventory_service,
                item_repository=self.item_repository,
                barcode_service=self.barcode_service,
                shopping_service=self.shopping_service,
                camera_service=self.camera_service,
                settings=settings,
                available_cameras=self.available_cameras
            )

            # Show the window
            self.main_window.show()

            # Log successful startup
            logger.info("Application started successfully")

            # Show welcome message if first run
            if self._is_first_run():
                self.main_window.show_welcome_dialog()

            # Start background tasks using QTimer
            from PySide6.QtCore import QTimer
            self.background_timer = QTimer()
            self.background_timer.timeout.connect(self._background_tasks)
            self.background_timer.start(BACKGROUND_TASK_INTERVAL_MS)

        except Exception as e:
            logger.error(f"Error starting application: {e}")
            QMessageBox.critical(
                None, "Startup Error",
                f"Failed to start application:\n\n{str(e)}"
            )
            sys.exit(1)


    def _is_first_run(self) -> bool:
        """Check if this is the first run of the application.

        Returns:
            True if first run, False otherwise
        """
        items = self.item_repository.get_all()
        return len(items) == 0

    def _background_tasks(self):
        """Run background tasks periodically."""
        try:
            # Clean up old barcode cache entries (runs every 24 hours via QTimer)
            deleted = self.barcode_repository.cleanup_old_entries(days=365)
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old barcode cache entries")

        except Exception as e:
            logger.error(f"Error in background task: {e}")
    
    def cleanup(self):
        """Cleanup resources on application exit."""
        logger.info("Cleaning up application resources...")

        # Stop background timer
        if hasattr(self, 'background_timer'):
            try:
                self.background_timer.stop()
            except Exception as e:
                logger.debug(f"Error stopping background timer: {e}")

        # Stop camera service (stop keep-alive first, then camera)
        if hasattr(self, 'camera_service'):
            try:
                logger.info("Stopping camera service...")
                self.camera_service.stop_keep_alive()
                self.camera_service.stop_camera()
                logger.info("Camera service stopped")
            except Exception as e:
                logger.error(f"Error stopping camera service: {e}")

        # Close database connections
        try:
            db_pool.close_all()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

        logger.info("Application cleanup complete")


def run_app():
    """Run the Fridge Inventory application."""
    app = None
    qt_app = None

    try:
        # High DPI scaling is enabled by default in Qt6
        # (Removed deprecated Qt.AA_EnableHighDpiScaling and Qt.AA_UseHighDpiPixmaps)

        # Create Qt application
        qt_app = QApplication(sys.argv)
        qt_app.setApplicationName("Cool Companion")
        qt_app.setOrganizationName("Cool Companion")

        # Create application instance
        app = FridgeInventoryApp(qt_app)

        # Start the application
        app.start()

        # Run event loop
        exit_code = qt_app.exec()

        logger.info("Application exited normally")
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if qt_app:
            QMessageBox.critical(None, "Fatal Error", f"Application error:\n\n{str(e)}")
        sys.exit(1)
    finally:
        if app:
            app.cleanup()

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        sys.exit(1)
    
    # Run application
    run_app()