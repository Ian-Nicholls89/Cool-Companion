"""Centralized theme configuration for PySide6 application."""
from PySide6.QtGui import QColor, QPalette, QFont, QIcon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import os


class UITheme:
    """Centralized theme configuration with Material Design 3 colors for Qt."""

    # Color scheme (RGB values)
    PRIMARY = QColor(25, 118, 210)  # Blue 700
    PRIMARY_VARIANT = QColor(13, 71, 161)  # Blue 900
    PRIMARY_LIGHT = QColor(179, 229, 252)  # Blue 100
    SECONDARY = QColor(0, 137, 123)  # Teal 600
    SECONDARY_VARIANT = QColor(0, 77, 64)  # Teal 800
    BACKGROUND = QColor(250, 250, 250)  # Grey 50
    SURFACE = QColor(255, 255, 255)  # White
    ERROR = QColor(211, 47, 47)  # Red 700
    WARNING = QColor(245, 124, 0)  # Orange 700
    SUCCESS = QColor(56, 142, 60)  # Green 700
    INFO = QColor(30, 136, 229)  # Blue 600

    # Text colors
    TEXT_PRIMARY = QColor(33, 33, 33)  # Grey 900
    TEXT_SECONDARY = QColor(97, 97, 97)  # Grey 700
    TEXT_DISABLED = QColor(189, 189, 189)  # Grey 400
    TEXT_ON_PRIMARY = QColor(255, 255, 255)  # White
    TEXT_ON_ERROR = QColor(255, 255, 255)  # White

    # Status colors for items
    EXPIRED_BG = QColor(255, 235, 238)  # Red 50
    EXPIRED_TEXT = QColor(211, 47, 47)  # Red 700
    EXPIRING_BG = QColor(255, 243, 224)  # Orange 50
    EXPIRING_TEXT = QColor(245, 124, 0)  # Orange 700
    FRESH_BG = QColor(232, 245, 233)  # Green 50
    FRESH_TEXT = QColor(56, 142, 60)  # Green 700
    OPENED_BG = QColor(227, 242, 253)  # Blue 50
    OPENED_TEXT = QColor(30, 136, 229)  # Blue 600

    # Spacing constants (pixels)
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 16
    SPACING_LG = 24
    SPACING_XL = 32
    SPACING_XXL = 48

    # Border radius
    RADIUS_SM = 4
    RADIUS_MD = 8
    RADIUS_LG = 16
    RADIUS_XL = 24
    RADIUS_ROUND = 999

    # Font sizes
    FONT_SIZE_LARGE = 16
    FONT_SIZE_MEDIUM = 14
    FONT_SIZE_SMALL = 12
    FONT_SIZE_CAPTION = 11

    # Component sizes
    BUTTON_HEIGHT = 48
    ICON_SIZE_SM = 16
    ICON_SIZE_MD = 24
    ICON_SIZE_LG = 32
    ICON_SIZE_XL = 48

    @classmethod
    def get_stylesheet(cls) -> str:
        """Get the complete Qt stylesheet for the application.

        Returns:
            QString containing the complete stylesheet
        """
        return f"""
        /* Main application styling */
        QMainWindow {{
            background-color: {cls.BACKGROUND.name()};
        }}

        /* Primary buttons */
        QPushButton {{
            background-color: {cls.PRIMARY.name()};
            color: white;
            border: none;
            border-radius: {cls.RADIUS_MD}px;
            padding: 8px 16px;
            font-size: {cls.FONT_SIZE_MEDIUM}px;
            font-weight: 500;
            min-height: 36px;
        }}

        QPushButton:hover {{
            background-color: {cls.PRIMARY_VARIANT.name()};
        }}

        QPushButton:pressed {{
            background-color: {cls.PRIMARY_VARIANT.name()};
        }}

        QPushButton:disabled {{
            background-color: {cls.TEXT_DISABLED.name()};
            color: white;
        }}

        /* Secondary buttons */
        QPushButton[styleClass="secondary"] {{
            background-color: {cls.SECONDARY.name()};
        }}

        QPushButton[styleClass="secondary"]:hover {{
            background-color: {cls.SECONDARY_VARIANT.name()};
        }}

        /* Success buttons */
        QPushButton[styleClass="success"] {{
            background-color: {cls.SUCCESS.name()};
        }}

        /* Error/Delete buttons */
        QPushButton[styleClass="error"] {{
            background-color: {cls.ERROR.name()};
        }}

        /* Text input fields */
        QLineEdit, QTextEdit, QSpinBox, QDateEdit, QComboBox {{
            border: 2px solid {cls.PRIMARY_LIGHT.name()};
            border-radius: {cls.RADIUS_SM}px;
            padding: 8px;
            background-color: white;
            font-size: {cls.FONT_SIZE_MEDIUM}px;
        }}

        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{
            border: 2px solid {cls.PRIMARY.name()};
        }}

        /* Labels */
        QLabel {{
            color: {cls.TEXT_PRIMARY.name()};
            font-size: {cls.FONT_SIZE_MEDIUM}px;
        }}

        QLabel[styleClass="headline"] {{
            font-size: 36px;
            font-weight: 500;
            color: {cls.PRIMARY.name()};
        }}

        QLabel[styleClass="title"] {{
            font-size: 20px;
            font-weight: 600;
        }}

        QLabel[styleClass="subtitle"] {{
            font-size: {cls.FONT_SIZE_MEDIUM}px;
            color: {cls.TEXT_SECONDARY.name()};
        }}

        QLabel[styleClass="caption"] {{
            font-size: {cls.FONT_SIZE_CAPTION}px;
            color: {cls.TEXT_SECONDARY.name()};
        }}

        /* Cards/Frames */
        QFrame[styleClass="card"] {{
            background-color: white;
            border: 1px solid {cls.PRIMARY_LIGHT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: {cls.SPACING_MD}px;
        }}

        QFrame[styleClass="stat-card"] {{
            background-color: white;
            border: 1px solid {cls.PRIMARY_LIGHT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: {cls.SPACING_SM}px;
        }}

        /* Status badges */
        QLabel[status="expired"] {{
            background-color: {cls.EXPIRED_BG.name()};
            color: {cls.EXPIRED_TEXT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: 4px 8px;
        }}

        QLabel[status="expiring_soon"] {{
            background-color: {cls.EXPIRING_BG.name()};
            color: {cls.EXPIRING_TEXT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: 4px 8px;
        }}

        QLabel[status="fresh"] {{
            background-color: {cls.FRESH_BG.name()};
            color: {cls.FRESH_TEXT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: 4px 8px;
        }}

        QLabel[status="opened"] {{
            background-color: {cls.OPENED_BG.name()};
            color: {cls.OPENED_TEXT.name()};
            border-radius: {cls.RADIUS_MD}px;
            padding: 4px 8px;
        }}

        /* Scroll areas */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}

        QScrollBar:vertical {{
            background: {cls.BACKGROUND.name()};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background: {cls.TEXT_DISABLED.name()};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {cls.TEXT_SECONDARY.name()};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        /* Dialogs */
        QDialog {{
            background-color: white;
        }}

        /* Checkboxes and Radio buttons */
        QCheckBox, QRadioButton {{
            font-size: {cls.FONT_SIZE_MEDIUM}px;
            spacing: 8px;
        }}

        QCheckBox::indicator, QRadioButton::indicator {{
            width: 20px;
            height: 20px;
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {cls.TEXT_PRIMARY.name()};
            color: white;
            border: none;
            padding: 4px 8px;
            font-size: {cls.FONT_SIZE_SMALL}px;
        }}

        /* Menu bar and menus */
        QMenuBar {{
            background-color: white;
            border-bottom: 1px solid {cls.PRIMARY_LIGHT.name()};
        }}

        QMenuBar::item {{
            padding: 4px 12px;
        }}

        QMenuBar::item:selected {{
            background-color: {cls.PRIMARY_LIGHT.name()};
        }}

        QMenu {{
            background-color: white;
            border: 1px solid {cls.PRIMARY_LIGHT.name()};
        }}

        QMenu::item {{
            padding: 8px 24px;
        }}

        QMenu::item:selected {{
            background-color: {cls.PRIMARY_LIGHT.name()};
        }}
        """

    @classmethod
    def apply_to_app(cls, app: QApplication):
        """Apply theme to Qt application.

        Args:
            app: QApplication instance
        """
        # Set application stylesheet
        app.setStyleSheet(cls.get_stylesheet())

        # Set application palette
        palette = QPalette()
        palette.setColor(QPalette.Window, cls.BACKGROUND)
        palette.setColor(QPalette.WindowText, cls.TEXT_PRIMARY)
        palette.setColor(QPalette.Base, cls.SURFACE)
        palette.setColor(QPalette.AlternateBase, cls.PRIMARY_LIGHT)
        palette.setColor(QPalette.ToolTipBase, cls.TEXT_PRIMARY)
        palette.setColor(QPalette.ToolTipText, cls.TEXT_ON_PRIMARY)
        palette.setColor(QPalette.Text, cls.TEXT_PRIMARY)
        palette.setColor(QPalette.Button, cls.PRIMARY)
        palette.setColor(QPalette.ButtonText, cls.TEXT_ON_PRIMARY)
        palette.setColor(QPalette.BrightText, cls.ERROR)
        palette.setColor(QPalette.Link, cls.PRIMARY)
        palette.setColor(QPalette.Highlight, cls.PRIMARY)
        palette.setColor(QPalette.HighlightedText, cls.TEXT_ON_PRIMARY)

        app.setPalette(palette)

        # Set default font
        font = QFont("Segoe UI", cls.FONT_SIZE_MEDIUM)
        app.setFont(font)

    @classmethod
    def get_status_colors(cls, status: str) -> tuple:
        """Get colors for item status.

        Args:
            status: Item status (expired, expiring_soon, fresh, opened)

        Returns:
            Tuple of (background_color, text_color, icon_name)
        """
        status_map = {
            "expired": (cls.EXPIRED_BG, cls.EXPIRED_TEXT, "SP_MessageBoxCritical"),
            "expiring_soon": (cls.EXPIRING_BG, cls.EXPIRING_TEXT, "SP_MessageBoxWarning"),
            "fresh": (cls.FRESH_BG, cls.FRESH_TEXT, "SP_DialogApplyButton"),
            "opened": (cls.OPENED_BG, cls.OPENED_TEXT, "SP_DialogOpenButton"),
        }

        return status_map.get(status, (cls.SURFACE, cls.TEXT_PRIMARY, "SP_MessageBoxInformation"))

    @classmethod
    def create_button_style(cls, style_class: str = "primary") -> str:
        """Create button style based on class.

        Args:
            style_class: Button style (primary, secondary, success, error)

        Returns:
            Style string for button
        """
        styles = {
            "primary": f"background-color: {cls.PRIMARY.name()}; color: white;",
            "secondary": f"background-color: {cls.SECONDARY.name()}; color: white;",
            "success": f"background-color: {cls.SUCCESS.name()}; color: white;",
            "error": f"background-color: {cls.ERROR.name()}; color: white;",
        }

        return styles.get(style_class, styles["primary"])
