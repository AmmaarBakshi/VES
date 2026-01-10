import ollama

# HARDCODED CLOUD MODEL as per your request
MODEL_NAME = "deepseek-v3.1:671b-cloud"

def query_ollama(prompt):
    """
    Sends text to the Google Cloud model via Ollama.
    """
    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'system', 'content': 'You are a helpful automation assistant. Output only the requested result.'},
            {'role': 'user', 'content': prompt},
        ])
        return response['message']['content']
        
    except ollama.ResponseError as e:
        if e.status_code == 401:
            return "[ERROR: 401 Unauthorized. You MUST run 'ollama run gemini-3-flash-preview:cloud' in terminal to login first.]"
        return f"[Error: {e.error}]"
    except Exception as e:
        return f"[Error: {str(e)}]"