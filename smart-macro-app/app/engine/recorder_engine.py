import threading
import time
import math
import json
import os
import ctypes
import pyautogui
import pygetwindow as gw
import uuid
from pynput import mouse, keyboard
from pynput.keyboard import Key, KeyCode, Listener as KeyboardListener, Controller as KeyboardController
from pynput.mouse import Listener as MouseListener, Controller as MouseController

# FORCE high-DPI awareness on Windows to prevent coordinate shifting
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

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
        
        # Image Storage
        self.image_folder = os.path.join(RECORDINGS_DIR, "images")
        os.makedirs(self.image_folder, exist_ok=True)
        self.session_id = None

    def start(self):
        self.events = []
        self.start_time = time.time()
        self.session_id = str(uuid.uuid4())[:8]
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
        if not self.recording or not pressed: return
        
        # Gather Context
        timestamp = time.time() - self.start_time
        
        # 1. Window Capture
        win_title = None
        rel_x = x
        rel_y = y
        try:
            # Prioritize Active Window if click is inside it
            active = gw.getActiveWindow()
            target_win = None
            if active and (active.left <= x <= active.right and active.top <= y <= active.bottom):
                target_win = active
            else:
                 # Fallback
                wins = gw.getWindowsAt(x, y)
                if wins: target_win = wins[0]
            
            if target_win:
                win_title = target_win.title
                rel_x = x - target_win.left
                rel_y = y - target_win.top
                print(f"[REC] Window: '{win_title}' | Rel: ({rel_x}, {rel_y})")
        except: pass

        # 2. Image Anchor
        img_path = None
        try:
            img_name = f"{self.session_id}_{int(timestamp*1000)}.png"
            full_path = os.path.join(self.image_folder, img_name)
            # Capture 60x60 around click
            capture_region = (x - 30, y - 30, 60, 60)
            pyautogui.screenshot(region=capture_region).save(full_path)
            img_path = full_path
        except Exception as e:
            print(f"[REC] Img Capture Error: {e}")

        self.events.append({
            'type': 'mouse', 
            'action': 'click', 
            'position': (x, y), 
            'relative_pos': (rel_x, rel_y),
            'window_title': win_title,
            'image_path': img_path,
            'button': button.name, 
            'pressed': pressed, 
            'time': timestamp
        })

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
                    if event.get('pressed', False): # Only handle press for complex logic
                        target_x, target_y = event['position']
                        
                        # --- ROBUST PLAYBACK LOGIC ---
                        win_title = event.get('window_title')
                        if win_title:
                            try:
                                # Find Valid Window
                                candidates = [w for w in gw.getWindowsWithTitle(win_title) if w.title]
                                
                                # Exact vs Fuzzy Match
                                target_win = None
                                for w in candidates:
                                    if w.title == win_title: 
                                        target_win = w
                                        break
                                if not target_win: # Fuzzy fallback
                                    clean = win_title.lower().strip()
                                    for w in gw.getAllWindows():
                                         if w.title and clean in w.title.lower():
                                             target_win = w
                                             break
                                
                                if target_win:
                                    if target_win.isMinimized:
                                        target_win.restore()
                                        time.sleep(0.2)
                                    try:
                                        target_win.activate()
                                        # Aggressive Focus
                                        try:
                                            hwnd = target_win._hWnd
                                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                                        except: pass
                                        time.sleep(0.2)
                                    except: pass
                                    
                                    # Fallback to Relative Coords
                                    if 'relative_pos' in event:
                                        rx, ry = event['relative_pos']
                                        target_x = target_win.left + rx
                                        target_y = target_win.top + ry
                                        # print(f"Window Fallback: ({target_x}, {target_y})")
                            except Exception as e:
                                print(f"Win Error: {e}")

                        # --- IMAGE SEARCH (PRIMARY) ---
                        if event.get('image_path') and os.path.exists(event['image_path']):
                            # Retry Loop: Wait for image to appear (animations, loading)
                            start_search = time.time()
                            found = None
                            
                            while time.time() - start_search < 2.0: # Try for 2 seconds
                                try:
                                    found = pyautogui.locateCenterOnScreen(event['image_path'], confidence=0.8)
                                    if found: break
                                except: pass
                                time.sleep(0.1)
                                
                            if found:
                                print(f"✅ Image Match: {found}")
                                target_x, target_y = found
                            else:
                                print("⚠️ Image not found after 2s, using coords")
                        
                        # EXECUTE CLICK
                        # Use pyautogui for click to ensure it hits the right spot visually
                        pyautogui.click(target_x, target_y, button=event['button'])
                        
                        # Sync pynput controller just in case
                        self.mouse_controller.position = (target_x, target_y)
                    else:
                         pass # Release is handled by pyautogui.click usually, or we skip
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