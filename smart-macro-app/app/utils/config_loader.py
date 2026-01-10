import json
import os

CONFIG_PATH = "user_data/configs/macros.json"

def load_macros():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_macro(name, instruction):
    macros = load_macros()
    macros[name] = instruction
    
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(macros, f, indent=4)