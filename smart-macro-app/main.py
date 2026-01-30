import sys
import os
from app.gui.app_window import AppWindow
from app.utils.ollama_manager import ensure_ollama_running

# Fix for module import issues
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Create necessary user folders if they don't exist
    os.makedirs("user_data/configs", exist_ok=True)
    os.makedirs("user_data/logs", exist_ok=True)
    
    # Auto-start Ollama service if not running
    print("=" * 50)
    print("Smart Macro Station - Starting Up")
    print("=" * 50)
    ensure_ollama_running()
    print("=" * 50)
    
    app = AppWindow()
    app.mainloop()
