"""
Ollama Service Manager

Automatically checks if Ollama is running and starts it if needed.
Provides utilities for managing the Ollama service lifecycle.
"""

import subprocess
import time
import requests
import threading
import os


class OllamaManager:
    """Manages Ollama service startup and health checks"""
    
    def __init__(self):
        self.ollama_process = None
        self.ollama_url = "http://localhost:11434"
        self.is_running = False
    
    def check_ollama_running(self):
        """
        Check if Ollama service is already running.
        
        Returns:
            bool: True if Ollama is running, False otherwise
        """
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                print("✅ Ollama is already running")
                self.is_running = True
                return True
        except requests.exceptions.RequestException:
            pass
        
        self.is_running = False
        return False
    
    def start_ollama(self):
        """
        Start Ollama service in the background.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            print("🚀 Starting Ollama service...")
            
            # Start Ollama serve in background
            # Using CREATE_NO_WINDOW flag to hide the console window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Wait for Ollama to be ready (max 10 seconds)
            for i in range(20):
                time.sleep(0.5)
                if self.check_ollama_running():
                    print("✅ Ollama started successfully!")
                    return True
            
            print("⚠️ Ollama started but not responding yet. It may take a moment...")
            return True
            
        except FileNotFoundError:
            print("❌ Ollama not found. Please install Ollama from https://ollama.ai")
            return False
        except Exception as e:
            print(f"❌ Error starting Ollama: {e}")
            return False
    
    def ensure_ollama_running(self):
        """
        Ensure Ollama is running, start it if not.
        This is the main method to call on app startup.
        
        Returns:
            bool: True if Ollama is running (or was started), False otherwise
        """
        if self.check_ollama_running():
            return True
        
        print("Ollama is not running. Starting it now...")
        return self.start_ollama()
    
    def start_ollama_async(self, callback=None):
        """
        Start Ollama asynchronously in a background thread.
        
        Args:
            callback: Optional function to call when startup completes
                     Will receive True/False indicating success
        """
        def run():
            success = self.ensure_ollama_running()
            if callback:
                callback(success)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def stop_ollama(self):
        """Stop Ollama service if it was started by this manager"""
        if self.ollama_process:
            try:
                self.ollama_process.terminate()
                self.ollama_process.wait(timeout=5)
                print("🛑 Ollama service stopped")
            except Exception as e:
                print(f"Error stopping Ollama: {e}")


# Global instance
_ollama_manager = None


def get_ollama_manager():
    """Get the global OllamaManager instance"""
    global _ollama_manager
    if _ollama_manager is None:
        _ollama_manager = OllamaManager()
    return _ollama_manager


def ensure_ollama_running():
    """
    Convenience function to ensure Ollama is running.
    Call this at application startup.
    
    Returns:
        bool: True if Ollama is running, False otherwise
    """
    manager = get_ollama_manager()
    return manager.ensure_ollama_running()


def start_ollama_async(callback=None):
    """
    Convenience function to start Ollama asynchronously.
    
    Args:
        callback: Optional function to call when startup completes
    """
    manager = get_ollama_manager()
    manager.start_ollama_async(callback)
