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
        """Apply git delta update in background thread."""
        try:
            import asyncio

            # Run async update in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                success, message = loop.run_until_complete(self.update_service.apply_update())
                self.finished.emit(success, message)
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
        self.title_label = QLabel("🎉 A new version is available!")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Commit information
        commit_layout = QHBoxLayout()

        current_label = QLabel(f"Current: <b>{self.update_info.current_commit}</b>")
        commit_layout.addWidget(current_label)

        commit_layout.addStretch()

        latest_label = QLabel(f"Latest: <b>{self.update_info.latest_commit}</b>")
        commit_layout.addWidget(latest_label)

        layout.addLayout(commit_layout)

        # Update summary
        summary = self.update_info.get_summary()
        summary_label = QLabel(summary)
        summary_label.setStyleSheet("color: #2563eb; font-weight: bold; margin-top: 8px;")
        layout.addWidget(summary_label)

        # Changed files preview
        if self.update_info.changed_files:
            files_label = QLabel("Changed Files:")
            files_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
            layout.addWidget(files_label)

            files_text = QTextEdit()
            files_text.setReadOnly(True)
            files_text.setPlainText('\n'.join(self.update_info.changed_files))
            files_text.setMaximumHeight(120)
            files_text.setStyleSheet("background-color: #f3f4f6; font-family: monospace;")
            layout.addWidget(files_text)

        # Commit messages
        commits_label = QLabel("Recent Commits:")
        commits_label.setStyleSheet("font-weight: bold; margin-top: 12px;")
        layout.addWidget(commits_label)

        commits_text = QTextEdit()
        commits_text.setReadOnly(True)
        commits_text.setPlainText(self.update_info.commit_messages)
        commits_text.setMaximumHeight(150)
        commits_text.setStyleSheet("font-family: monospace;")
        layout.addWidget(commits_text)

        # Last update date
        if self.update_info.last_update_date:
            date_label = QLabel(f"Last updated: {self.update_info.last_update_date}")
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

        # Update button (git pull delta update)
        update_btn = QPushButton(f"Update Now ({self.update_info.commits_behind} commits)")
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

        layout.addLayout(button_layout)

        self.setLayout(layout)


    def _apply_git_update(self):
        """Apply git delta update in background."""
        # Confirm action
        file_count = len(self.update_info.changed_files)
        reply = QMessageBox.question(
            self,
            "Confirm Update",
            f"This will update the application using git pull (delta download).\n\n"
            f"Changes:\n"
            f"  • {self.update_info.commits_behind} commit(s) will be applied\n"
            f"  • {file_count} file(s) will be updated\n\n"
            f"Only changed file contents will be downloaded.\n"
            f"Your data (.env, fridge.db, logs) will be preserved.\n\n"
            f"Continue?",
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
        self.title_label.setText("⏳ Applying update...")

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
            self.title_label.setText("🎉 A new version is available!")


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
            f"<b>Update available:</b> {self.update_info.commits_behind} commit(s), "
            f"{len(self.update_info.changed_files)} file(s) changed"
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
