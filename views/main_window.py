"""Main window for the Fridge Inventory application using PySide6."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QDialog, QDateEdit, QSpinBox,
    QMessageBox, QDialogButtonBox, QGridLayout, QComboBox, QCheckBox,
    QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QDate, QTimer, Signal, QThread
from PySide6.QtGui import QIcon, QPixmap, QImage
import asyncio
import logging
import base64
from datetime import date, datetime, timedelta
from typing import Optional, List
import numpy as np

from models.item import Item
from services.inventory_service import InventoryService
from services.barcode_service import BarcodeService
from services.shopping_service import ShoppingListService
from services.camera_service import CameraService
from repositories.item_repository import ItemRepository
from components.theme_qt import UITheme
from utils.formatters import DateFormatter, QuantityFormatter
from config.settings import settings

logger = logging.getLogger(__name__)


class BarcodeScanWorker(QThread):
    """Worker thread for barcode scanning."""

    scan_complete = Signal(str)  # Emits barcode when found
    frame_ready = Signal(str, int)  # Emits (frame_base64, remaining_seconds)
    scan_failed = Signal(str)  # Emits error message
    camera_ready = Signal()  # Emits when camera is initialized and ready

    def __init__(self, camera_service):
        super().__init__()
        self.camera_service = camera_service
        self.timeout = 30
        self._running = True

    def run(self):
        """Run the scanning process."""
        try:
            # Emit camera ready signal after first frame (camera is initialized)
            first_frame = [True]

            def frame_callback(frame_base64: str, remaining: int):
                # Emit camera ready on first frame
                if first_frame[0]:
                    self.camera_ready.emit()
                    first_frame[0] = False

                # Emit frame for display in UI
                if self._running:
                    self.frame_ready.emit(frame_base64, remaining)

            # Stop flag to allow cancellation
            def should_stop():
                return not self._running

            barcode = self.camera_service.scan_barcode_sync(
                timeout=self.timeout,
                frame_callback=frame_callback,
                stop_flag=should_stop
            )

            if barcode and self._running:
                self.scan_complete.emit(barcode)
            elif self._running:
                self.scan_failed.emit("No barcode detected")

        except Exception as e:
            logger.error(f"Error in scan worker: {e}")
            if self._running:
                self.scan_failed.emit(str(e))

    def stop(self):
        """Stop the scanning process."""
        self._running = False
        # Don't stop the camera - let keep-alive handle it
        # The camera service will automatically resume keep-alive after scanning


class AddItemDialog(QDialog):
    """Dialog for adding a new item."""

    def __init__(self, parent, barcode_service, camera_service, settings):
        super().__init__(parent)
        self.barcode_service = barcode_service
        self.camera_service = camera_service
        self.settings = settings
        self.scan_worker = None

        self.setWindowTitle("Add Item")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout()
        layout.setSpacing(UITheme.SPACING_MD)

        # Item name field with produce button
        name_layout = QHBoxLayout()
        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Item Name *")
        name_layout.addWidget(self.name_field)

        produce_btn = QPushButton("Produce?")
        produce_btn.setProperty("styleClass", "secondary")
        produce_btn.clicked.connect(self._show_produce_selector)
        name_layout.addWidget(produce_btn)
        layout.addLayout(name_layout)

        # Expiry date field
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Expiry Date: *"))
        self.expiry_date_field = QDateEdit()
        self.expiry_date_field.setCalendarPopup(True)
        self.expiry_date_field.setDate(QDate.currentDate().addDays(7))
        self.expiry_date_field.setMinimumDate(QDate.currentDate())
        date_layout.addWidget(self.expiry_date_field)
        layout.addLayout(date_layout)

        # Barcode field with scan button
        barcode_layout = QHBoxLayout()
        self.barcode_field = QLineEdit()
        self.barcode_field.setPlaceholderText("Barcode (optional)")
        self.barcode_field.returnPressed.connect(self._on_barcode_submit)
        barcode_layout.addWidget(self.barcode_field)

        if self.settings.enable_barcode_scanning:
            scan_btn = QPushButton("Scan")
            scan_btn.setProperty("styleClass", "secondary")
            scan_btn.clicked.connect(self._scan_barcode)
            barcode_layout.addWidget(scan_btn)

        layout.addLayout(barcode_layout)

        # Quantity field
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Quantity:"))
        self.quantity_field = QSpinBox()
        self.quantity_field.setMinimum(1)
        self.quantity_field.setMaximum(999)
        self.quantity_field.setValue(1)
        qty_layout.addWidget(self.quantity_field)
        qty_layout.addStretch()
        layout.addLayout(qty_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Style the OK button as success
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("Add Item")
        ok_button.setProperty("styleClass", "success")

        layout.addWidget(button_box)

        self.setLayout(layout)

    def _on_barcode_submit(self):
        """Handle barcode field submission."""
        barcode = self.barcode_field.text().strip()
        if barcode:
            product_info = self.barcode_service.lookup_product_sync(barcode)
            if product_info:
                self.name_field.setText(product_info["name"])
                QMessageBox.information(
                    self, "Product Found", f"Found: {product_info['name']}"
                )
            else:
                QMessageBox.information(
                    self, "Product Not Found",
                    "Product not found. Please enter name manually."
                )

    def _scan_barcode(self):
        """Scan barcode using camera with live feed."""
        scan_dialog = QDialog(self)
        scan_dialog.setWindowTitle("Scanning for Barcode")
        scan_dialog.setModal(True)
        scan_dialog.setMinimumSize(680, 600)

        layout = QVBoxLayout()

        info_label = QLabel("Point your camera at a barcode")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        countdown_label = QLabel("Time remaining: 30s")
        countdown_label.setAlignment(Qt.AlignCenter)
        countdown_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(countdown_label)

        # Camera feed label
        camera_label = QLabel()
        camera_label.setAlignment(Qt.AlignCenter)
        camera_label.setMinimumSize(640, 480)
        camera_label.setStyleSheet("background-color: black; border: 2px solid #1976D2; color: white;")
        camera_label.setScaledContents(False)
        layout.addWidget(camera_label)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(scan_dialog.reject)
        layout.addWidget(cancel_btn)

        scan_dialog.setLayout(layout)

        # Show dialog first so user sees the loading state
        scan_dialog.show()
        QApplication.processEvents()  # Process events to show dialog immediately

        # Start scanning in background thread
        self.scan_worker = BarcodeScanWorker(self.camera_service)

        # Function called when camera is ready
        def on_camera_ready():
            countdown_label.setText("Time remaining: 30s")
            camera_label.setText("")

        # Function to update camera feed
        def update_frame(frame_base64: str, remaining: int):
            try:
                # Update countdown
                countdown_label.setText(f"Time remaining: {remaining}s")

                # Decode base64 image and display
                image_data = base64.b64decode(frame_base64)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)

                # Scale pixmap to fit the label while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    camera_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                camera_label.setPixmap(scaled_pixmap)
            except Exception as e:
                logger.error(f"Error updating camera feed: {e}")

        def on_scan_complete(barcode):
            scan_dialog.accept()
            self.barcode_field.setText(barcode)
            QMessageBox.information(self, "Success", f"Barcode scanned: {barcode}")

            # Try to lookup product info
            product_info = self.barcode_service.lookup_product_sync(barcode)
            if product_info:
                self.name_field.setText(product_info["name"])
                QMessageBox.information(
                    self, "Product Found", f"Found: {product_info['name']}"
                )

        def on_scan_failed(error):
            scan_dialog.reject()
            QMessageBox.warning(self, "Scan Failed", f"Failed to scan barcode: {error}")

        # Connect signals
        self.scan_worker.camera_ready.connect(on_camera_ready)
        self.scan_worker.frame_ready.connect(update_frame)
        self.scan_worker.scan_complete.connect(on_scan_complete)
        self.scan_worker.scan_failed.connect(on_scan_failed)
        self.scan_worker.start()

        result = scan_dialog.exec()

        if result == QDialog.Rejected and self.scan_worker:
            self.scan_worker.stop()
            self.scan_worker.wait()

    def _show_produce_selector(self):
        """Show produce item selector."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Produce Item")
        dialog.setModal(True)
        dialog.setMinimumSize(300, 400)

        layout = QVBoxLayout()

        # Create scroll area with produce items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        produce_widget = QWidget()
        produce_layout = QVBoxLayout()

        produce_items = self.barcode_service.get_produce_items()

        for barcode, name in produce_items:
            btn = QPushButton(name)
            btn.clicked.connect(
                lambda checked, b=barcode, n=name: self._select_produce(b, n, dialog)
            )
            produce_layout.addWidget(btn)

        produce_widget.setLayout(produce_layout)
        scroll.setWidget(produce_widget)

        layout.addWidget(scroll)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(cancel_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _select_produce(self, barcode: str, name: str, dialog: QDialog):
        """Select a produce item."""
        self.barcode_field.setText(barcode)
        self.name_field.setText(name)
        dialog.accept()

    def get_item_data(self):
        """Get the item data from the form.

        Returns:
            dict with item data or None if invalid
        """
        name = self.name_field.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter an item name")
            return None

        expiry_date = self.expiry_date_field.date().toPython()
        barcode = self.barcode_field.text().strip() or None
        quantity = self.quantity_field.value()

        return {
            "name": name,
            "expiry_date": expiry_date,
            "barcode": barcode,
            "quantity": quantity
        }


class ItemCard(QFrame):
    """Card widget for displaying an item."""

    delete_requested = Signal(int, str)  # id, name
    toggle_opened_requested = Signal(int)  # id
    add_to_shopping_requested = Signal(str)  # name

    def __init__(self, item: Item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setProperty("styleClass", "card")
        self.setFrameStyle(QFrame.Box)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        # Get status colors
        bg_color, text_color, _ = UITheme.get_status_colors(self.item.status)

        # Set background color
        self.setStyleSheet(f"""
            QFrame[styleClass="card"] {{
                background-color: {bg_color.name()};
                border: 1px solid {UITheme.PRIMARY_LIGHT.name()};
                border-radius: {UITheme.RADIUS_MD}px;
                padding: {UITheme.SPACING_MD}px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(UITheme.SPACING_MD, UITheme.SPACING_MD,
                                   UITheme.SPACING_MD, UITheme.SPACING_MD)

        # Left side: Item info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Item name
        name_label = QLabel(self.item.display_name)
        name_label.setStyleSheet("font-weight: 600; font-size: 16px;")
        info_layout.addWidget(name_label)

        # Status badges
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(4)

        status_text = DateFormatter.format_expiry_status(self.item.expiry_date)
        status_label = QLabel(status_text)
        status_label.setProperty("status", self.item.status)
        status_label.setStyleSheet(f"""
            background-color: {bg_color.name()};
            color: {text_color.name()};
            border-radius: {UITheme.RADIUS_SM}px;
            padding: 2px 8px;
            font-size: {UITheme.FONT_SIZE_CAPTION}px;
        """)
        badges_layout.addWidget(status_label)

        if self.item.is_opened:
            opened_text = f"Opened {DateFormatter.format_date_short(self.item.opened_date)}" if self.item.opened_date else "Opened"
            opened_label = QLabel(opened_text)
            opened_label.setStyleSheet(f"""
                background-color: {UITheme.OPENED_BG.name()};
                color: {UITheme.OPENED_TEXT.name()};
                border-radius: {UITheme.RADIUS_SM}px;
                padding: 2px 8px;
                font-size: {UITheme.FONT_SIZE_CAPTION}px;
            """)
            badges_layout.addWidget(opened_label)

        badges_layout.addStretch()
        info_layout.addLayout(badges_layout)

        # Expiry date
        expiry_label = QLabel(f"Best before: {DateFormatter.format_date(self.item.expiry_date, '%B %d, %Y')}")
        expiry_label.setProperty("styleClass", "subtitle")
        expiry_label.setStyleSheet(f"color: {UITheme.TEXT_SECONDARY.name()}; font-size: {UITheme.FONT_SIZE_SMALL}px;")
        info_layout.addWidget(expiry_label)

        layout.addLayout(info_layout, stretch=1)

        # Right side: Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(0)

        # Toggle opened button
        toggle_btn = QPushButton()
        toggle_btn.setIcon(QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_DialogOpenButton if self.item.is_opened
            else QApplication.style().StandardPixmap.SP_FileIcon
        ))
        toggle_btn.setToolTip("Mark as opened" if not self.item.is_opened else "Mark as unopened")
        toggle_btn.setFixedSize(32, 32)
        toggle_btn.clicked.connect(lambda: self.toggle_opened_requested.emit(self.item.id))
        actions_layout.addWidget(toggle_btn)

        # Add to shopping list button
        shopping_btn = QPushButton()
        shopping_btn.setIcon(QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_DialogSaveButton
        ))
        shopping_btn.setToolTip("Add to shopping list")
        shopping_btn.setFixedSize(32, 32)
        shopping_btn.clicked.connect(lambda: self.add_to_shopping_requested.emit(self.item.name))
        actions_layout.addWidget(shopping_btn)

        # Delete button
        delete_btn = QPushButton()
        delete_btn.setIcon(QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_TrashIcon
        ))
        delete_btn.setToolTip("Remove item")
        delete_btn.setFixedSize(32, 32)
        delete_btn.setProperty("styleClass", "error")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.item.id, self.item.name))
        actions_layout.addWidget(delete_btn)

        layout.addLayout(actions_layout)

        self.setLayout(layout)


class MainWindow(QMainWindow):
    """Main window for the application."""

    def __init__(
        self,
        inventory_service: InventoryService,
        item_repository: ItemRepository,
        barcode_service: BarcodeService,
        shopping_service: ShoppingListService,
        camera_service: CameraService,
        settings,
        available_cameras: list = None
    ):
        super().__init__()

        self.inventory_service = inventory_service
        self.item_repository = item_repository
        self.barcode_service = barcode_service
        self.shopping_service = shopping_service
        self.camera_service = camera_service
        self.settings = settings
        self.available_cameras = available_cameras or []

        self.setWindowTitle("Cool Companion")

        # Set window size
        if settings.window_fullscreen:
            self.showFullScreen()
        else:
            self.resize(settings.window_width, settings.window_height)

        self._init_ui()
        self._refresh_items()

    def _init_ui(self):
        """Initialize the UI."""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(UITheme.SPACING_MD)
        main_layout.setContentsMargins(UITheme.SPACING_MD, UITheme.SPACING_MD,
                                        UITheme.SPACING_MD, UITheme.SPACING_MD)

        # Header
        main_layout.addWidget(self._build_header())

        # Stats section
        main_layout.addWidget(self._build_stats_section())

        # Items list section
        items_label = QLabel("Your Items:")
        items_label.setProperty("styleClass", "title")
        main_layout.addWidget(items_label)

        # Scrollable items list
        self.items_scroll = QScrollArea()
        self.items_scroll.setWidgetResizable(True)
        self.items_scroll.setFrameShape(QFrame.NoFrame)

        self.items_widget = QWidget()
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(UITheme.SPACING_SM)
        self.items_widget.setLayout(self.items_layout)

        self.items_scroll.setWidget(self.items_widget)
        main_layout.addWidget(self.items_scroll, stretch=1)

        # Add item button
        add_btn = QPushButton("+ Add Item")
        add_btn.setProperty("styleClass", "success")
        add_btn.setFixedHeight(UITheme.BUTTON_HEIGHT)
        add_btn.clicked.connect(self._show_add_dialog)
        main_layout.addWidget(add_btn)

        central_widget.setLayout(main_layout)

    def _build_header(self) -> QWidget:
        """Build header with logo, title, and settings button."""
        header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Logo (if exists)
        import os
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(logo_label)

        # Title
        title = QLabel("Cool Companion")
        title.setProperty("styleClass", "headline")
        header_layout.addWidget(title, stretch=1, alignment=Qt.AlignCenter)

        # Settings button
        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(40, 40)
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._show_settings_dialog)
        header_layout.addWidget(settings_btn)

        header_widget.setLayout(header_layout)
        return header_widget

    def _build_stats_section(self) -> QWidget:
        """Build statistics section."""
        stats = self.inventory_service.get_inventory_stats()

        stats_widget = QWidget()
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(UITheme.SPACING_MD)

        # Total items
        stats_layout.addWidget(
            self._build_stat_card("Total", str(stats["total_items"]), UITheme.PRIMARY)
        )

        # Expiring items
        stats_layout.addWidget(
            self._build_stat_card("Expiring", str(stats["expiring_soon_count"]), UITheme.WARNING)
        )

        # Expired items
        stats_layout.addWidget(
            self._build_stat_card("Expired", str(stats["expired_count"]), UITheme.ERROR)
        )

        stats_widget.setLayout(stats_layout)
        return stats_widget

    def _build_stat_card(self, title: str, value: str, color) -> QFrame:
        """Build a statistics card."""
        card = QFrame()
        card.setProperty("styleClass", "stat-card")
        card.setFrameStyle(QFrame.Box)
        card.setFixedWidth(100)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(2)

        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color.name()};")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)

        # Title
        title_label = QLabel(title)
        title_label.setProperty("styleClass", "caption")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        card.setLayout(layout)
        return card

    def _refresh_items(self):
        """Refresh the items list."""
        try:
            # Clear existing items
            while self.items_layout.count():
                child = self.items_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Get all items
            items = self.item_repository.get_all()

            if not items:
                # Show empty state
                empty_widget = QWidget()
                empty_layout = QVBoxLayout()
                empty_layout.setAlignment(Qt.AlignCenter)

                empty_label = QLabel("Your fridge is empty!")
                empty_label.setStyleSheet("font-size: 20px; font-weight: 600;")
                empty_label.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(empty_label)

                subtitle = QLabel("Add your first item to get started")
                subtitle.setProperty("styleClass", "subtitle")
                subtitle.setAlignment(Qt.AlignCenter)
                empty_layout.addWidget(subtitle)

                add_btn = QPushButton("Add Item")
                add_btn.setProperty("styleClass", "success")
                add_btn.clicked.connect(self._show_add_dialog)
                empty_layout.addWidget(add_btn, alignment=Qt.AlignCenter)

                empty_widget.setLayout(empty_layout)
                self.items_layout.addWidget(empty_widget)
            else:
                # Add item cards
                for item in items:
                    card = ItemCard(item)
                    card.delete_requested.connect(self._show_delete_dialog)
                    card.toggle_opened_requested.connect(self._toggle_opened)
                    card.add_to_shopping_requested.connect(self._add_to_shopping_list)
                    self.items_layout.addWidget(card)

            self.items_layout.addStretch()

            # Refresh stats
            stats = self.inventory_service.get_inventory_stats()
            # Update stats (you could store references to stat labels to update them)

        except Exception as e:
            logger.error(f"Error refreshing items: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load items: {str(e)}")

    def _show_add_dialog(self):
        """Show add item dialog."""
        dialog = AddItemDialog(self, self.barcode_service, self.camera_service, self.settings)

        if dialog.exec() == QDialog.Accepted:
            item_data = dialog.get_item_data()
            if item_data:
                try:
                    item = Item(
                        name=item_data["name"],
                        expiry_date=item_data["expiry_date"],
                        barcode=item_data["barcode"],
                        quantity=item_data["quantity"]
                    )

                    saved_item = self.inventory_service.add_item(item)

                    if saved_item:
                        self._refresh_items()
                        QMessageBox.information(
                            self, "Success", f"Added {saved_item.display_name}"
                        )
                    else:
                        QMessageBox.warning(self, "Error", "Failed to add item")

                except Exception as e:
                    logger.error(f"Error adding item: {e}")
                    QMessageBox.critical(self, "Error", f"Failed to add item: {str(e)}")

    def _toggle_opened(self, item_id: int):
        """Toggle item opened status."""
        if self.inventory_service.toggle_opened_status(item_id):
            self._refresh_items()
            QMessageBox.information(self, "Success", "Item status updated")
        else:
            QMessageBox.warning(self, "Error", "Failed to update item status")

    def _add_to_shopping_list(self, item_name: str):
        """Add item to shopping list."""
        if self.shopping_service.add_item_sync(item_name):
            QMessageBox.information(
                self, "Success", f"Added '{item_name}' to shopping list"
            )
        else:
            QMessageBox.warning(self, "Error", "Failed to add to shopping list")

    def _show_delete_dialog(self, item_id: int, item_name: str):
        """Show delete confirmation dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Remove Item")
        msg.setText(f"Do you want to add '{item_name}' to your shopping list before removing?")
        msg.addButton("Yes, add to list", QMessageBox.YesRole)
        msg.addButton("No, just delete", QMessageBox.NoRole)
        msg.addButton("Cancel", QMessageBox.RejectRole)

        result = msg.exec()

        if result == 0:  # Yes
            self._delete_item(item_id, True)
        elif result == 1:  # No
            self._delete_item(item_id, False)

    def _delete_item(self, item_id: int, add_to_shopping: bool):
        """Delete item from inventory."""
        if self.inventory_service.delete_and_restock_sync(item_id, add_to_shopping):
            self._refresh_items()
            QMessageBox.information(self, "Success", "Item removed successfully")
        else:
            QMessageBox.warning(self, "Error", "Failed to remove item")

    def _show_settings_dialog(self):
        """Show settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setModal(True)
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Create scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout()

        # Bring Shopping List settings
        settings_layout.addWidget(QLabel("<b>Bring Shopping List</b>"))

        bring_email = QLineEdit(self.settings.bring_email)
        bring_email.setPlaceholderText("Bring Email")
        settings_layout.addWidget(bring_email)

        bring_password = QLineEdit(self.settings.bring_password)
        bring_password.setPlaceholderText("Bring Password")
        bring_password.setEchoMode(QLineEdit.Password)
        settings_layout.addWidget(bring_password)

        # Camera settings
        settings_layout.addWidget(QLabel("<b>Camera</b>"))

        camera_combo = QComboBox()
        for idx, name in self.available_cameras:
            camera_combo.addItem(name, idx)
        camera_combo.setCurrentIndex(self.settings.camera_index)
        settings_layout.addWidget(camera_combo)

        # Feature toggles
        settings_layout.addWidget(QLabel("<b>Features</b>"))

        barcode_check = QCheckBox("Enable Barcode Scanning")
        barcode_check.setChecked(self.settings.enable_barcode_scanning)
        settings_layout.addWidget(barcode_check)

        shopping_check = QCheckBox("Enable Shopping List")
        shopping_check.setChecked(self.settings.enable_shopping_list)
        settings_layout.addWidget(shopping_check)

        settings_widget.setLayout(settings_layout)
        scroll.setWidget(settings_widget)

        layout.addWidget(scroll)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        dialog.setLayout(layout)

        if dialog.exec() == QDialog.Accepted:
            # Save settings to .env file
            try:
                import os
                from dotenv import set_key

                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

                # Ensure .env file exists
                if not os.path.exists(env_path):
                    with open(env_path, 'w') as f:
                        f.write("# Cool Companion Configuration\n")

                # Settings to save
                settings_map = {
                    'BRING_EMAIL': bring_email.text(),
                    'BRING_PASSWORD': bring_password.text(),
                    'CAMERA_INDEX': str(camera_combo.currentData()),
                    'ENABLE_BARCODE_SCANNING': 'true' if barcode_check.isChecked() else 'false',
                    'ENABLE_SHOPPING_LIST': 'true' if shopping_check.isChecked() else 'false',
                }

                # Use set_key for safe, atomic updates with proper escaping
                for key, value in settings_map.items():
                    set_key(env_path, key, value, quote_mode='never')

                QMessageBox.information(
                    self, "Success",
                    "Settings saved! Please restart the app for changes to take effect."
                )

            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")

    def show_welcome_dialog(self):
        """Show welcome dialog for first-time users."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Welcome to Cool Companion!")
        msg.setText("Track your food items and reduce waste!")
        msg.setInformativeText(
            "Features:\n"
            "• Scan barcodes to add items quickly\n"
            "• Track expiry dates with visual indicators\n"
            "• Sync with Bring! shopping list\n"
            "• Get notified about expiring items"
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
