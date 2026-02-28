"""
Reusable Qt Widgets — Smart Macro Station
Card layouts, nav buttons, status badges, and utility components.
"""

from PyQt6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QPlainTextEdit, QWidget, QSizePolicy
)
from PyQt6.QtCore import Qt


class Card(QFrame):
    """Rounded card container with optional title."""

    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        if title:
            header = QFrame()
            header.setObjectName("cardHeader")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(24, 18, 24, 14)
            lbl = QLabel(title)
            lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
            header_layout.addWidget(lbl)
            self._layout.addWidget(header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 16, 24, 20)
        self._content_layout.setSpacing(12)
        self._layout.addWidget(self._content)

    def content_layout(self):
        return self._content_layout

    def add_widget(self, widget):
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        self._content_layout.addLayout(layout)


class StatusBadge(QFrame):
    """Pill-shaped status indicator with dot + text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBadge")
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #D97706; font-size: 12px;")
        layout.addWidget(self._dot)

        self._label = QLabel("Initializing...")
        self._label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._label)
        layout.addStretch()

    def set_status(self, status, text):
        colors = {
            "success": "#059669", "error": "#DC2626",
            "warning": "#D97706", "loading": "#2563EB"
        }
        color = colors.get(status, "#94A3B8")
        self._dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._label.setText(text)


class ProgressStep(QFrame):
    """Step indicator with icon + label."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self._icon = QLabel("○")
        self._icon.setFixedSize(30, 30)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            "font-size: 14px; color: #94A3B8; "
            "border: 2px solid #E2E8F0; border-radius: 15px; "
            "background-color: #F1F5F9;"
        )
        layout.addWidget(self._icon)

        self._label = QLabel(text)
        self._label.setStyleSheet("color: #64748B; font-size: 13px;")
        layout.addWidget(self._label, 1)

    def set_state(self, state):
        if state == "pending":
            self._icon.setText("○")
            self._icon.setStyleSheet(
                "font-size: 14px; color: #94A3B8; "
                "border: 2px solid #E2E8F0; border-radius: 15px; "
                "background-color: #F1F5F9;"
            )
            self._label.setStyleSheet("color: #64748B; font-size: 13px;")
        elif state == "active":
            self._icon.setText("◔")
            self._icon.setStyleSheet(
                "font-size: 14px; color: #2563EB; "
                "border: 2px solid #2563EB; border-radius: 15px; "
                "background-color: #DBEAFE;"
            )
            self._label.setStyleSheet("color: #0F172A; font-size: 13px; font-weight: bold;")
        elif state == "complete":
            self._icon.setText("✓")
            self._icon.setStyleSheet(
                "font-size: 14px; color: white; "
                "border: 2px solid #059669; border-radius: 15px; "
                "background-color: #059669;"
            )
            self._label.setStyleSheet("color: #475569; font-size: 13px;")


class ReasoningTerminal(QPlainTextEdit):
    """Dark hacker-style terminal for AI reasoning output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("terminal")
        self.setReadOnly(True)
        self.setMinimumHeight(120)
        self.setMaximumHeight(180)

    def append_text(self, text):
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.insertPlainText(text)
        self.ensureCursorVisible()

    def clear_text(self):
        self.clear()


class DownloadButton(QPushButton):
    """Download-to-Downloads button with state management."""

    def __init__(self, parent=None):
        super().__init__("⬇️  Save to Downloads", parent)
        self.setEnabled(False)
        self.setFixedHeight(40)
        self._ready = False

    def set_ready(self, filepath):
        self._filepath = filepath
        self._ready = True
        self.setEnabled(True)
        self.setObjectName("success")
        self.setText("⬇️  Ready — Save to Downloads")
        self.style().unpolish(self)
        self.style().polish(self)

    def do_download(self):
        if not self._ready:
            return None
        import os
        import shutil
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(downloads, exist_ok=True)
        dest = os.path.join(downloads, os.path.basename(self._filepath))
        shutil.copy2(self._filepath, dest)
        self.setText("✅  Saved to Downloads!")
        self.setEnabled(False)
        return dest