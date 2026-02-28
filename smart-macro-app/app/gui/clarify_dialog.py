"""
Clarification Dialog — PyQt6
Modal dialog that shows a task-specific starter question and collects user answers.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QTimer


class ClarifyDialog(QDialog):
    """
    Floating modal dialog for AI clarification before executing tasks.

    Shows an instant starter question relevant to the task,
    then optionally streams additional AI questions.
    Calls on_proceed(answer) or on_cancel().
    """

    # Starter questions shown immediately — no LLM needed
    _STARTER_QUESTIONS = {
        "ppt": "What topic is your presentation about, and who is the audience?",
        "pdf": "What subject should the PDF cover, and what tone do you prefer?",
        "word_process": "What changes would you like me to make to this document?",
        "excel_process": "Which columns are most important, and what should the output look like?",
        "enhance": "What matters most — grammar, tone, clarity, or structure?",
        "smart_fill": "Any placeholders to leave empty or specific format preferences?",
        "directory": "Is this for a new project or an existing one? What tech stack?",
    }

    def __init__(self, parent=None, task_label="", task_type="", on_proceed=None, on_cancel=None):
        super().__init__(parent)
        self.on_proceed = on_proceed
        self.on_cancel_cb = on_cancel

        self.setWindowTitle(f"AI Clarification — {task_label}")
        self.setFixedSize(560, 480)
        self.setModal(True)

        # Force explicit colors so text is always visible regardless of theme
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                color: #1a1a2e;
            }
            QScrollArea {
                background-color: #FFFFFF;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #FFFFFF;
            }
            QLabel {
                color: #1a1a2e;
                background: transparent;
            }
            QLineEdit {
                background-color: #F3F4F6;
                color: #1a1a2e;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #4F46E5;
            }
            QPushButton#dialogPrimary {
                background-color: #4F46E5;
                color: #1a1a2e;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#dialogPrimary:hover {
                background-color: #4338CA;
            }
            QPushButton#dialogGhost {
                background: transparent;
                color: #6b7280;
                border: none;
                font-size: 12px;
            }
            QPushButton#dialogGhost:hover {
                color: #1a1a2e;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #F9FAFB; border-bottom: 1px solid #E5E7EB;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 12)
        title = QLabel(task_label)
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #1a1a2e;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        step_lbl = QLabel("Preferences")
        step_lbl.setStyleSheet("font-size: 11px; color: #9ca3af; font-weight: 500;")
        header_layout.addWidget(step_lbl)
        layout.addWidget(header)

        # Chat scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background-color: #FFFFFF;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(20, 16, 20, 16)
        self._msg_layout.setSpacing(10)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, 1)

        # Input row
        input_bar = QWidget()
        input_bar.setStyleSheet("background-color: #F9FAFB; border-top: 1px solid #E5E7EB;")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(20, 12, 20, 8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type your answer or preferences...")
        self._input.returnPressed.connect(self._submit)
        input_layout.addWidget(self._input, 1)
        submit_btn = QPushButton("Send")
        submit_btn.setObjectName("dialogPrimary")
        submit_btn.setFixedHeight(36)
        submit_btn.clicked.connect(self._submit)
        input_layout.addWidget(submit_btn)
        layout.addWidget(input_bar)

        # Skip link
        skip_btn = QPushButton("Skip — run with defaults")
        skip_btn.setObjectName("dialogGhost")
        skip_btn.setFixedHeight(28)
        skip_btn.clicked.connect(self._skip)
        skip_wrap = QWidget()
        skip_wrap.setStyleSheet("background-color: #FFFFFF;")
        skip_layout = QHBoxLayout(skip_wrap)
        skip_layout.setContentsMargins(0, 0, 0, 12)
        skip_layout.addStretch()
        skip_layout.addWidget(skip_btn)
        skip_layout.addStretch()
        layout.addWidget(skip_wrap)

        self._current_ai_label = None
        self._token_buffer = []

        # Show the starter question with a typing animation
        starter = self._STARTER_QUESTIONS.get(task_type, "What are your preferences for this task?")
        self._typing_label = self._add_bubble("", is_ai=True)
        self._typing_text = starter
        self._typing_index = 0
        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._type_next_char)
        self._typing_timer.start(30)  # 30ms per character

        self.show()

    def _type_next_char(self):
        if self._typing_index < len(self._typing_text):
            self._typing_label.setText(self._typing_text[:self._typing_index + 1])
            self._typing_index += 1
        else:
            self._typing_timer.stop()

    def _add_bubble(self, text, is_ai=False):
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        if is_ai:
            bubble.setStyleSheet(
                "background-color: #EEF2FF; color: #1e1b4b; "
                "border-radius: 10px; padding: 12px 16px; font-size: 13px; "
                "border: 1px solid #C7D2FE;"
            )
        else:
            bubble.setStyleSheet(
                "background-color: #F3F4F6; color: #1a1a2e; "
                "border-radius: 10px; padding: 12px 16px; font-size: 13px; "
                "border: 1px solid #E5E7EB;"
            )
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))
        return bubble

    # Thread-safe wrappers for additional AI streaming (optional)
    def start_ai_message_safe(self):
        QTimer.singleShot(0, self._do_start_ai)

    def append_ai_token_safe(self, token):
        QTimer.singleShot(0, lambda t=token: self._do_append_token(t))

    def end_ai_message_safe(self):
        QTimer.singleShot(0, self._do_end_ai)

    def _do_start_ai(self):
        self._current_ai_label = self._add_bubble("", is_ai=True)
        if self._token_buffer:
            self._current_ai_label.setText("".join(self._token_buffer))
            self._token_buffer.clear()

    def _do_append_token(self, token):
        if self._current_ai_label:
            current = self._current_ai_label.text()
            self._current_ai_label.setText(current + token)
        else:
            self._token_buffer.append(token)

    def _do_end_ai(self):
        self._current_ai_label = None

    def _submit(self):
        answer = self._input.text().strip()
        if not answer:
            return
        self._submitted = True
        self._add_bubble(answer, is_ai=False)
        self._input.clear()
        if self.on_proceed:
            self.on_proceed(answer)
        self.close()

    def _skip(self):
        self._submitted = True
        if self.on_proceed:
            self.on_proceed("")
        self.close()

    def closeEvent(self, event):
        if not getattr(self, '_submitted', False) and self.on_cancel_cb:
            self.on_cancel_cb()
        super().closeEvent(event)
