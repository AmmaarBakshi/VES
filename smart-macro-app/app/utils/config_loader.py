import json
import os

CONFIG_PATH = "user_data/configs/macros.json"
AI_CONFIG_PATH = "user_data/configs/ai_config.json"

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

def load_ai_config():
    default_config = {
        "active_model": "llama3.2",
        "ollama_base_url": "http://localhost:11434"
    }
    if not os.path.exists(AI_CONFIG_PATH):
        return default_config
    try:
        with open(AI_CONFIG_PATH, 'r') as f:
            config = json.load(f)
            # Merge defaults for any missing keys
            return {**default_config, **config}
    except:
        return default_config

def save_ai_config(config):
    os.makedirs(os.path.dirname(AI_CONFIG_PATH), exist_ok=True)
    with open(AI_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)