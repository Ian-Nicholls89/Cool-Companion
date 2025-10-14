"""
Fridge Inventory Application - Main Entry Point
Refactored with proper architecture, security, and best practices.
Optimized for Raspberry Pi 3 Model B with GL context validation.
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
from views.main_view import MainView

# Import UI theme
from components.theme import UITheme

# Check system compatibility (can be skipped for development)
if settings.skip_system_checks:
    logger.info("System checks skipped (SKIP_SYSTEM_CHECKS=true)")
else:
    if not check_and_report_system():
        logger.warning("System compatibility issues detected - attempting to continue with fallbacks")

if settings.statement:
    for line in settings.statement:
        logger.warning(line)

class FridgeInventoryApp:
    """Main application class with dependency injection."""
    
    def __init__(self):
        """Initialize application with all dependencies."""
        logger.info("Initializing Cool Companion...")
        
        # Check if running on Raspberry Pi and log system info
        if SystemCompatibilityChecker.is_raspberry_pi():
            logger.info("Detected Raspberry Pi - optimizations enabled")
        
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
            # Check GL context before proceeding (unless skipped for development)
            if not settings.skip_system_checks:
                gl_ok, gl_error = SystemCompatibilityChecker.check_gl_context()
                if not gl_ok:
                    logger.error(f"GL Context Error: {gl_error}")
                    await self._show_gl_error_dialog(page, gl_error)
                    return
            else:
                logger.info("GL context check skipped (SKIP_SYSTEM_CHECKS=true)")
            
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
    
    async def _show_gl_error_dialog(self, page: Page, error_message: str):
        """Show GL context error dialog with troubleshooting steps.
        
        Args:
            page: Flet page object
            error_message: The GL error message
        """
        page.title = "Cool Companion - System Error"
        
        # Get recommendations
        recommendations = SystemCompatibilityChecker.get_optimization_recommendations()
        
        # Build recommendations text
        rec_text = "\n".join([f"• {rec}" for rec in recommendations]) if recommendations else "No specific recommendations available."
        
        error_dialog = flet.Container(
            content=flet.Column([
                flet.Icon(Icons.ERROR_OUTLINE, size=80, color=flet.Colors.RED_700),
                flet.Text(
                    "Unable to Create GL Context",
                    size=28,
                    weight=flet.FontWeight.BOLD,
                    color=flet.Colors.RED_700,
                    text_align=flet.TextAlign.CENTER
                ),
                flet.Divider(height=20, color=flet.Colors.TRANSPARENT),
                flet.Text(
                    "The application cannot start because OpenGL context creation failed.",
                    size=16,
                    color=flet.Colors.GREY_800,
                    text_align=flet.TextAlign.CENTER
                ),
                flet.Divider(height=10, color=flet.Colors.TRANSPARENT),
                flet.Container(
                    content=flet.Text(
                        error_message,
                        size=14,
                        color=flet.Colors.RED_600,
                        text_align=flet.TextAlign.CENTER,
                        italic=True
                    ),
                    bgcolor=flet.Colors.RED_50,
                    padding=15,
                    border_radius=8
                ),
                flet.Divider(height=20, color=flet.Colors.TRANSPARENT),
                flet.Text(
                    "Troubleshooting Steps:",
                    size=18,
                    weight=flet.FontWeight.BOLD,
                    color=flet.Colors.BLUE_700
                ),
                flet.Container(
                    content=flet.Column([
                        flet.Text(
                            "1. Enable GL Driver (Raspberry Pi):",
                            size=14,
                            weight=flet.FontWeight.BOLD
                        ),
                        flet.Text(
                            "   sudo raspi-config → Advanced Options → GL Driver → Enable",
                            size=13,
                            color=flet.Colors.GREY_700
                        ),
                        flet.Divider(height=10, color=flet.Colors.TRANSPARENT),
                        flet.Text(
                            "2. Install Required Libraries:",
                            size=14,
                            weight=flet.FontWeight.BOLD
                        ),
                        flet.Text(
                            "   sudo apt-get update",
                            size=13,
                            color=flet.Colors.GREY_700
                        ),
                        flet.Text(
                            "   sudo apt-get install libgles2-mesa libgles2-mesa-dev",
                            size=13,
                            color=flet.Colors.GREY_700
                        ),
                        flet.Divider(height=10, color=flet.Colors.TRANSPARENT),
                        flet.Text(
                            "3. Set Display Environment:",
                            size=14,
                            weight=flet.FontWeight.BOLD
                        ),
                        flet.Text(
                            "   export DISPLAY=:0",
                            size=13,
                            color=flet.Colors.GREY_700
                        ),
                        flet.Divider(height=10, color=flet.Colors.TRANSPARENT),
                        flet.Text(
                            "4. Enable Software Rendering (Fallback):",
                            size=14,
                            weight=flet.FontWeight.BOLD
                        ),
                        flet.Text(
                            "   export FLET_FORCE_SOFTWARE_RENDERING=1",
                            size=13,
                            color=flet.Colors.GREY_700
                        ),
                    ], spacing=5),
                    bgcolor=flet.Colors.BLUE_50,
                    padding=15,
                    border_radius=8
                ),
                flet.Divider(height=20, color=flet.Colors.TRANSPARENT),
                flet.Text(
                    "Additional Recommendations:",
                    size=16,
                    weight=flet.FontWeight.BOLD,
                    color=flet.Colors.GREEN_700
                ),
                flet.Container(
                    content=flet.Text(
                        rec_text,
                        size=13,
                        color=flet.Colors.GREY_700
                    ),
                    bgcolor=flet.Colors.GREEN_50,
                    padding=15,
                    border_radius=8
                ),
                flet.Divider(height=20, color=flet.Colors.TRANSPARENT),
                flet.Row([
                    flet.ElevatedButton(
                        "Retry",
                        icon=Icons.REFRESH,
                        on_click=lambda _: asyncio.create_task(self._retry_startup(page))
                    ),
                    flet.OutlinedButton(
                        "Exit",
                        icon=Icons.EXIT_TO_APP,
                        on_click=lambda _: page.window_close()
                    )
                ], alignment=flet.MainAxisAlignment.CENTER, spacing=10)
            ],
            horizontal_alignment=flet.CrossAxisAlignment.CENTER,
            scroll=flet.ScrollMode.AUTO,
            spacing=10),
            padding=30,
            alignment=flet.alignment.center,
            expand=True
        )
        
        page.add(error_dialog)
        page.update()
    
    async def _retry_startup(self, page: Page):
        """Retry application startup after user fixes GL issues.
        
        Args:
            page: Flet page object
        """
        page.clean()
        logger.info("Retrying application startup...")
        await self.main(page)
    
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
        
        # Determine view mode based on environment and system
        is_rpi = SystemCompatibilityChecker.is_raspberry_pi()
        view_mode = flet.AppView.FLET_APP
        
        if settings.is_production():
            view_mode = flet.AppView.WEB_BROWSER
        elif is_rpi and os.environ.get('FLET_FORCE_SOFTWARE_RENDERING') == '1':
            logger.info("Using software rendering mode for Raspberry Pi")
        
        # Run Flet app
        flet.app(
            target=lambda page: asyncio.run(app.main(page)),
            view=view_mode,
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