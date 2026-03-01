import requests
import json
from app.utils.config_loader import load_ai_config

# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/chat"

def query_ollama(prompt):
    """
    Sends text to Ollama using standard HTTP requests.
    """
    ai_config = load_ai_config()
    model_name = ai_config.get("active_model", "llama3.2")
    
    # Optional override if base URL is configured
    base_url = ai_config.get("ollama_base_url", "http://localhost:11434").rstrip('/')
    api_url = f"{base_url}/api/chat"

    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system", 
                "content": "You are a helpful automation assistant. Output only the requested result.(fastest time possible [note the content should be accurate but the output should come in fastest timre possible ])"
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "stream": False 
    }

    try:
        # Send the POST request
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        
        # Specific check for Auth Error
        if response.status_code == 401:
             print("❌ BLOCKED: Google Cloud Auth missing.")
             return "[ERROR: 401 Unauthorized. You MUST open a terminal and run 'ollama run gemini-3-flash-preview:cloud' to sign in.]"
        
        # Check for other errors (like 404 Model Not Found)
        if response.status_code == 404:
            return f"[Error: Model '{model_name}' not found. Run 'ollama pull {model_name}' in terminal.]"
            
        response.raise_for_status() 
        
        # Parse JSON
        data = response.json()
        return data['message']['content']

    except requests.exceptions.ConnectionError:
        return "[Error: Could not connect to Ollama. Is it running? (Type 'ollama serve')]"
    except requests.exceptions.Timeout:
        return "[Error: Cloud request timed out. Internet might be slow.]"
    except Exception as e:
        return f"[Error: {str(e)}]"