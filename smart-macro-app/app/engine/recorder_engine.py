import threading
import time
import math
import json
import os
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode, Listener as KeyboardListener, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Controller as MouseController

# Save recordings in the user_data folder we created earlier
RECORDINGS_DIR = "user_data/recordings"
if not os.path.exists(RECORDINGS_DIR):
    os.makedirs(RECORDINGS_DIR)

STOP_HOTKEY = {Key.f10}

class Recorder:
    def __init__(self):
        self.events = []
        self.start_time = None
        self.recording = False
        self.keyboard_listener = None
        self.mouse_listener = None
        self.last_mouse_pos = (0, 0)

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

    def on_press(self, key):
        if not self.recording or key in STOP_HOTKEY: return
        self.events.append({'type': 'keyboard', 'action': 'press', 'key': self.get_key_name(key), 'time': time.time() - self.start_time})

    def on_release(self, key):
        if not self.recording or key in STOP_HOTKEY: return
        self.events.append({'type': 'keyboard', 'action': 'release', 'key': self.get_key_name(key), 'time': time.time() - self.start_time})

    def on_move(self, x, y):
        if not self.recording: return
        # Optimization: Only record if moved > 5 pixels
        dist = math.hypot(x - self.last_mouse_pos[0], y - self.last_mouse_pos[1])
        if dist < 5: return 
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
                    
                    target_offset = event['time'] / self.speed
                    target_real_time = start_real_time + target_offset
                    
                    while True:
                        current_time = time.perf_counter()
                        remaining = target_real_time - current_time
                        if remaining <= 0: break
                        if remaining > 0.015: time.sleep(remaining - 0.005)
                        else: pass 

                    if self.playing:
                        self.execute_event(event)
                        if self.progress_callback and total_duration > 0:
                            self.progress_callback(event['time'] / total_duration)

                if not self.loop:
                    self.playing = False
                    if self.finished_callback: self.finished_callback()
                    
            except Exception as e:
                print(f"Error: {e}")
                self.playing = False

    def execute_event(self, event):
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