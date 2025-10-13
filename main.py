"""
Fridge Inventory Application - Main Entry Point
Refactored with proper architecture, security, and best practices.
"""
import flet
from flet import Page, Icons
import asyncio
import logging
from dotenv import load_dotenv
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
from loguru import logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

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
from views.main_view import MainView

# Import UI theme
from components.theme import UITheme

class FridgeInventoryApp:
    """Main application class with dependency injection."""
    
    def __init__(self):
        """Initialize application with all dependencies."""
        logger.info("Initializing Cool Companion...")
        
        # Enumerate available cameras at startup
        logger.info("Enumerating available cameras...")
        from services.camera_service import enumerate_cameras
        self.available_cameras = enumerate_cameras()
        logger.info(f"Found {len(self.available_cameras)} camera(s): {self.available_cameras}")
        
        # Validate settings
        if not settings.validate():
            logger.warning("Settings validation failed - some features may not work")
        
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
        
        logger.info("Cool Companion initialized successfully!")
    
    async def main(self, page: Page):
        """Main application entry point.
        
        Args:
            page: Flet page object
        """
        try:
            # Apply theme
            UITheme.apply_to_page(page)
            
            # Set page properties
            page.title = "Cool Companion"
            
            # Apply fullscreen setting if enabled
            if settings.window_fullscreen:
                page.window_full_screen = True
            else:
                page.window_width = settings.window_width
                page.window_height = settings.window_height
            
            page.vertical_alignment = "start"
            
            # Set window icon
            import os
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
            if os.path.exists(icon_path):
                page.window.icon = icon_path
            
            # Initialize main view with dependencies
            main_view = MainView(
                page=page,
                inventory_service=self.inventory_service,
                item_repository=self.item_repository,
                barcode_service=self.barcode_service,
                shopping_service=self.shopping_service,
                camera_service=self.camera_service,
                settings=settings,
                available_cameras=self.available_cameras
            )
            
            # Build and display UI
            await main_view.build()
            
            # Log successful startup
            logger.info("Application started successfully")
            
            # Show welcome message if first run
            if await self._is_first_run():
                await main_view.show_welcome_dialog()
            
            # Start background tasks
            asyncio.create_task(self._background_tasks())
            
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            if page:
                page.add(
                    flet.Container(
                        content=flet.Column([
                            flet.Icon(Icons.ERROR_OUTLINE, size=64, color=flet.Colors.RED_700),
                            flet.Text(
                                "Failed to start application",
                                size=24,
                                weight=flet.FontWeight.BOLD,
                                color=flet.Colors.RED_700
                            ),
                            flet.Text(
                                str(e),
                                size=14,
                                color=flet.Colors.GREY_700
                            ),
                            flet.ElevatedButton(
                                "Retry",
                                on_click=lambda _: asyncio.create_task(self.main(page))
                            )
                        ], horizontal_alignment=flet.CrossAxisAlignment.CENTER),
                        padding=50,
                        alignment=flet.alignment.center
                    )
                )
                page.update()
    
    async def _is_first_run(self) -> bool:
        """Check if this is the first run of the application.
        
        Returns:
            True if first run, False otherwise
        """
        items = self.item_repository.get_all()
        return len(items) == 0
    
    async def _background_tasks(self):
        """Run background tasks periodically."""
        while True:
            try:
                # Clean up old barcode cache entries (every 24 hours)
                await asyncio.sleep(86400)  # 24 hours
                deleted = self.barcode_repository.cleanup_old_entries(days=365)
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old barcode cache entries")
                    
            except Exception as e:
                logger.error(f"Error in background task: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    def cleanup(self):
        """Cleanup resources on application exit."""
        logger.info("Cleaning up application resources...")
        
        # Close database connections
        db_pool.close_all()
        
        # Stop any running services (synchronously since no event loop)
        if hasattr(self, 'camera_service'):
            try:
                # Try to stop camera service if event loop exists
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.camera_service.stop())
            except RuntimeError:
                # No event loop, skip async cleanup
                logger.debug("No event loop available for async cleanup")
        
        logger.info("Application cleanup complete")

def run_app():
    """Run the Fridge Inventory application."""
    try:
        # Create application instance
        app = FridgeInventoryApp()
        
        # Run Flet app
        flet.app(
            target=lambda page: asyncio.run(app.main(page)),
            view=flet.AppView.FLET_APP if not settings.is_production() else flet.AppView.WEB_BROWSER,
            port=8550 if settings.is_production() else 0,
            host="0.0.0.0" if settings.is_production() else None
        )
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if 'app' in locals():
            app.cleanup()

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required")
        sys.exit(1)
    
    # Run application
    run_app()