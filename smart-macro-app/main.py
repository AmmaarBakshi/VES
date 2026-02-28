import sys
import os

# Fix for module import issues
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from app.gui.app_window import AppWindow
from app.gui.theme import ThemeManager
from app.utils.ollama_manager import ensure_ollama_running

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

    # Launch PyQt6 application
    qt_app = QApplication(sys.argv)
    ThemeManager.set_theme("light", qt_app)

    window = AppWindow()
    window.show()
    sys.exit(qt_app.exec())
