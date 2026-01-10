import customtkinter as ctk
import os
from tkinter import messagebox
from pynput.keyboard import Key
from app.engine.recorder_engine import Recorder, Player, HotkeyListener, STOP_HOTKEY, RECORDINGS_DIR

class RecorderTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # State
        self.recorder = Recorder()
        self.player = None
        self.stop_listener = None
        self.compact_mode = False
        
        # Layout: Grid Configuration (2 Columns)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDEBAR (Controls) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Macro Controls", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Big Action Buttons
        self.btn_record = ctk.CTkButton(self.sidebar_frame, text="● REC (F9)", command=self.start_recording, 
                                        fg_color="#e74c3c", hover_color="#c0392b", height=40)
        self.btn_record.grid(row=1, column=0, padx=20, pady=10)

        self.btn_play = ctk.CTkButton(self.sidebar_frame, text="▶ PLAY", command=self.start_playback, 
                                      fg_color="#2ecc71", hover_color="#27ae60", height=40)
        self.btn_play.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_stop = ctk.CTkButton(self.sidebar_frame, text="■ STOP (F10)", command=self.stop_action, state="disabled", 
                                      fg_color="#000000", height=40)
        self.btn_stop.grid(row=3, column=0, padx=20, pady=10)

        # --- RIGHT MAIN AREA ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # 1. Status Dashboard
        self.status_frame = ctk.CTkFrame(self.main_frame, height=100)
        self.status_frame.pack(fill="x", pady=(0, 15))
        
        self.lbl_status = ctk.CTkLabel(self.status_frame, text="Status: Idle", font=ctk.CTkFont(size=16))
        self.lbl_status.pack(side="left", padx=20, pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.status_frame)
        self.progress_bar.pack(side="right", padx=20, pady=15, fill="x", expand=True)
        self.progress_bar.set(0)

        # 2. Configuration Card
        self.config_frame = ctk.CTkFrame(self.main_frame)
        self.config_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(self.config_frame, text="Playback Settings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=10)
        
        self.speed_slider = ctk.CTkSlider(self.config_frame, from_=0.5, to=3.0, number_of_steps=25)
        self.speed_slider.pack(padx=20, pady=(0, 20), fill="x")
        self.speed_slider.set(1.0)
        
        self.chk_loop = ctk.CTkCheckBox(self.config_frame, text="Loop Playback")
        self.chk_loop.pack(padx=20, pady=(0, 15), anchor="w")

        # 3. File Management Card
        self.files_frame = ctk.CTkFrame(self.main_frame)
        self.files_frame.pack(fill="x", pady=(0, 0))
        
        ctk.CTkLabel(self.files_frame, text="Recordings", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=10)
        
        self.combo_files = ctk.CTkComboBox(self.files_frame, values=self.get_recordings())
        self.combo_files.pack(padx=20, pady=(0, 10), fill="x")
        
        self.btn_save = ctk.CTkButton(self.files_frame, text="Save Recording", command=self.save_recording, fg_color="#3498db")
        self.btn_save.pack(side="left", padx=20, pady=15, expand=True)
        
        self.btn_delete = ctk.CTkButton(self.files_frame, text="Delete", command=self.delete_recording, fg_color="#e74c3c", width=80)
        self.btn_delete.pack(side="right", padx=20, pady=15)

        # Init Hotkeys
        self.init_hotkeys()

    # --- LOGIC METHODS ---
    def refresh_file_list(self):
        self.combo_files.configure(values=self.get_recordings())
        if len(self.get_recordings()) > 0:
            self.combo_files.set(self.get_recordings()[0])

    def get_recordings(self):
        if not os.path.exists(RECORDINGS_DIR): return ["No Recordings"]
        files = [f.replace(".json", "") for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
        return files if files else ["No Recordings"]

    def set_status(self, text, color="white"):
        self.lbl_status.configure(text=f"Status: {text}", text_color=color)

    def start_recording(self):
        if self.recorder.recording or (self.player and self.player.playing): return
        
        self.recorder.start()
        self.set_status("RECORDING...", "#e74c3c")
        self.btn_record.configure(state="disabled")
        self.btn_play.configure(state="disabled")
        self.btn_stop.configure(state="normal", fg_color="#c0392b")
        
        if self.stop_listener: self.stop_listener.listener.stop()
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def stop_action(self):
        if self.recorder.recording:
            self.recorder.stop()
            self.set_status("Ready to Save/Play", "#f1c40f")
            self.btn_record.configure(state="normal")
            self.btn_play.configure(state="normal")
            self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
        
        if self.player and self.player.playing:
            self.player.stop()
            self.set_status("Idle", "white")
            self.btn_record.configure(state="normal")
            self.btn_play.configure(state="normal")
            self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
            self.progress_bar.set(0)

    def start_playback(self):
        filename = self.combo_files.get()
        if not self.recorder.events:
            if filename == "No Recordings": return
            path = os.path.join(RECORDINGS_DIR, f"{filename}.json")
            if not self.recorder.load_events(path): return

        speed = self.speed_slider.get()
        loop = bool(self.chk_loop.get())
        
        self.player = Player(self.recorder.events, loop=loop, speed=speed, 
                             progress_callback=self.update_progress,
                             finished_callback=self.stop_action)
        self.player.start()
        
        self.set_status("PLAYING...", "#2ecc71")
        self.btn_record.configure(state="disabled")
        self.btn_play.configure(state="disabled")
        self.btn_stop.configure(state="normal", fg_color="#27ae60")
        
        if self.stop_listener: self.stop_listener.listener.stop()
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def update_progress(self, val):
        self.progress_bar.set(val)

    def save_recording(self):
        if not self.recorder.events:
            messagebox.showwarning("Empty", "Record something first!")
            return
            
        dialog = ctk.CTkInputDialog(text="Name your recording:", title="Save Macro")
        name = dialog.get_input()
        if name:
            self.recorder.save_events(name)
            self.refresh_file_list()
            self.set_status(f"Saved: {name}", "#3498db")

    def delete_recording(self):
        name = self.combo_files.get()
        if name == "No Recordings": return
        try:
            os.remove(os.path.join(RECORDINGS_DIR, f"{name}.json"))
            self.refresh_file_list()
        except: pass

    def init_hotkeys(self):
        START_HOTKEY = {Key.f9}
        self.start_listener = HotkeyListener(self.start_recording, START_HOTKEY)
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)