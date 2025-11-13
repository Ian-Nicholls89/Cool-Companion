"""Views module for presentation layer."""
from .main_window import MainWindow
from .update_dialog import UpdateDialog, UpdateNotificationWidget

__all__ = ['MainWindow', 'UpdateDialog', 'UpdateNotificationWidget']