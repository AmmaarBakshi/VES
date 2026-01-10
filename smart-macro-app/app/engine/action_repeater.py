import time
import threading
import pyautogui
from pynput import mouse, keyboard
import json
import math

# FAILSAFE: Drag mouse to top-left corner to kill the script instantly
pyautogui.FAILSAFE = True 

class ActionRepeater:
    def __init__(self):
        self.actions = []
        self.recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.key_listener = None
        
        # OPTIMIZATION SETTINGS
        self.move_duration = 0.2  # Seconds to glide mouse (0 = instant)
        self.max_delay = 1.0      # Max wait time between actions (removes long pauses)
        self.speed_multiplier = 1.0 # 1.0 = normal, 2.0 = double speed

    def start_recording(self):
        self.actions = []
        self.recording = True
        self.start_time = time.time()
        
        # We record CLICKS and KEYS. 
        # We generally DO NOT record mouse movement paths because it creates huge laggy files.
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.key_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.key_listener.start()
        print("🔴 Recording started...")

    def stop_recording(self):
        self.recording = False
        if self.mouse_listener: self.mouse_listener.stop()
        if self.key_listener: self.key_listener.stop()
        print(f"⏹ Recording stopped. Captured {len(self.actions)} actions.")
        return self.actions

    def save_macro(self, filepath):
        with open(filepath, 'w') as f:
            json.dump(self.actions, f)

    def load_and_play(self, filepath, speed=1.0):
        try:
            self.speed_multiplier = speed
            with open(filepath, 'r') as f:
                actions = json.load(f)
            self.play_actions(actions)
            return "Macro finished successfully."
        except pyautogui.FailSafeException:
            return "Stopped by User (Failsafe triggered)."
        except Exception as e:
            return f"Error playing macro: {e}"

    def on_click(self, x, y, button, pressed):
        if pressed and self.recording:
            dt = time.time() - self.start_time
            # Record coordinates
            self.actions.append({
                'type': 'click', 
                'x': x, 
                'y': y, 
                'button': str(button), 
                'time': dt
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
        
        start_replay = time.time()
        # We track 'virtual time' to allow speed adjustments
        virtual_start_time = actions[0]['time'] 
        
        last_action_time = virtual_start_time

        for i, action in enumerate(actions):
            # 1. Calculate how long to wait
            original_delay = action['time'] - last_action_time
            
            # OPTIMIZATION: Cap the delay (e.g., never wait more than 1 second)
            if original_delay > self.max_delay:
                original_delay = self.max_delay
            
            # OPTIMIZATION: Apply Speed Multiplier
            adjusted_delay = original_delay / self.speed_multiplier
            
            # Sleep smoothly
            if adjusted_delay > 0:
                time.sleep(adjusted_delay)

            # 2. Execute Action
            if action['type'] == 'click':
                # SMOOTHNESS: Glide to target instead of teleporting
                # Only glide if distance is significant
                curr_x, curr_y = pyautogui.position()
                dist = math.hypot(curr_x - action['x'], curr_y - action['y'])
                
                if dist > 50: # Only animate if moving far
                    pyautogui.moveTo(action['x'], action['y'], duration=self.move_duration / self.speed_multiplier)
                else:
                    pyautogui.moveTo(action['x'], action['y']) # Instant for short distances
                
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