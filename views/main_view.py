"""Main view for the Fridge Inventory application."""
import flet
from flet import Page, Column, Row, ListView, Text, TextField, ElevatedButton, IconButton, Icons, BottomSheet, Container, Card, Chip, Badge, AlertDialog, TextButton, SnackBar, DatePicker
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List
from models.item import Item
from services.inventory_service import InventoryService
from services.barcode_service import BarcodeService
from services.shopping_service import ShoppingListService
from services.camera_service import CameraService
from repositories.item_repository import ItemRepository
from components.theme import UITheme
from utils.formatters import DateFormatter, QuantityFormatter
from config.settings import settings

logger = logging.getLogger(__name__)

class MainView:
    """Main view for the application."""
    
    def __init__(
        self,
        page: Page,
        inventory_service: InventoryService,
        item_repository: ItemRepository,
        barcode_service: BarcodeService,
        shopping_service: ShoppingListService,
        camera_service: CameraService,
        settings,
        available_cameras: list = None
    ):
        """Initialize main view.
        
        Args:
            page: Flet page
            inventory_service: Inventory service
            item_repository: Item repository
            barcode_service: Barcode service
            shopping_service: Shopping list service
            camera_service: Camera service
            settings: Application settings
            available_cameras: List of tuples (index, name) for available cameras
        """
        self.page = page
        self.inventory_service = inventory_service
        self.item_repository = item_repository
        self.barcode_service = barcode_service
        self.shopping_service = shopping_service
        self.camera_service = camera_service
        self.settings = settings
        self.available_cameras = available_cameras or []
        
        # UI components
        self.items_list_view = None
        self.add_sheet = None
        self.item_name_field = None
        self.expiry_date_field = None
        self.barcode_field = None
        self.quantity_field = None
        
        # Initialize date picker
        self.page.date_picker = DatePicker(
            first_date=datetime.now(),
            last_date=datetime.now() + timedelta(days=1825),
            on_change=self._on_date_picked
        )
    
    async def build(self):
        """Build and display the main view."""
        try:
            # Create UI components
            self._create_form_fields()
            self._create_items_list()
            
            # Create floating action button at bottom center
            fab = Container(
                content=flet.FloatingActionButton(
                    icon=Icons.ADD,
                    on_click=lambda e: self._show_add_sheet(),
                    bgcolor=UITheme.PRIMARY,
                    tooltip="Add food item",
                ),
                alignment=flet.alignment.center,
            )
            
            # Build main layout with FAB at bottom
            self.page.add(
                Column([
                    self._build_header(),
                    flet.Divider(height=1, color=UITheme.PRIMARY_LIGHT),
                    self._build_stats_section(),
                    flet.Divider(height=1),
                    Text("Your Items:", style=flet.TextThemeStyle.HEADLINE_SMALL),
                    self.items_list_view,
                    Container(
                        content=fab,
                        padding=flet.padding.only(top=10, bottom=10),
                    ),
                ], expand=True, spacing=UITheme.SPACING_MD)
            )
            
            # Add overlays
            self.page.overlay.append(self.page.date_picker)
            
            # Load initial data
            await self._refresh_items_list()
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error building main view: {e}")
            self._show_error("Failed to load application", str(e))
    
    def _create_form_fields(self):
        """Create form input fields."""
        self.item_name_field = TextField(
            label="Item Name",
            expand=True,
            border_color=UITheme.PRIMARY,
            focused_border_color=UITheme.PRIMARY_VARIANT,
        )
        
        self.expiry_date_field = TextField(
            label="Expiry Date (YYYY-MM-DD)",
            expand=True,
            read_only=True,
            border_color=UITheme.PRIMARY,
            focused_border_color=UITheme.PRIMARY_VARIANT,
        )
        
        self.barcode_field = TextField(
            label="Barcode (optional)",
            expand=True,
            on_submit=self._on_barcode_submit,
            border_color=UITheme.PRIMARY,
            focused_border_color=UITheme.PRIMARY_VARIANT,
        )
        
        self.quantity_field = TextField(
            label="Quantity",
            value="1",
            width=100,
            keyboard_type=flet.KeyboardType.NUMBER,
            border_color=UITheme.PRIMARY,
            focused_border_color=UITheme.PRIMARY_VARIANT,
        )
    
    def _create_items_list(self):
        """Create items list view."""
        self.items_list_view = ListView(
            expand=1,
            spacing=UITheme.SPACING_SM,
            padding=UITheme.SPACING_MD
        )
    
    def _build_header(self) -> Row:
        """Build header with logo, title, and settings button."""
        import os
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
        
        return Row([
            Container(
                flet.Image(
                    src=logo_path,
                    width=50,
                    height=50,
                    fit=flet.ImageFit.CONTAIN,
                ) if os.path.exists(logo_path) else Container(),
                expand=1,
                alignment=flet.alignment.center_left
            ),
            Container(
                Text("Cool Companion", size=36, weight=flet.FontWeight.W_500, font_family="Winter-City", color=UITheme.PRIMARY),
                expand=1,
                alignment=flet.alignment.center
            ),
            Container(
                IconButton(
                    Icons.SETTINGS,
                    tooltip="Settings",
                    on_click=lambda e: self._show_settings_dialog(),
                    icon_color=UITheme.PRIMARY,
                    icon_size=32
                ),
                expand=1,
                alignment=flet.alignment.center_right
            ),
        ], alignment=flet.MainAxisAlignment.SPACE_BETWEEN)
    
    def _build_stats_section(self) -> Container:
        """Build statistics section."""
        stats = self.inventory_service.get_inventory_stats()
        
        return Container(
            content=Row([
                self._build_stat_card("Total", str(stats["total_items"]), Icons.INVENTORY_2, UITheme.PRIMARY),
                self._build_stat_card("Expiring", str(stats["expiring_soon_count"]), Icons.WARNING_AMBER, UITheme.WARNING),
                self._build_stat_card("Expired", str(stats["expired_count"]), Icons.ERROR_OUTLINE, UITheme.ERROR),
            ], alignment=flet.MainAxisAlignment.SPACE_AROUND),
            padding=UITheme.SPACING_SM
        )
    
    def _build_stat_card(self, title: str, value: str, icon: str, color: str) -> Card:
        """Build a statistics card."""
        return Card(
            content=Container(
                content=Column([
                    flet.Icon(icon, size=24, color=color),
                    Text(value, size=20, weight=flet.FontWeight.BOLD, color=color),
                    Text(title, size=11, color=UITheme.TEXT_SECONDARY),
                ], horizontal_alignment=flet.CrossAxisAlignment.CENTER, spacing=2),
                padding=UITheme.SPACING_SM,
                width=100,
            ),
            elevation=1,
        )
    
    async def _refresh_items_list(self):
        """Refresh the items list."""
        try:
            items = self.item_repository.get_all()
            self.items_list_view.controls.clear()
            
            if not items:
                self.items_list_view.controls.append(
                    Container(
                        content=Column([
                            flet.Icon(Icons.INVENTORY_2, size=64, color=UITheme.TEXT_DISABLED),
                            Text("Your fridge is empty!", size=20, weight=flet.FontWeight.W_600, color=UITheme.TEXT_SECONDARY),
                            Text("Add your first item to get started", size=14, color=UITheme.TEXT_DISABLED),
                            ElevatedButton(
                                "Add Item",
                                icon=Icons.ADD,
                                on_click=lambda e: self._show_add_sheet(),
                                bgcolor=UITheme.PRIMARY,
                                color=UITheme.TEXT_ON_PRIMARY,
                            )
                        ], horizontal_alignment=flet.CrossAxisAlignment.CENTER, spacing=UITheme.SPACING_MD),
                        padding=UITheme.SPACING_XL,
                        alignment=flet.alignment.center,
                    )
                )
            else:
                for item in items:
                    self.items_list_view.controls.append(self._build_item_card(item))
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error refreshing items list: {e}")
            self._show_error("Failed to load items", str(e))
    
    def _build_item_card(self, item: Item) -> Card:
        """Build an item card."""
        # Determine status colors
        bg_color, text_color, status_icon = UITheme.get_status_colors(item.status)
        
        # Build item name with quantity
        item_name = Text(
            item.display_name,
            size=16,
            weight=flet.FontWeight.W_600,
            color=UITheme.TEXT_PRIMARY
        )
        
        # Status chip
        status_text = DateFormatter.format_expiry_status(item.expiry_date)
        status_chip = Chip(
            label=Text(status_text, size=11),
            leading=flet.Icon(status_icon, size=16),
            bgcolor=bg_color,
            label_style=flet.TextStyle(color=text_color)
        )
        
        # Opened indicator
        chips_row = Row([status_chip], spacing=4)
        if item.is_opened:
            opened_text = f"Opened {DateFormatter.format_date_short(item.opened_date)}" if item.opened_date else "Opened"
            chips_row.controls.append(
                Chip(
                    label=Text(opened_text, size=11),
                    leading=flet.Icon(Icons.OPEN_IN_NEW, size=14),
                    bgcolor=UITheme.OPENED_BG,
                    label_style=flet.TextStyle(color=UITheme.OPENED_TEXT)
                )
            )
        
        # Expiry date
        expiry_text = Text(
            f"Best before: {DateFormatter.format_date(item.expiry_date, '%B %d, %Y')}",
            size=12,
            color=UITheme.TEXT_SECONDARY
        )
        
        # Action buttons
        actions = Row([
            IconButton(
                icon=Icons.INVENTORY if not item.is_opened else Icons.INVENTORY_2,
                on_click=lambda e, id=item.id: self._toggle_opened(id),
                tooltip="Mark as opened" if not item.is_opened else "Mark as unopened",
                icon_color=UITheme.PRIMARY,
                icon_size=20,
            ),
            IconButton(
                icon=Icons.ADD_SHOPPING_CART,
                on_click=lambda e, name=item.name: self._add_to_shopping_list(name),
                tooltip="Add to shopping list",
                icon_color=UITheme.SECONDARY,
                icon_size=20,
            ),
            IconButton(
                icon=Icons.DELETE_OUTLINE,
                on_click=lambda e, id=item.id, name=item.name: self._show_delete_dialog(id, name),
                tooltip="Remove item",
                icon_color=UITheme.ERROR,
                icon_size=20,
            ),
        ], spacing=0)
        
        return Card(
            content=Container(
                content=Row([
                    Column([
                        item_name,
                        chips_row,
                        expiry_text,
                    ], spacing=4, expand=True),
                    actions
                ], alignment=flet.MainAxisAlignment.SPACE_BETWEEN),
                padding=UITheme.SPACING_MD,
                bgcolor=bg_color,
                border_radius=UITheme.RADIUS_MD,
            ),
            elevation=2 if item.is_expired else 1,
        )
    
    def _show_add_sheet(self):
        """Show add item bottom sheet."""
        self.add_sheet = BottomSheet(
            Container(
                Column([
                    Row([self.item_name_field]),
                    Row([
                        self.expiry_date_field,
                        IconButton(
                            Icons.CALENDAR_MONTH,
                            tooltip="Pick a date",
                            on_click=lambda e: self.page.open(self.page.date_picker),
                            icon_color=UITheme.PRIMARY
                        ),
                    ]),
                    Row([
                        self.barcode_field,
                        ElevatedButton(
                            "Scan",
                            on_click=lambda e: self.page.run_task(self._scan_barcode),
                            bgcolor=UITheme.PRIMARY,
                            color=UITheme.TEXT_ON_PRIMARY,
                        ) if self.settings.enable_barcode_scanning else Container()
                    ]),
                    Row([
                        self.quantity_field,
                        ElevatedButton(
                            "Produce?",
                            on_click=lambda e: self._show_produce_selector(),
                            bgcolor=UITheme.SECONDARY,
                            color=UITheme.TEXT_ON_PRIMARY,
                            expand=True,
                        )
                    ]),
                    ElevatedButton(
                        "Add Item",
                        on_click=lambda e: self._add_item(),
                        icon=Icons.ADD,
                        bgcolor=UITheme.PRIMARY,
                        color=UITheme.TEXT_ON_PRIMARY,
                        expand=True,
                    ),
                ], spacing=UITheme.SPACING_MD),
                padding=UITheme.SPACING_LG,
            ),
            enable_drag=True,
            show_drag_handle=True,
        )
        
        self.page.open(self.add_sheet)
        self.page.update()
    
    def _on_date_picked(self, e):
        """Handle date picker selection."""
        if e.control.value:
            self.expiry_date_field.value = e.control.value.strftime("%Y-%m-%d")
            self.page.update()
    
    def _on_barcode_submit(self, e):
        """Handle barcode field submission."""
        if self.barcode_field.value:
            product_info = self.barcode_service.lookup_product_sync(self.barcode_field.value)
            if product_info:
                self.item_name_field.value = product_info["name"]
                self._show_success(f"Found: {product_info['name']}")
            else:
                self._show_info("Product not found. Please enter name manually.")
            self.page.update()
    
    async def _scan_barcode(self):
        """Scan barcode using camera with live feed."""
        scan_dialog = None
        countdown_text = None
        camera_image = None
        scan_cancelled = False
        
        try:
            # Create UI elements
            countdown_text = Text("Time remaining: 30s", size=18, weight=flet.FontWeight.BOLD, color=UITheme.PRIMARY)
            camera_image = flet.Image(
                src_base64="",
                width=640,
                height=480,
                fit=flet.ImageFit.CONTAIN,
            )
            
            # Create scanning dialog with live camera feed
            scan_dialog = AlertDialog(
                modal=True,
                title=Text("Scanning for Barcode", weight=flet.FontWeight.BOLD),
                content=Container(
                    content=Column([
                        Text("Point your camera at a barcode", size=14, color=UITheme.TEXT_SECONDARY),
                        Container(height=5),
                        countdown_text,
                        Container(height=10),
                        camera_image,
                    ], horizontal_alignment=flet.CrossAxisAlignment.CENTER, spacing=5),
                    padding=20,
                    width=680,
                ),
                actions=[
                    TextButton("Cancel", on_click=lambda e: self._cancel_scan(scan_dialog)),
                ],
            )
            
            self.page.dialog = scan_dialog
            self.page.open(scan_dialog)
            self.page.update()
            
            # Give UI time to render
            await asyncio.sleep(0.2)
            
            # Frame callback to update UI with camera feed
            def frame_callback(frame_base64: str, remaining: int):
                if scan_cancelled:
                    return
                try:
                    camera_image.src_base64 = frame_base64
                    countdown_text.value = f"Time remaining: {remaining}s"
                    self.page.update()
                except Exception as e:
                    logger.error(f"Error updating camera feed: {e}")
            
            # Run scan in executor with frame callback
            loop = asyncio.get_event_loop()
            barcode = await loop.run_in_executor(
                None,
                lambda: self.camera_service.scan_barcode_sync(timeout=30, frame_callback=frame_callback)
            )
            
            # Cancel scan
            scan_cancelled = True
            
            # Close dialog
            if scan_dialog:
                self.page.close(scan_dialog)
                self.page.update()
            
            # Reopen the add sheet
            if self.add_sheet:
                self.page.open(self.add_sheet)
            
            if barcode:
                self.barcode_field.value = barcode
                self._show_success(f"Barcode scanned: {barcode}")
                
                # Try to lookup product info
                product_info = self.barcode_service.lookup_product_sync(barcode)
                if product_info:
                    self.item_name_field.value = product_info["name"]
                    self._show_success(f"Found: {product_info['name']}")
                else:
                    self._show_info("Product not found. Please enter name manually.")
            else:
                self._show_info("No barcode detected. Please try again.")
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error scanning barcode: {e}")
            scan_cancelled = True
            if scan_dialog:
                self.page.close(scan_dialog)
            # Reopen the add sheet even on error
            if self.add_sheet:
                self.page.open(self.add_sheet)
            self._show_error("Scan Error", str(e))
            self.page.update()
    
    def _cancel_scan(self, dialog):
        """Cancel barcode scanning."""
        try:
            self.camera_service.stop_camera()
            self.page.close(dialog)
            # Reopen the add sheet
            if self.add_sheet:
                self.page.open(self.add_sheet)
            self._show_info("Scan cancelled")
            self.page.update()
        except Exception as e:
            logger.error(f"Error cancelling scan: {e}")
    
    def _show_produce_selector(self):
        """Show produce item selector."""
        produce_items = self.barcode_service.get_produce_items()
        
        produce_list = ListView(
            [
                flet.ListTile(
                    title=Text(name, size=14),
                    on_click=lambda e, b=barcode, n=name: self._select_produce(b, n),
                    hover_color=UITheme.PRIMARY_LIGHT,
                )
                for barcode, name in produce_items
            ],
            height=400,
        )
        
        dialog = AlertDialog(
            modal=True,
            title=Text("Select Produce Item", weight=flet.FontWeight.BOLD),
            content=Container(content=produce_list, width=300),
            actions=[
                TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
            ],
        )
        
        self.page.dialog = dialog
        self.page.open(dialog)
        self.page.update()
    
    def _select_produce(self, barcode: str, name: str):
        """Select a produce item."""
        self.barcode_field.value = barcode
        self.item_name_field.value = name
        self.page.close(self.page.dialog)
        self.page.open(self.add_sheet)
        self.page.update()
    
    def _add_item(self):
        """Add new item to inventory."""
        try:
            # Validate inputs
            if not self.item_name_field.value or not self.expiry_date_field.value:
                self._show_error("Validation Error", "Please fill in all required fields")
                return
            
            # Create item
            item = Item(
                name=self.item_name_field.value,
                expiry_date=date.fromisoformat(self.expiry_date_field.value),
                barcode=self.barcode_field.value if self.barcode_field.value else None,
                quantity=int(self.quantity_field.value) if self.quantity_field.value else 1
            )
            
            # Save item
            saved_item = self.inventory_service.add_item(item)
            
            if saved_item:
                # Clear form
                self.item_name_field.value = ""
                self.expiry_date_field.value = ""
                self.barcode_field.value = ""
                self.quantity_field.value = "1"
                
                # Close sheet and refresh
                self.page.close(self.add_sheet)
                self.page.run_task(self._refresh_items_list)
                
                self._show_success(f"Added {saved_item.display_name}")
            else:
                self._show_error("Error", "Failed to add item")
                
        except ValueError as e:
            self._show_error("Validation Error", str(e))
        except Exception as e:
            logger.error(f"Error adding item: {e}")
            self._show_error("Error", f"Failed to add item: {str(e)}")
    
    def _toggle_opened(self, item_id: int):
        """Toggle item opened status."""
        if self.inventory_service.toggle_opened_status(item_id):
            self.page.run_task(self._refresh_items_list)
            self._show_success("Item status updated")
        else:
            self._show_error("Error", "Failed to update item status")
    
    def _add_to_shopping_list(self, item_name: str):
        """Add item to shopping list."""
        if self.shopping_service.add_item_sync(item_name):
            self._show_success(f"Added '{item_name}' to shopping list")
        else:
            self._show_error("Error", "Failed to add to shopping list")
    
    def _show_delete_dialog(self, item_id: int, item_name: str):
        """Show delete confirmation dialog."""
        dialog = AlertDialog(
            modal=True,
            title=Text("Remove Item"),
            content=Text(f"Do you want to add '{item_name}' to your shopping list before removing?"),
            actions=[
                TextButton("Yes, add to list", on_click=lambda e: self._delete_item(item_id, True)),
                TextButton("No, just delete", on_click=lambda e: self._delete_item(item_id, False)),
                TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
            ],
        )
        
        self.page.dialog = dialog
        self.page.open(dialog)
        self.page.update()
    
    def _delete_item(self, item_id: int, add_to_shopping: bool):
        """Delete item from inventory."""
        self.page.close(self.page.dialog)
        
        if self.inventory_service.delete_and_restock_sync(item_id, add_to_shopping):
            self.page.run_task(self._refresh_items_list)
            self._show_success("Item removed successfully")
        else:
            self._show_error("Error", "Failed to remove item")
    
    def _show_success(self, message: str):
        """Show success message."""
        self.page.snack_bar = SnackBar(
            content=Row([
                flet.Icon(Icons.CHECK_CIRCLE, color=flet.Colors.WHITE, size=20),
                Text(message, color=flet.Colors.WHITE)
            ]),
            bgcolor=UITheme.SUCCESS,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _show_error(self, title: str, message: str):
        """Show error message."""
        self.page.snack_bar = SnackBar(
            content=Row([
                flet.Icon(Icons.ERROR_OUTLINE, color=flet.Colors.WHITE, size=20),
                Text(f"{title}: {message}", color=flet.Colors.WHITE)
            ]),
            bgcolor=UITheme.ERROR,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _show_info(self, message: str):
        """Show info message."""
        self.page.snack_bar = SnackBar(
            content=Row([
                flet.Icon(Icons.INFO_OUTLINE, color=flet.Colors.WHITE, size=20),
                Text(message, color=flet.Colors.WHITE)
            ]),
            bgcolor=UITheme.INFO,
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def _show_settings_dialog(self):
        """Show settings dialog for editing .env configuration."""
        # Create text fields for each setting
        bring_email_field = TextField(
            label="Bring Email",
            value=self.settings.bring_email,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        bring_password_field = TextField(
            label="Bring Password",
            value=self.settings.bring_password,
            password=True,
            can_reveal_password=True,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        # Use stored camera enumeration from startup
        # Create dropdown for camera selection
        camera_options = [
            flet.dropdown.Option(key=str(idx), text=name)
            for idx, name in self.available_cameras
        ]
        
        # If no cameras found, add a default option
        if not camera_options:
            camera_options = [flet.dropdown.Option(key="0", text="Camera 0 (Default)")]
        
        camera_dropdown = flet.Dropdown(
            label="Camera Device",
            value=str(self.settings.camera_index),
            options=camera_options,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        database_path_field = TextField(
            label="Database Path",
            value=self.settings.database_path,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        api_timeout_field = TextField(
            label="API Timeout (seconds)",
            value=str(self.settings.api_timeout),
            keyboard_type=flet.KeyboardType.NUMBER,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        api_verify_ssl_switch = flet.Switch(
            label="Verify SSL Certificates (recommended)",
            value=self.settings.api_verify_ssl,
        )
        
        window_width_field = TextField(
            label="Window Width",
            value=str(self.settings.window_width),
            keyboard_type=flet.KeyboardType.NUMBER,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        window_height_field = TextField(
            label="Window Height",
            value=str(self.settings.window_height),
            keyboard_type=flet.KeyboardType.NUMBER,
            expand=True,
            border_color=UITheme.PRIMARY,
        )
        
        window_fullscreen_switch = flet.Switch(
            label="Fullscreen Mode",
            value=self.settings.window_fullscreen,
        )
        
        enable_barcode_switch = flet.Switch(
            label="Enable Barcode Scanning",
            value=self.settings.enable_barcode_scanning,
        )
        
        enable_shopping_switch = flet.Switch(
            label="Enable Shopping List",
            value=self.settings.enable_shopping_list,
        )
        
        def save_settings(e):
            """Save settings to .env file."""
            try:
                import os
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
                
                # Read existing .env content
                env_lines = []
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        env_lines = f.readlines()
                
                # Update or add settings
                settings_map = {
                    'BRING_EMAIL': bring_email_field.value,
                    'BRING_PASSWORD': bring_password_field.value,
                    'CAMERA_INDEX': camera_dropdown.value,
                    'DATABASE_PATH': database_path_field.value,
                    'API_TIMEOUT': api_timeout_field.value,
                    'WINDOW_WIDTH': window_width_field.value,
                    'WINDOW_HEIGHT': window_height_field.value,
                    'WINDOW_FULLSCREEN': 'true' if window_fullscreen_switch.value else 'false',
                    'ENABLE_BARCODE_SCANNING': 'true' if enable_barcode_switch.value else 'false',
                    'ENABLE_SHOPPING_LIST': 'true' if enable_shopping_switch.value else 'false',
                    'API_VERIFY_SSL': 'true' if api_verify_ssl_switch.value else 'false',
                }
                
                # Update existing lines or collect new ones
                updated_keys = set()
                new_lines = []
                
                for line in env_lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key = line.split('=')[0].strip()
                        if key in settings_map:
                            new_lines.append(f"{key}={settings_map[key]}\n")
                            updated_keys.add(key)
                        else:
                            new_lines.append(line + '\n')
                    else:
                        new_lines.append(line + '\n')
                
                # Add new settings that weren't in the file
                for key, value in settings_map.items():
                    if key not in updated_keys:
                        new_lines.append(f"{key}={value}\n")
                
                # Write back to .env file
                with open(env_path, 'w') as f:
                    f.writelines(new_lines)
                
                self.page.close(dialog)
                self._show_success("Settings saved! Please restart the app for changes to take effect.")
                
            except Exception as ex:
                logger.error(f"Error saving settings: {ex}")
                self._show_error("Save Error", str(ex))
        
        dialog = AlertDialog(
            modal=True,
            title=Text("Settings", weight=flet.FontWeight.BOLD),
            content=Container(
                content=Column([
                    Text("Bring Shopping List", weight=flet.FontWeight.W_500, size=14),
                    bring_email_field,
                    bring_password_field,
                    flet.Divider(),
                    Text("Camera", weight=flet.FontWeight.W_500, size=14),
                    camera_dropdown,
                    flet.Divider(),
                    Text("Database", weight=flet.FontWeight.W_500, size=14),
                    database_path_field,
                    flet.Divider(),
                    Text("API", weight=flet.FontWeight.W_500, size=14),
                    api_timeout_field,
                    api_verify_ssl_switch,
                    flet.Divider(),
                    Text("Window", weight=flet.FontWeight.W_500, size=14),
                    Row([window_width_field, window_height_field]),
                    window_fullscreen_switch,
                    flet.Divider(),
                    Text("Features", weight=flet.FontWeight.W_500, size=14),
                    enable_barcode_switch,
                    enable_shopping_switch,
                ], spacing=10, scroll=flet.ScrollMode.AUTO),
                width=400,
                height=500,
            ),
            actions=[
                TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                ElevatedButton(
                    "Save",
                    on_click=save_settings,
                    bgcolor=UITheme.PRIMARY,
                    color=UITheme.TEXT_ON_PRIMARY,
                ),
            ],
        )
        
        self.page.dialog = dialog
        self.page.open(dialog)
        self.page.update()
    
    async def show_welcome_dialog(self):
        """Show welcome dialog for first-time users."""
        dialog = AlertDialog(
            modal=True,
            title=Text("Welcome to Cool Companion!", weight=flet.FontWeight.BOLD),
            content=Column([
                Text("Track your food items and reduce waste!", size=14),
                Text("", size=4),
                Text("Features:", weight=flet.FontWeight.W_500),
                Text("• Scan barcodes to add items quickly", size=12),
                Text("• Track expiry dates with visual indicators", size=12),
                Text("• Sync with Bring! shopping list", size=12),
                Text("• Get notified about expiring items", size=12),
            ], tight=True),
            actions=[
                TextButton("Get Started", on_click=lambda e: self.page.close(dialog)),
            ],
        )
        
        self.page.dialog = dialog
        self.page.open(dialog)
        self.page.update()
