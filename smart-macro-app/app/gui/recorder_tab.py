import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QSlider, QCheckBox, QComboBox,
    QProgressBar, QFrame, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from pynput.keyboard import Key
from app.engine.recorder_engine import Recorder, Player, HotkeyListener, STOP_HOTKEY, RECORDINGS_DIR
from app.gui.components import Card


class RecorderTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorder = Recorder()
        self.player = None
        self.stop_listener = None

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Left — controls
        ctrl_card = Card("Macro Controls")
        cl = ctrl_card.content_layout()
        self.btn_record = QPushButton("●  REC (F9)")
        self.btn_record.setObjectName("danger")
        self.btn_record.setFixedHeight(42)
        self.btn_record.clicked.connect(self.start_recording)
        cl.addWidget(self.btn_record)

        self.btn_play = QPushButton("▶  PLAY")
        self.btn_play.setObjectName("success")
        self.btn_play.setFixedHeight(42)
        self.btn_play.clicked.connect(self.start_playback)
        cl.addWidget(self.btn_play)

        self.btn_stop = QPushButton("■  STOP (F10)")
        self.btn_stop.setFixedHeight(42)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_action)
        cl.addWidget(self.btn_stop)

        layout.addWidget(ctrl_card, 0, 0)

        # Right area
        right = QVBoxLayout()
        right.setSpacing(12)

        # Status dashboard
        status_card = Card()
        sl = status_card.content_layout()
        row = QHBoxLayout()
        self.lbl_status = QLabel("Status: Idle")
        self.lbl_status.setObjectName("statusText")
        row.addWidget(self.lbl_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        row.addWidget(self.progress_bar, 1)
        sl.addLayout(row)
        right.addWidget(status_card)

        # Config card
        config_card = Card("Playback Settings")
        ccl = config_card.content_layout()

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(300)
        self.speed_slider.setValue(100)
        speed_row.addWidget(self.speed_slider, 1)
        ccl.addLayout(speed_row)

        self.chk_loop = QCheckBox("Loop Playback")
        ccl.addWidget(self.chk_loop)
        right.addWidget(config_card)

        # Recordings
        files_card = Card("Recordings")
        fl = files_card.content_layout()
        self.combo_files = QComboBox()
        self.combo_files.addItems(self.get_recordings())
        fl.addWidget(self.combo_files)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("💾  Save Recording")
        self.btn_save.setObjectName("primary")
        self.btn_save.setFixedHeight(38)
        self.btn_save.clicked.connect(self.save_recording)
        btn_row.addWidget(self.btn_save)
        self.btn_delete = QPushButton("🗑️  Delete")
        self.btn_delete.setFixedHeight(38)
        self.btn_delete.clicked.connect(self.delete_recording)
        btn_row.addWidget(self.btn_delete)
        fl.addLayout(btn_row)
        right.addWidget(files_card)
        right.addStretch()

        layout.addLayout(right, 0, 1)
        layout.setColumnStretch(1, 1)

        self.init_hotkeys()

    # --- Logic ---
    def refresh_file_list(self):
        self.combo_files.clear()
        self.combo_files.addItems(self.get_recordings())

    def get_recordings(self):
        if not os.path.exists(RECORDINGS_DIR): return ["No Recordings"]
        files = [f.replace(".json", "") for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
        return files if files else ["No Recordings"]

    def set_status(self, text, color=None):
        style = f"color: {color}; font-weight: bold;" if color else ""
        self.lbl_status.setText(f"Status: {text}")
        self.lbl_status.setStyleSheet(style)

    def start_recording(self):
        if self.recorder.recording or (self.player and self.player.playing): return
        self.recorder.start()
        self.set_status("RECORDING...", "#DC2626")
        self.btn_record.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if self.stop_listener: self.stop_listener.listener.stop()
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def stop_action(self):
        if self.recorder.recording:
            self.recorder.stop()
            self.set_status("Ready to Save/Play", "#D97706")
            self.btn_record.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.progress_bar.setValue(0)

        if self.player and self.player.playing:
            self.player.stop()
            self.set_status("Idle")
            self.btn_record.setEnabled(True)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.progress_bar.setValue(0)

    def start_playback(self):
        filename = self.combo_files.currentText()
        if not self.recorder.events:
            if filename == "No Recordings": return
            path = os.path.join(RECORDINGS_DIR, f"{filename}.json")
            if not self.recorder.load_events(path): return

        speed = self.speed_slider.value() / 100.0
        loop = self.chk_loop.isChecked()
        self.player = Player(self.recorder.events, loop=loop, speed=speed,
                             progress_callback=self.update_progress,
                             finished_callback=self.stop_action)
        self.player.start()
        self.set_status("PLAYING...", "#059669")
        self.btn_record.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(True)
        if self.stop_listener: self.stop_listener.listener.stop()
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def update_progress(self, val):
        self.progress_bar.setValue(int(val * 100))

    def save_recording(self):
        if not self.recorder.events:
            QMessageBox.warning(self, "Empty", "Record something first!")
            return
        name, ok = QInputDialog.getText(self, "Save Macro", "Name your recording:")
        if ok and name:
            self.recorder.save_events(name)
            self.refresh_file_list()
            self.set_status(f"Saved: {name}", "#2563EB")

    def delete_recording(self):
        name = self.combo_files.currentText()
        if name == "No Recordings": return
        try:
            os.remove(os.path.join(RECORDINGS_DIR, f"{name}.json"))
            self.refresh_file_list()
        except: pass

    def init_hotkeys(self):
        START_HOTKEY = {Key.f9}
        self.start_listener = HotkeyListener(self.start_recording, START_HOTKEY)
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)