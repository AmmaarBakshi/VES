"""
Web Scraper Tab — PyQt6
Record and replay browser automation via Playwright.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from app.engine.web_recorder import (
    WebRecorder, WebPlayer, get_saved_recordings,
    delete_recording, RECORDINGS_DIR
)
from app.gui.components import Card


class WebScraperTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorder = WebRecorder()
        self.player = WebPlayer()

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Left — controls
        ctrl_card = Card("Web Scraper")
        cl = ctrl_card.content_layout()

        self.btn_record = QPushButton("●  RECORD")
        self.btn_record.setObjectName("danger")
        self.btn_record.setFixedHeight(42)
        self.btn_record.clicked.connect(self.start_recording)
        cl.addWidget(self.btn_record)

        self.btn_stop = QPushButton("■  STOP")
        self.btn_stop.setFixedHeight(42)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_action)
        cl.addWidget(self.btn_stop)

        self.btn_play = QPushButton("▶  PLAY")
        self.btn_play.setObjectName("success")
        self.btn_play.setFixedHeight(42)
        self.btn_play.clicked.connect(self.start_playback)
        cl.addWidget(self.btn_play)

        layout.addWidget(ctrl_card, 0, 0)

        # Right area
        right = QVBoxLayout()
        right.setSpacing(12)

        # Status
        status_card = Card()
        sl = status_card.content_layout()
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setObjectName("statusText")
        sl.addWidget(self.lbl_status)
        right.addWidget(status_card)

        # Instructions
        info_card = Card("How to Use")
        il = info_card.content_layout()
        instructions = (
            "1. Click RECORD to start browser recording\n"
            "2. Browser opens automatically — perform your actions\n"
            "3. Click STOP when finished\n"
            "4. Recording auto-saves with timestamp\n"
            "5. Select recording and click PLAY to replay"
        )
        lbl = QLabel(instructions)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #64748B; font-size: 12px;")
        il.addWidget(lbl)
        right.addWidget(info_card)

        # Recordings
        files_card = Card("Saved Recordings")
        fl = files_card.content_layout()
        self.combo_files = QComboBox()
        self.combo_files.addItems(self.get_recordings())
        fl.addWidget(self.combo_files)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄  Refresh")
        self.btn_refresh.setObjectName("primary")
        self.btn_refresh.setFixedHeight(38)
        self.btn_refresh.clicked.connect(self.refresh_file_list)
        btn_row.addWidget(self.btn_refresh)
        self.btn_open_folder = QPushButton("📁  Open Folder")
        self.btn_open_folder.setFixedHeight(38)
        self.btn_open_folder.clicked.connect(self.open_recordings_folder)
        btn_row.addWidget(self.btn_open_folder)
        self.btn_delete = QPushButton("🗑️  Delete")
        self.btn_delete.setFixedHeight(38)
        self.btn_delete.clicked.connect(self.delete_recording_action)
        btn_row.addWidget(self.btn_delete)
        fl.addLayout(btn_row)
        right.addWidget(files_card)
        right.addStretch()

        layout.addLayout(right, 0, 1)
        layout.setColumnStretch(1, 1)
        self.refresh_file_list()

    # --- Logic ---
    def get_recordings(self):
        recordings = get_saved_recordings()
        return recordings if recordings else ["No Recordings"]

    def refresh_file_list(self):
        recordings = self.get_recordings()
        self.combo_files.clear()
        self.combo_files.addItems(recordings)

    def set_status(self, text, color=None):
        style = f"color: {color}; font-weight: bold;" if color else ""
        self.lbl_status.setText(f"Status: {text}")
        self.lbl_status.setStyleSheet(style)

    def start_recording(self):
        if self.recorder.recording or self.player.playing: return
        success = self.recorder.start_recording()
        if success:
            self.set_status("RECORDING... (Browser should open)", "#DC2626")
            self.btn_record.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(True)
        else:
            self.set_status("Failed to start recording", "#DC2626")
            QMessageBox.critical(self, "Recording Error",
                "Failed to start Playwright codegen.\n\n"
                "Make sure Playwright is installed:\n"
                "1. pip install playwright\n"
                "2. playwright install chromium")

    def stop_action(self):
        if self.recorder.recording:
            success = self.recorder.stop_recording()
            if success:
                saved_path = self.recorder.save_recording()
                if saved_path:
                    filename = os.path.basename(saved_path).replace(".py", "")
                    self.set_status(f"Saved: {filename}", "#059669")
                    self.refresh_file_list()
                else:
                    self.set_status("Recording stopped (save failed)", "#D97706")
            else:
                self.set_status("Recording stopped (no script captured)", "#D97706")
            self.btn_record.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)

        elif self.player.playing:
            self.player.stop_playback()
            self.set_status("Playback stopped", "#D97706")
            self.btn_record.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def start_playback(self):
        filename = self.combo_files.currentText()
        if filename == "No Recordings":
            QMessageBox.information(self, "No Recordings", "No recordings available to play.")
            return
        script_path = os.path.join(RECORDINGS_DIR, f"{filename}.py")
        if not os.path.exists(script_path):
            QMessageBox.critical(self, "File Not Found", f"Recording not found: {filename}")
            self.refresh_file_list()
            return

        self.set_status("PLAYING...", "#059669")
        self.btn_record.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(True)
        success = self.player.play_recording(
            script_path,
            on_complete=self._on_playback_complete,
            on_error=self._on_playback_error
        )
        if not success:
            self.set_status("Failed to start playback", "#DC2626")
            self.btn_record.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _on_playback_complete(self):
        from PyQt6.QtCore import QMetaObject, Qt as QtCore_Qt
        QMetaObject.invokeMethod(self, "_reset_after_playback", QtCore_Qt.ConnectionType.QueuedConnection)

    def _on_playback_error(self, error_msg):
        from PyQt6.QtCore import QMetaObject, Qt as QtCore_Qt
        QMetaObject.invokeMethod(self, "_reset_after_playback", QtCore_Qt.ConnectionType.QueuedConnection)

    def _reset_after_playback(self):
        self.set_status("Idle")
        self.btn_record.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def delete_recording_action(self):
        filename = self.combo_files.currentText()
        if filename == "No Recordings": return
        confirm = QMessageBox.question(self, "Confirm Delete",
            f"Delete recording '{filename}'?\n\nThis cannot be undone.")
        if confirm == QMessageBox.StandardButton.Yes:
            success = delete_recording(filename)
            if success:
                self.set_status(f"Deleted: {filename}", "#DC2626")
                self.refresh_file_list()

    def open_recordings_folder(self):
        if not os.path.exists(RECORDINGS_DIR):
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
        if os.name == 'nt':
            os.startfile(RECORDINGS_DIR)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', RECORDINGS_DIR])
