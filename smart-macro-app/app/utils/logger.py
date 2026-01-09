import logging
import os

# Create the logs folder if it doesn't exist
os.makedirs("user_data/logs", exist_ok=True)

# Setup basic logging
logging.basicConfig(filename="user_data/logs/app.log", level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(message):
    """
    Logs a message to the file and prints it to the console.
    """
    logging.info(message)
    print(f"[LOG] {message}")