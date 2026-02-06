import time
import threading
import pyautogui
import pygetwindow as gw
from pynput import mouse, keyboard
import json
import math
import os
import uuid
import ctypes
import win32gui
import win32process
import psutil

# FORCE HIGH-DPI AWARENESS (Fixes coordinate drift on modern screens)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try: ctypes.windll.user32.SetProcessDPIAware()
    except: pass

pyautogui.FAILSAFE = True 

class ActionRepeater:
    def __init__(self):
        self.actions = []
        self.recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.key_listener = None
        
        # SETTINGS
        self.base_folder = "user_data/macros"
        self.move_duration = 0.2
        self.speed_multiplier = 1.0

    def get_window_info_under_mouse(self, x, y):
        """
        NUCLEAR OPTION: Uses low-level Windows API to find exactly which 
        process and window is under the mouse cursor.
        """
        try:
            # 1. Get HWND (Window Handle) at coordinates
            hwnd = win32gui.WindowFromPoint((x, y))
            
            # 2. Walk up to the root window (in case we clicked a button inside)
            while win32gui.GetParent(hwnd):
                hwnd = win32gui.GetParent(hwnd)
            
            # 3. Get Process Name (e.g., 'notepad.exe')
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except:
                process_name = "Unknown"

            # 4. Get Window Rect & Title
            rect = win32gui.GetWindowRect(hwnd)
            win_x, win_y = rect[0], rect[1]
            title = win32gui.GetWindowText(hwnd)
            
            return {
                "title": title,
                "process": process_name,
                "x": win_x,
                "y": win_y,
                "hwnd": hwnd # Only for recording, invalid on restart
            }
        except Exception as e:
            print(f"Debug Info Error: {e}")
            return None

    def start_recording(self):
        self.actions = []
        self.recording = True
        self.start_time = time.time()
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.key_listener = keyboard.Listener(on_press=self.on_press)
        self.mouse_listener.start()
        self.key_listener.start()
        print("🔴 Recording... (Tracking Process Names)")

    def stop_recording(self):
        self.recording = False
        if self.mouse_listener: self.mouse_listener.stop()
        if self.key_listener: self.key_listener.stop()
        print(f"⏹ Stopped. Captured {len(self.actions)} actions.")
        return self.actions

    def save_macro(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Generate ID if saving new
        data = {"actions": self.actions}
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_and_play(self, filepath, speed=1.0):
        try:
            self.speed_multiplier = speed
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list): actions = data
            else: actions = data.get("actions", [])
            
            self.play_actions(actions)
            return "✅ Macro Finished"
        except pyautogui.FailSafeException:
            return "🛑 Stopped by User"
        except Exception as e:
            return f"❌ Error: {e}"

    def on_click(self, x, y, button, pressed):
        if pressed and self.recording:
            dt = time.time() - self.start_time
            
            # INTELLIGENT CAPTURE
            win_info = self.get_window_info_under_mouse(x, y)
            
            action = {
                'type': 'click', 
                'x': x, 
                'y': y, 
                'button': str(button), 
                'time': dt,
                # Store Process info for robust replay
                'process_name': win_info['process'] if win_info else None,
                'window_title': win_info['title'] if win_info else None,
                'relative_x': (x - win_info['x']) if win_info else 0,
                'relative_y': (y - win_info['y']) if win_info else 0
            }
            self.actions.append(action)
            
            if win_info:
                print(f"🖱️ Clicked [{win_info['process']}] at ({action['relative_x']}, {action['relative_y']})")

    def on_press(self, key):
        if self.recording:
            try: k = key.char
            except: k = str(key)
            if k == 'Key.f9': return 
            self.actions.append({'type': 'press', 'key': k, 'time': time.time() - self.start_time})

    def find_target_window(self, process_name, window_title):
        """
        Robust Window Finder:
        1. Checks Exact Title
        2. Checks Process Name (The most robust way)
        """
        # Strategy 1: Find by exact title (fastest)
        if window_title:
            try:
                wins = gw.getWindowsWithTitle(window_title)
                if wins: return wins[0]
            except: pass

        # Strategy 2: Find by Process Name (iterate all windows)
        # This fixes "Untitled - Notepad" changing to "Notes - Notepad"
        if process_name:
            def callback(hwnd, result_list):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    if proc.name().lower() == process_name.lower():
                        if win32gui.IsWindowVisible(hwnd):
                            result_list.append(hwnd)
                except: pass
            
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            
            if hwnds:
                # If multiple windows (e.g. 2 Chrome tabs), try to match title fuzzy
                best_hwnd = hwnds[0]
                if window_title:
                    for h in hwnds:
                        t = win32gui.GetWindowText(h)
                        if t in window_title or window_title in t:
                            best_hwnd = h
                            break
                
                # Convert HWND to pygetwindow object for easy manipulation
                # or just use win32gui to get rect
                rect = win32gui.GetWindowRect(best_hwnd)
                return {
                    'left': rect[0], 'top': rect[1], 
                    'hwnd': best_hwnd, 'obj': None # Using raw rect logic
                }
        return None

    def play_actions(self, actions):
        if not actions: return
        last_action_time = actions[0]['time']

        print("\n▶️ PLAYBACK STARTED")

        for action in actions:
            # Timing
            delay = action['time'] - last_action_time
            if delay > 0.5: delay = 0.5 # Smart speedup
            if delay > 0: time.sleep(delay / self.speed_multiplier)
            last_action_time = action['time']

            if action['type'] == 'click':
                target_x, target_y = action['x'], action['y'] # Default to absolute
                
                # PROCESS LOCK REPLAY
                if action.get('process_name'):
                    target_win = self.find_target_window(action['process_name'], action.get('window_title'))
                    
                    if target_win:
                        # Found the window! Calculate new coordinates
                        # Handle struct diff between pygetwindow obj and dict
                        if isinstance(target_win, dict):
                            win_x, win_y = target_win['left'], target_win['top']
                            hwnd = target_win['hwnd']
                        else:
                            win_x, win_y = target_win.left, target_win.top
                            hwnd = target_win._hWnd

                        # Bring to front (Crucial)
                        try:
                            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, 9) # Restore
                            win32gui.SetForegroundWindow(hwnd)
                        except: pass
                        
                        # Apply relative offset
                        target_x = win_x + action['relative_x']
                        target_y = win_y + action['relative_y']
                        print(f"✅ Tracking {action['process_name']} -> Moving to ({target_x}, {target_y})")
                    else:
                        print(f"⚠️ App {action['process_name']} not found. Clicking absolute coords.")

                # Move & Click
                pyautogui.moveTo(target_x, target_y, duration=self.move_duration)
                if "right" in action['button']: pyautogui.click(button='right')
                else: pyautogui.click()
            
            elif action['type'] == 'press':
                key = action['key']
                if "Key." in key: pyautogui.press(key.replace("Key.", ""))
                else: pyautogui.write(key)