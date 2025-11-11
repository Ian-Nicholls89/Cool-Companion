"""Dialog for displaying update information and options."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
import logging
import webbrowser
from services.update_service import UpdateInfo

logger = logging.getLogger(__name__)


class UpdateApplyWorker(QThread):
    """Worker thread for applying git updates."""

    finished = Signal(bool, str)  # success, message

    def __init__(self, update_service):
        super().__init__()
        self.update_service = update_service

    def run(self):
        """Apply git update in background thread."""
        try:
            import asyncio

            # Run async update in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                success = loop.run_until_complete(
                    self.update_service.apply_git_update()
                )

                if success:
                    self.finished.emit(True, "Update applied successfully! Please restart the application.")
                else:
                    self.finished.emit(False, "Update failed. Please check logs for details.")
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error applying update: {e}")
            self.finished.emit(False, f"Update error: {str(e)}")


class UpdateDialog(QDialog):
    """Dialog for displaying update information."""

    def __init__(self, update_info: UpdateInfo, update_service, parent=None):
        """Initialize update dialog.

        Args:
            update_info: Information about the available update
            update_service: Update service instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.update_info = update_info
        self.update_service = update_service
        self.worker = None

        self.setWindowTitle("Update Available")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # Title
        title = QLabel("🎉 A new version is available!")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Version information
        version_layout = QHBoxLayout()

        current_label = QLabel(f"Current version: <b>{self.update_info.current_version}</b>")
        version_layout.addWidget(current_label)

        version_layout.addStretch()

        latest_label = QLabel(f"Latest version: <b>{self.update_info.latest_version}</b>")
        version_layout.addWidget(latest_label)

        layout.addLayout(version_layout)

        # Release notes
        notes_label = QLabel("Release Notes:")
        notes_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(notes_label)

        notes_text = QTextEdit()
        notes_text.setReadOnly(True)
        notes_text.setPlainText(self.update_info.release_notes)
        notes_text.setMaximumHeight(200)
        layout.addWidget(notes_text)

        # Published date
        if self.update_info.published_at:
            date_label = QLabel(f"Published: {self.update_info.published_at}")
            date_label.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(date_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Remind later button
        remind_btn = QPushButton("Remind Me Later")
        remind_btn.clicked.connect(self.reject)
        button_layout.addWidget(remind_btn)

        # View release button (if URL available)
        if self.update_info.release_url:
            view_btn = QPushButton("View Release")
            view_btn.clicked.connect(self._open_release_url)
            button_layout.addWidget(view_btn)

        # Update action button
        if self.update_service.is_git_repo:
            # Git repo: offer to update via git pull
            update_btn = QPushButton("Update Now (Git Pull)")
            update_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    font-weight: bold;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            update_btn.clicked.connect(self._apply_git_update)
            button_layout.addWidget(update_btn)
        elif self.update_info.download_url:
            # Release download available
            download_btn = QPushButton("Download Update")
            download_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: white;
                    font-weight: bold;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
            """)
            download_btn.clicked.connect(self._download_update)
            button_layout.addWidget(download_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _open_release_url(self):
        """Open release URL in browser."""
        try:
            webbrowser.open(self.update_info.release_url)
        except Exception as e:
            logger.error(f"Error opening release URL: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open browser: {str(e)}"
            )

    def _download_update(self):
        """Open download URL in browser."""
        try:
            if self.update_info.download_url:
                webbrowser.open(self.update_info.download_url)

                QMessageBox.information(
                    self,
                    "Download Started",
                    "The download should start in your browser.\n\n"
                    "After downloading, please extract and replace the application files.\n"
                    "Your data (.env, fridge.db, logs) will be preserved."
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "No Download Available",
                    "No download URL is available for this release.\n"
                    "Please visit the release page to download manually."
                )
        except Exception as e:
            logger.error(f"Error opening download URL: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open browser: {str(e)}"
            )

    def _apply_git_update(self):
        """Apply git update in background."""
        # Confirm action
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            "This will run 'git pull' to update the application.\n\n"
            "Make sure you have committed or stashed any local changes.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Disable buttons during update
        for button in self.findChildren(QPushButton):
            button.setEnabled(False)

        # Create and start worker thread
        self.worker = UpdateApplyWorker(self.update_service)
        self.worker.finished.connect(self._on_update_finished)
        self.worker.start()

        # Show progress
        self.findChild(QLabel).setText("⏳ Applying update...")

    def _on_update_finished(self, success: bool, message: str):
        """Handle update completion.

        Args:
            success: Whether update was successful
            message: Result message
        """
        # Re-enable buttons
        for button in self.findChildren(QPushButton):
            button.setEnabled(True)

        if success:
            QMessageBox.information(
                self,
                "Update Successful",
                message
            )
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Update Failed",
                message
            )
            # Reset title
            self.findChild(QLabel).setText("🎉 A new version is available!")


class UpdateNotificationWidget(QWidget):
    """Compact notification widget for showing update availability."""

    clicked = Signal()

    def __init__(self, update_info: UpdateInfo, parent=None):
        """Initialize notification widget.

        Args:
            update_info: Information about the available update
            parent: Parent widget
        """
        super().__init__(parent)
        self.update_info = update_info

        self.setStyleSheet("""
            QWidget {
                background-color: #dbeafe;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 8px;
            }
            QWidget:hover {
                background-color: #bfdbfe;
            }
        """)

        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)

        # Icon
        icon_label = QLabel("🔔")
        icon_label.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        layout.addWidget(icon_label)

        # Message
        message = QLabel(
            f"<b>Update available:</b> {self.update_info.latest_version} "
            f"<span style='color: #666;'>(current: {self.update_info.current_version})</span>"
        )
        message.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(message, 1)

        # Click to view button
        view_label = QLabel("Click to view →")
        view_label.setStyleSheet("background: transparent; border: none; color: #2563eb; font-weight: bold;")
        layout.addWidget(view_label)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
