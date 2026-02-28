import threading
import time
import math
import json
import os
import customtkinter as ctk  # The modern UI library
from tkinter import messagebox
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode, Listener as KeyboardListener, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Controller as MouseController

# --- CONFIGURATION ---
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

STOP_HOTKEY = {Key.f10}
RECORDINGS_DIR = "recordings"

if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

# --- LOGIC CLASSES (Kept identical to ensure functionality) ---

class Recorder:
    def __init__(self):
        self.events = []
        self.start_time = None
        self.recording = False
        self.keyboard_listener = None
        self.mouse_listener = None
        self.last_mouse_pos = (0, 0) # To track distance

    def start(self):
        self.events = []
        self.start_time = time.time()
        self.recording = True
        self.keyboard_listener = KeyboardListener(on_press=self.on_press, on_release=self.on_release)
        self.mouse_listener = MouseListener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        self.keyboard_listener.start()
        self.mouse_listener.start()
        print("Recording started...")

    def stop(self):
        self.recording = False
        if self.keyboard_listener: self.keyboard_listener.stop()
        if self.mouse_listener: self.mouse_listener.stop()
        print("Recording stopped.")

    # --- INPUT HANDLERS ---
    def on_press(self, key):
        if not self.recording or key in STOP_HOTKEY: return
        self.events.append({'type': 'keyboard', 'action': 'press', 'key': self.get_key_name(key), 'time': time.time() - self.start_time})

    def on_release(self, key):
        if not self.recording or key in STOP_HOTKEY: return
        self.events.append({'type': 'keyboard', 'action': 'release', 'key': self.get_key_name(key), 'time': time.time() - self.start_time})

    def on_move(self, x, y):
        if not self.recording: return
        
        # OPTIMIZATION: Only record if mouse moved more than 5 pixels
        # This reduces "Event Flooding" by 90% without affecting accuracy
        dist = math.hypot(x - self.last_mouse_pos[0], y - self.last_mouse_pos[1])
        if dist < 5: 
            return 
            
        self.last_mouse_pos = (x, y)
        self.events.append({'type': 'mouse', 'action': 'move', 'position': (x, y), 'time': time.time() - self.start_time})

    def on_click(self, x, y, button, pressed):
        if not self.recording: return
        self.events.append({'type': 'mouse', 'action': 'click', 'position': (x, y), 'button': button.name, 'pressed': pressed, 'time': time.time() - self.start_time})

    def on_scroll(self, x, y, dx, dy):
        if not self.recording: return
        self.events.append({'type': 'mouse', 'action': 'scroll', 'position': (x, y), 'scroll': (dx, dy), 'time': time.time() - self.start_time})

    def get_key_name(self, key):
        try: return key.char
        except AttributeError: return str(key)

    def save_events(self, name):
        filename = os.path.join(RECORDINGS_DIR, f"{name}.json")
        try:
            with open(filename, 'w') as f: json.dump(self.events, f, indent=4)
            return filename
        except Exception: return None

    def load_events(self, filename):
        try:
            with open(filename, 'r') as f: self.events = json.load(f)
            return True
        except Exception: return False

class Player:
    def __init__(self, events, loop=False, speed=1.0, progress_callback=None, finished_callback=None):
        self.events = events
        self.playing = False
        self.loop = loop
        self.speed = speed
        self.keyboard_controller = KeyboardController()
        self.mouse_controller = MouseController()
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def start(self):
        if not self.events: return
        self.playing = True
        threading.Thread(target=self.play_loop, daemon=True).start()

    def stop(self):
        self.playing = False

    def play_loop(self):
        while self.playing:
            try:
                if not self.events: break
                
                start_real_time = time.perf_counter()
                total_duration = self.events[-1]['time']
                
                for event in self.events:
                    if not self.playing: break
                    
                    # Calculate when this event SHOULD happen (scaled by speed)
                    target_offset = event['time'] / self.speed
                    target_real_time = start_real_time + target_offset
                    
                    # PRECISE WAIT LOGIC
                    while True:
                        current_time = time.perf_counter()
                        remaining = target_real_time - current_time
                        
                        if remaining <= 0:
                            break # Time to execute!
                        
                        # If wait is long (> 15ms), use system sleep (saves CPU)
                        if remaining > 0.015:
                            time.sleep(remaining - 0.005) # Sleep but wake up slightly early
                        else:
                            # If wait is tiny (< 15ms), "Busy Wait" (burn CPU for precision)
                            # This bypasses the Windows Sleep lag
                            pass 

                    if self.playing:
                        self.execute_event(event)
                        # Update UI Progress
                        if self.progress_callback and total_duration > 0:
                            self.progress_callback(event['time'] / total_duration)

                if not self.loop:
                    self.playing = False
                    if self.finished_callback: self.finished_callback()
                    
            except Exception as e:
                print(f"Error: {e}")
                self.playing = False

    def execute_event(self, event):
        # (Same execution logic as before)
        try:
            if event['type'] == 'keyboard':
                key = self.parse_key(event['key'])
                if event['action'] == 'press': self.keyboard_controller.press(key)
                elif event['action'] == 'release': self.keyboard_controller.release(key)
            elif event['type'] == 'mouse':
                if event['action'] == 'move': 
                    self.mouse_controller.position = event['position']
                elif event['action'] == 'click':
                    btn = getattr(mouse.Button, event['button'], mouse.Button.left)
                    if event['pressed']: self.mouse_controller.press(btn)
                    else: self.mouse_controller.release(btn)
                elif event['action'] == 'scroll': 
                    self.mouse_controller.scroll(*event['scroll'])
        except Exception: pass

    def parse_key(self, key_str):
        if len(key_str) == 1: return key_str
        return getattr(Key, key_str.replace('Key.', ''), key_str)

