import time
import threading
import pyautogui
import pygetwindow as gw
from pynput import mouse, keyboard
import json
import math
import os
import uuid
#changes
import ctypes

# FORCE high-DPI awareness on Windows to prevent coordinate shifting
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
#changes

# FAILSAFE: Drag mouse to top-left corner to kill the script instantly
pyautogui.FAILSAFE = True 

class ActionRepeater:
    def __init__(self):
        self.actions = []
        self.recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.key_listener = None
        
        # PERSISTENCE
        self.base_folder = "user_data/macros"
        self.current_session_id = None
        self.current_image_folder = None
        
        # OPTIMIZATION SETTINGS
        self.move_duration = 0.2  # Seconds to glide mouse (0 = instant)
        self.max_delay = 1.0      # Max wait time between actions (removes long pauses)
        self.speed_multiplier = 1.0 # 1.0 = normal, 2.0 = double speed

    def start_recording(self):
        self.actions = []
        self.recording = True
        self.start_time = time.time()
        
        # Create session folder for images
        self.current_session_id = str(uuid.uuid4())[:8]
        self.current_image_folder = os.path.join(self.base_folder, self.current_session_id)
        if not os.path.exists(self.current_image_folder):
            os.makedirs(self.current_image_folder)
        
        # We record CLICKS and KEYS. 
        # We generally DO NOT record mouse movement paths because it creates huge laggy files.
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.key_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.key_listener.start()
        print(f"🔴 Recording started in session {self.current_session_id}...")

    def stop_recording(self):
        self.recording = False
        if self.mouse_listener: self.mouse_listener.stop()
        if self.key_listener: self.key_listener.stop()
        print(f"⏹ Recording stopped. Captured {len(self.actions)} actions.")
        return self.actions

    def save_macro(self, filepath):
        # Ensure the directory for the macro file exists
        macro_dir = os.path.dirname(filepath)
        if macro_dir and not os.path.exists(macro_dir):
            os.makedirs(macro_dir)
            
        data = {
            "session_id": self.current_session_id,
            "actions": self.actions
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_and_play(self, filepath, speed=1.0):
        try:
            self.speed_multiplier = speed
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Handle both old format (list) and new format (dict)
            if isinstance(data, list):
                actions = data
                # No session ID, likely old macro
            else:
                actions = data.get("actions", [])
                # We might need session_id if we have relative paths, but we stored absolute or handle retrieval
            
            self.play_actions(actions)
            return "Macro finished successfully."
        except pyautogui.FailSafeException:
            return "Stopped by User (Failsafe triggered)."
        except Exception as e:
            return f"Error playing macro: {e}"

    def on_click(self, x, y, button, pressed):
        if pressed and self.recording:
            dt = time.time() - self.start_time
            
            # IMAGE ANCHORING: Capture distinct feature around the click
            # We capture a 60x60 square around existing click
            img_filename = f"click_{int(dt*1000)}.png"
            img_path = os.path.join(self.current_image_folder, img_filename)
            
            # WINDOW CAPTURE
            window_title = None
            relative_x = x
            relative_y = y
            
            try:
                # STRATEGY 1: Check what window is currently active (Reliable for clicks)
                target_window = None
                active_window = gw.getActiveWindow()
                
                # Verify the click is actually INSIDE the active window
                if active_window:
                     # Check bounds: left <= x <= right AND top <= y <= bottom
                    if (active_window.left <= x <= active_window.right and 
                        active_window.top <= y <= active_window.bottom):
                        target_window = active_window
                
                # STRATEGY 2: If active window doesn't match, query windows at location
                if not target_window:
                    windows = gw.getWindowsAt(x, y)
                    if windows:
                        target_window = windows[0]

                if target_window:
                    window_title = target_window.title
                    # Handle minimized/maximized offsets if necessary, 
                    # but usually left/top is enough context
                    relative_x = x - target_window.left
                    relative_y = y - target_window.top
                    print(f"Captured Window: '{window_title}' at ({target_window.left}, {target_window.top}) | Click: ({x}, {y}) | Rel: ({relative_x}, {relative_y})")
            except Exception as e:
                print(f"Warning: Window capture failed: {e}")
            
            try:
                # Region: (left, top, width, height)
                capture_region = (x - 30, y - 30, 60, 60)
                screenshot = pyautogui.screenshot(region=capture_region)
                screenshot.save(img_path)
                has_image = True
            except Exception as e:
                print(f"Warning: Failed to capture screenshot anchor: {e}")
                has_image = False
                img_path = None

            # Record action
            self.actions.append({
                'type': 'click', 
                'x': x, 
                'y': y, 
                'relative_x': relative_x,
                'relative_y': relative_y,
                'window_title': window_title,
                'button': str(button), 
                'time': dt,
                'image_anchor': img_path if has_image else None
            })

    def on_press(self, key):
        if self.recording:
            dt = time.time() - self.start_time
            try:
                k = key.char
            except AttributeError:
                k = str(key) # Special keys
            
            # Stop key (F9) shouldn't be recorded
            if k == 'Key.f9': 
                return

            self.actions.append({'type': 'press', 'key': k, 'time': dt})

    def play_actions(self, actions):
        if not actions: return
        
        # We track 'virtual time' to allow speed adjustments
        virtual_start_time = actions[0]['time'] 
        last_action_time = virtual_start_time

        for i, action in enumerate(actions):
            # 1. Calculate how long to wait
            original_delay = action['time'] - last_action_time
            
            # OPTIMIZATION: Cap the delay to catch up if user recorded long pauses
            if original_delay > self.max_delay:
                original_delay = self.max_delay
            
            # OPTIMIZATION: Apply Speed Multiplier
            adjusted_delay = original_delay / self.speed_multiplier
            
            if adjusted_delay > 0:
                time.sleep(adjusted_delay)

            # 2. Execute Action
            if action['type'] == 'click':
                target_x, target_y = action['x'], action['y']

                # ROBUST WINDOW HANDLING: Find Window & Apply Relative Coords
                win_title = action.get('window_title')
                if win_title:
                    try:
                        # 1. Find Candidates
                        candidates = gw.getWindowsWithTitle(win_title)
                       
                        # 2. Filter Candidates (Must be visible, non-empty)
                        valid_candidates = [w for w in candidates if w.title and (w.width > 0 and w.height > 0)]
                        
                        target_win = None
                        
                        # 3. Selection Strategy
                        # A. Exact Match
                        for w in valid_candidates:
                            if w.title == win_title:
                                target_win = w
                                break
                        
                        # B. Fuzzy Match (if no exact match)
                        if not target_win:
                             # Try partial matches (case insensitive)
                             clean_target = win_title.lower().strip()
                             for w in gw.getAllWindows():
                                 if not w.title: continue
                                 curr_title = w.title.lower().strip()
                                 if clean_target in curr_title or curr_title in clean_target:
                                     target_win = w
                                     print(f"Fuzzy match: '{win_title}' -> '{w.title}'")
                                     break

                        # 4. Activate & Calculate
                        if target_win:
                            if target_win.isMinimized:
                                target_win.restore()
                                time.sleep(0.2)
                            
                            try:
                                target_win.activate()
                                time.sleep(0.2)
                            except Exception:
                                pass # Focus might fail if user is holding mouse, but we proceed
                            
                            if 'relative_x' in action and 'relative_y' in action:
                                target_x = target_win.left + action['relative_x']
                                target_y = target_win.top + action['relative_y']
                                print(f"Targeting '{target_win.title}' New Pos: ({target_win.left}, {target_win.top}) | Target: ({target_x}, {target_y})")
                        else:
                            print(f"⚠️ Could not find window: '{win_title}'. Using original coordinates.")

                    except Exception as e:
                        print(f"Window logic error: {e}")
                
                # RECOVERY & PRIMARY STRATEGY: Image Search
                # We prioritize image match if available because it guarantees hitting the button 
                # even if window logic was slightly off or UI shifted.
                img_found = False
                if action.get('image_anchor') and os.path.exists(action['image_anchor']):
                    try:
                        # Search for the image on screen
                        # confidence=0.8 allows for slight rendering differences (antialiasing, etc)
                        try:
                            found_pos = pyautogui.locateCenterOnScreen(action['image_anchor'], confidence=0.8)
                        except TypeError:
                            # Fallback if opencv not found
                            found_pos = pyautogui.locateCenterOnScreen(action['image_anchor'])
                            
                        if found_pos:
                            print(f"✅ Image confirmed at {found_pos}. Overriding coords.")
                            target_x, target_y = found_pos
                            img_found = True
                        else:
                            print(f"⚠️ Image anchor not found visually.")
                    except Exception as e:
                        print(f"Image search failed: {e}")

                # SMOOTHNESS: Glide to target
                curr_x, curr_y = pyautogui.position()
                dist = math.hypot(curr_x - target_x, curr_y - target_y)
                
                if dist > 50:
                    pyautogui.moveTo(target_x, target_y, duration=self.move_duration / self.speed_multiplier)
                else:
                    pyautogui.moveTo(target_x, target_y)
                
                # Perform click
                if "Button.right" in action['button']:
                    pyautogui.click(button='right')
                else:
                    pyautogui.click()
            
            elif action['type'] == 'press':
                key_val = action['key']
                if "Key." in key_val:
                    clean_key = key_val.replace("Key.", "")
                    pyautogui.press(clean_key)
                else:
                    pyautogui.write(key_val)

            last_action_time = action['time']