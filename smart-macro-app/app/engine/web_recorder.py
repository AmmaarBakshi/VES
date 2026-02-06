"""
Web Scraper Recorder Engine
============================
Playwright Codegen-based browser automation recorder and player.

Features:
- Record browser interactions using Playwright codegen
- Save recordings as executable Python scripts
- Replay saved recordings
- Safe process management and cleanup
"""

import subprocess
import os
import time
import threading
import psutil
from datetime import datetime
from typing import Optional, Callable


# Configuration
RECORDINGS_DIR = "user_data/recordings/web_scraper"
CODEGEN_TIMEOUT = 300  # 5 minutes max recording time


class WebRecorder:
    """
    Manages Playwright codegen recording sessions.
    
    Handles:
    - Starting/stopping codegen process
    - Capturing generated script output
    - Saving recordings with timestamps
    """
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.recording = False
        self.captured_script = ""
        self.last_recording_path = None
        self.temp_output_file = None  # Temp file for codegen output
        
        # Ensure recordings directory exists
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
    
    def start_recording(self) -> bool:
        """
        Start Playwright codegen recording.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.recording:
            print("⚠️ Recording already in progress")
            return False
        
        try:
            # Generate temporary output file path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_output_file = os.path.join(RECORDINGS_DIR, f"temp_recording_{timestamp}.py")
            
            # Launch Playwright codegen with file output
            # --target python: Generate Python code
            # --output: Save to file (required for codegen to work properly)
            self.process = subprocess.Popen(
                ["playwright", "codegen", "--target", "python", "--output", self.temp_output_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            self.recording = True
            self.captured_script = ""
            print(f"🔴 Web recording started (Browser should open automatically)")
            print(f"📝 Recording will be saved to: {self.temp_output_file}")
            return True
            
        except FileNotFoundError:
            print("❌ Playwright not found. Install with: pip install playwright && playwright install")
            return False
        except Exception as e:
            print(f"❌ Failed to start recording: {e}")
            return False
    
    def stop_recording(self) -> bool:
        """
        Stop recording and capture generated script.
        
        Returns:
            bool: True if stopped successfully and script captured
        """
        if not self.recording or not self.process:
            print("⚠️ No active recording to stop")
            return False
        
        try:
            # Terminate the codegen process gracefully
            if os.name == 'nt':
                # Windows: Use taskkill for clean shutdown
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                        timeout=5
                    )
                except subprocess.TimeoutExpired:
                    pass
            else:
                # Unix: Send SIGTERM
                self.process.terminate()
            
            # Wait for process to finish
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if still running
                self.process.kill()
                self.process.wait()
            
            # Clean up any remaining child processes
            self._cleanup_process_tree(self.process.pid)
            
            # Read the generated script from file
            import time
            time.sleep(0.5)  # Give file system time to flush
            
            if os.path.exists(self.temp_output_file):
                with open(self.temp_output_file, 'r', encoding='utf-8') as f:
                    self.captured_script = f.read()
            else:
                self.captured_script = ""
            
            self.recording = False
            self.process = None
            
            if self.captured_script.strip():
                print(f"✅ Recording stopped. Captured {len(self.captured_script)} characters")
                return True
            else:
                print("⚠️ Recording stopped but no script was captured")
                print(f"⚠️ Expected file: {self.temp_output_file}")
                return False
                
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
            self.recording = False
            self.process = None
            return False
    
    def save_recording(self, custom_name: Optional[str] = None) -> Optional[str]:
        """
        Save captured script to file.
        
        Args:
            custom_name: Optional custom filename (without extension)
        
        Returns:
            str: Path to saved file, or None if failed
        """
        if not self.captured_script.strip():
            print("⚠️ No script to save")
            return None
        
        try:
            # Generate final filename
            if custom_name:
                filename = f"{custom_name}.py"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"web_recording_{timestamp}.py"
            
            filepath = os.path.join(RECORDINGS_DIR, filename)
            
            # If temp file exists and is the same, just rename it
            if hasattr(self, 'temp_output_file') and os.path.exists(self.temp_output_file):
                if filepath != self.temp_output_file:
                    # Rename temp file to final name
                    import shutil
                    shutil.move(self.temp_output_file, filepath)
                else:
                    # Already has correct name
                    filepath = self.temp_output_file
            else:
                # Write script to file (fallback)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.captured_script)
            
            self.last_recording_path = filepath
            print(f"💾 Recording saved: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ Failed to save recording: {e}")
            return None
    
    def get_last_recording_path(self) -> Optional[str]:
        """Get path to the most recently saved recording."""
        return self.last_recording_path
    
    def _cleanup_process_tree(self, pid: int):
        """
        Kill all child processes of a given PID.
        
        Args:
            pid: Process ID to clean up
        """
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")


class WebPlayer:
    """
    Executes saved Playwright recordings.
    
    Features:
    - Thread-safe playback
    - Process management
    - Progress callbacks
    """
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.playing = False
        self.playback_thread: Optional[threading.Thread] = None
    
    def play_recording(
        self, 
        script_path: str, 
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        Play a saved recording.
        
        Args:
            script_path: Path to the .py script to execute
            on_complete: Callback when playback finishes successfully
            on_error: Callback with error message if playback fails
        
        Returns:
            bool: True if playback started successfully
        """
        if self.playing:
            print("⚠️ Playback already in progress")
            return False
        
        if not os.path.exists(script_path):
            error_msg = f"Script not found: {script_path}"
            print(f"❌ {error_msg}")
            if on_error:
                on_error(error_msg)
            return False
        
        # Start playback in separate thread to avoid UI blocking
        self.playback_thread = threading.Thread(
            target=self._execute_playback,
            args=(script_path, on_complete, on_error),
            daemon=True
        )
        self.playback_thread.start()
        return True
    
    def _execute_playback(
        self, 
        script_path: str, 
        on_complete: Optional[Callable],
        on_error: Optional[Callable[[str], None]]
    ):
        """
        Internal method to execute playback in thread.
        
        Args:
            script_path: Path to script
            on_complete: Success callback
            on_error: Error callback
        """
        try:
            self.playing = True
            print(f"▶️ Playing: {os.path.basename(script_path)}")
            
            # Execute the Playwright script
            self.process = subprocess.Popen(
                ["python", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Wait for completion
            stdout, stderr = self.process.communicate()
            
            self.playing = False
            self.process = None
            
            if stderr and "error" in stderr.lower():
                error_msg = f"Playback error: {stderr[:200]}"
                print(f"❌ {error_msg}")
                if on_error:
                    on_error(error_msg)
            else:
                print("✅ Playback completed successfully")
                if on_complete:
                    on_complete()
                    
        except Exception as e:
            error_msg = f"Playback exception: {str(e)}"
            print(f"❌ {error_msg}")
            self.playing = False
            self.process = None
            if on_error:
                on_error(error_msg)
    
    def stop_playback(self) -> bool:
        """
        Stop currently playing recording.
        
        Returns:
            bool: True if stopped successfully
        """
        if not self.playing or not self.process:
            print("⚠️ No active playback to stop")
            return False
        
        try:
            # Terminate playback process
            if os.name == 'nt':
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                    timeout=5
                )
            else:
                self.process.terminate()
                self.process.wait(timeout=5)
            
            # Clean up process tree
            self._cleanup_process_tree(self.process.pid)
            
            self.playing = False
            self.process = None
            print("⏹ Playback stopped")
            return True
            
        except Exception as e:
            print(f"❌ Error stopping playback: {e}")
            self.playing = False
            self.process = None
            return False
    
    def _cleanup_process_tree(self, pid: int):
        """Kill all child processes."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
                    
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")


def get_saved_recordings() -> list[str]:
    """
    Get list of all saved recordings.
    
    Returns:
        list: List of recording filenames (without .py extension)
    """
    if not os.path.exists(RECORDINGS_DIR):
        return []
    
    try:
        files = [
            f.replace(".py", "") 
            for f in os.listdir(RECORDINGS_DIR) 
            if f.endswith(".py")
        ]
        # Sort by modification time (newest first)
        files.sort(
            key=lambda x: os.path.getmtime(os.path.join(RECORDINGS_DIR, f"{x}.py")),
            reverse=True
        )
        return files
    except Exception as e:
        print(f"⚠️ Error listing recordings: {e}")
        return []


def delete_recording(filename: str) -> bool:
    """
    Delete a saved recording.
    
    Args:
        filename: Name of recording (without .py extension)
    
    Returns:
        bool: True if deleted successfully
    """
    try:
        filepath = os.path.join(RECORDINGS_DIR, f"{filename}.py")
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"🗑️ Deleted: {filename}")
            return True
        return False
    except Exception as e:
        print(f"❌ Failed to delete recording: {e}")
        return False
