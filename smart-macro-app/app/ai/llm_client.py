import requests
import json

# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/chat"

# USE THIS for the Cloud Version (Requires the terminal login step above)
MODEL_NAME = "kimi-k2:1t-cloud"

# USE THIS if you want to switch back to Local/Offline (No login needed)
# MODEL_NAME = "qwen2.5:3b"

def query_ollama(prompt):
    """
    Sends text to Ollama using standard HTTP requests.
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
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
        response = requests.post(OLLAMA_API_URL, headers=headers, json=payload, timeout=120)
        
        # Specific check for Auth Error
        if response.status_code == 401:
             print("❌ BLOCKED: Google Cloud Auth missing.")
             return "[ERROR: 401 Unauthorized. You MUST open a terminal and run 'ollama run gemini-3-flash-preview:cloud' to sign in.]"
        
        # Check for other errors (like 404 Model Not Found)
        if response.status_code == 404:
            return f"[Error: Model '{MODEL_NAME}' not found. Run 'ollama pull {MODEL_NAME}' in terminal.]"
            
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