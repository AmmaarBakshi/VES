"""
AI Chat Panel — PyQt6
Scrollable chat interface for AI conversations.
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QTimer, QMetaObject, pyqtSlot
from app.gui.theme import ThemeManager


class AIChatPanel(QFrame):
    """Conversational AI chat panel with message bubbles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        lbl = QLabel("🤖 AI Chat")
        lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setObjectName("ghost")
        clear_btn.setFixedSize(60, 24)
        clear_btn.clicked.connect(self.clear)
        header_layout.addWidget(clear_btn)
        layout.addWidget(header)

        # Scroll area for messages
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(16, 8, 16, 8)
        self._messages_layout.setSpacing(8)
        self._messages_layout.addStretch()
        self._scroll.setWidget(self._messages_container)
        layout.addWidget(self._scroll, 1)

        # Input bar
        input_bar = QWidget()
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 8, 16, 12)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.returnPressed.connect(self._send_user_message)
        input_layout.addWidget(self._input, 1)
        send_btn = QPushButton("Send")
        send_btn.setObjectName("primary")
        send_btn.setFixedSize(70, 36)
        send_btn.clicked.connect(self._send_user_message)
        input_layout.addWidget(send_btn)
        layout.addWidget(input_bar)

        self._current_ai_label = None

    def _add_bubble(self, text, is_ai=False):
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        if is_ai:
            bubble.setStyleSheet(
                "background-color: #DBEAFE; color: #1E3A5F; "
                "border-radius: 10px; padding: 10px 14px; font-size: 13px;"
            )
        else:
            bubble.setStyleSheet(
                "background-color: #E2E8F0; color: #0F172A; "
                "border-radius: 10px; padding: 10px 14px; font-size: 13px;"
            )
        # Insert before the stretch
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))
        return bubble

    def _send_user_message(self):
        text = self._input.text().strip()
        if not text: return
        self._add_bubble(text, is_ai=False)
        self._input.clear()

    def start_ai_message(self):
        self._current_ai_label = self._add_bubble("", is_ai=True)

    def append_ai_token(self, token):
        if self._current_ai_label:
            current = self._current_ai_label.text()
            self._current_ai_label.setText(current + token)

    def end_ai_message(self):
        self._current_ai_label = None

    def add_user_message(self, text):
        self._add_bubble(text, is_ai=False)

    def clear(self):
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # Thread-safe wrappers
    def start_ai_message_safe(self):
        QMetaObject.invokeMethod(self, "_do_start_ai", Qt.ConnectionType.QueuedConnection)

    def append_ai_token_safe(self, token):
        # Use QTimer for thread safety without needing Q_ARG
        QTimer.singleShot(0, lambda: self.append_ai_token(token))

    def end_ai_message_safe(self):
        QMetaObject.invokeMethod(self, "_do_end_ai", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def _do_start_ai(self):
        self.start_ai_message()

    @pyqtSlot()
    def _do_end_ai(self):
        self.end_ai_message()

    def set_enabled_input(self, enabled):
        self._input.setEnabled(enabled)