class HotkeyListener:
    def __init__(self, callback, keys):
        self.callback = callback
        self.keys = keys
        self.current_keys = set()
        self.listener = KeyboardListener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def on_press(self, key):
        self.current_keys.add(key)
        if self.keys.issubset(self.current_keys): self.callback()

    def on_release(self, key):
        if key in self.current_keys: self.current_keys.remove(key)

# --- MODERN UI CLASS ---

class ModernApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Fantastic 4 - Smart Macro Recorder")
        self.geometry("800x500")
        self.resizable(False, False)
        
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
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Smart Macro", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Big Action Buttons`
        self.btn_record = ctk.CTkButton(self.sidebar_frame, text="● REC (f9)", command=self.start_recording, 
                                        fg_color="#e74c3c", hover_color="#c0392b", height=40)
        self.btn_record.grid(row=1, column=0, padx=20, pady=10)

        self.btn_play = ctk.CTkButton(self.sidebar_frame, text="▶ PLAY", command=self.start_playback, 
                                      fg_color="#2ecc71", hover_color="#27ae60", height=40)
        self.btn_play.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_stop = ctk.CTkButton(self.sidebar_frame, text="■ STOP (f10)", command=self.stop_action, state="disabled", 
                                      fg_color="#000000", height=40)
        self.btn_stop.grid(row=3, column=0, padx=20, pady=10)

        # Compact Toggle at bottom of sidebar
        self.switch_compact = ctk.CTkSwitch(self.sidebar_frame, text="Compact Mode", command=self.toggle_compact)
        self.switch_compact.grid(row=5, column=0, padx=20, pady=20, sticky="s")

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
        self.chk_loop.select()

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
        
        # Handle Close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- UI HELPERS ---
    def refresh_file_list(self):
        self.combo_files.configure(values=self.get_recordings())
        self.combo_files.set(self.get_recordings()[0])

    def get_recordings(self):
        files = [f.replace(".json", "") for f in os.listdir(RECORDINGS_DIR) if f.endswith(".json")]
        return files if files else ["No Recordings"]

    def set_status(self, text, color="white"):
        self.lbl_status.configure(text=f"Status: {text}", text_color=color)

    # --- ACTIONS ---
    def start_recording(self):
        if self.recorder.recording or (self.player and self.player.playing): return
        
        self.recorder.start()
        self.set_status("RECORDING...", "#e74c3c")
        self.btn_record.configure(state="disabled")
        self.btn_play.configure(state="disabled")
        self.btn_stop.configure(state="normal", fg_color="#c0392b")
        
        # Update hotkey
        if self.stop_listener: self.stop_listener.listener.stop()
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def stop_action(self):
        # Stop Recording
        if self.recorder.recording:
            self.recorder.stop()
            self.set_status("Ready to Save/Play", "#f1c40f")
            self.btn_record.configure(state="normal")
            self.btn_play.configure(state="normal")
            self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
        
        # Stop Playback
        if self.player and self.player.playing:
            self.player.stop()
            self.set_status("Idle", "white")
            self.btn_record.configure(state="normal")
            self.btn_play.configure(state="normal")
            self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
            self.progress_bar.set(0)

    def start_playback(self):
        filename = self.combo_files.get()
        # If we have unsaved events in memory, use those first. Otherwise load file.
        if not self.recorder.events:
            if filename == "No Recordings": return
            if not self.recorder.load_events(os.path.join(RECORDINGS_DIR, f"{filename}.json")): return

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
        os.remove(os.path.join(RECORDINGS_DIR, f"{name}.json"))
        self.refresh_file_list()

    # --- COMPACT MODE & UTILS ---
    def toggle_compact(self):
        self.compact_mode = not self.compact_mode
        if self.compact_mode:
            self.geometry("250x300")
            self.main_frame.grid_forget() # Hide main area
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew") # Sidebar takes full space
            self.logo_label.grid_forget() # Hide logo to save space
            self.switch_compact.configure(text="Full Mode")
            self.attributes("-topmost", True)
        else:
            self.geometry("800x500")
            self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
            self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
            self.switch_compact.configure(text="Compact Mode")
            self.attributes("-topmost", False)

    def init_hotkeys(self):
        # Hotkey for 'R' to record
        START_HOTKEY = {Key.f9}
        self.start_listener = HotkeyListener(self.start_recording, START_HOTKEY)
        self.stop_listener = HotkeyListener(self.stop_action, STOP_HOTKEY)

    def on_closing(self):
        if self.recorder.recording: self.recorder.stop()
        if self.player: self.player.stop()
        if self.start_listener: self.start_listener.listener.stop()
        if self.stop_listener: self.stop_listener.listener.stop()
        self.destroy()
        os._exit(0) # Force kill threads

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()