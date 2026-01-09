import sys
import os
from app.gui.app_window import AppWindow

# Fix for module import issues
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Create necessary user folders if they don't exist
    os.makedirs("user_data/configs", exist_ok=True)
    os.makedirs("user_data/logs", exist_ok=True)
    
    app = AppWindow()
    app.mainloop()