import os
from pypdf import PdfReader
from app.ai.llm_client import query_ollama
from app.ai.prompts import get_prompt

def process_pdf_file(file_path, instruction):
    """
    Reads a PDF, extracts text, summarizes/edits it with AI, and saves to .txt.
    (PDF editing is hard, so we save as text for now).
    """
    try:
        reader = PdfReader(file_path)
        full_text = ""
        
        # specific check for encrypted files
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except:
                return "Error: PDF is password protected."

        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        if not full_text.strip():
            return "Error: No text found in PDF (It might be a scanned image)."

        # Limit text to 4000 chars to prevent crashing the local AI
        chunk = full_text[:4000]
        
        prompt = get_prompt(instruction, chunk)
        ai_response = query_ollama(prompt)

        # Save to a text file
        base_name = os.path.basename(file_path)
        new_filename = f"PROCESSED_{base_name}.txt"
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, new_filename)
        
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(ai_response)
            
        return new_path

    except Exception as e:
        print(f"PDF Error Detail: {e}") # Print to terminal for debugging
        return f"Error: {str(e)}"