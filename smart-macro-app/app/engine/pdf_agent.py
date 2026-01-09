import os
from pypdf import PdfReader
from app.ai.llm_client import query_ollama
from app.ai.prompts import get_prompt

def process_pdf_file(file_path, instruction):
    try:
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"

        prompt = get_prompt(instruction, full_text[:4000]) # Limit length
        summary = query_ollama(prompt)

        base_name = os.path.basename(file_path)
        new_path = os.path.join(os.path.dirname(file_path), f"PROCESSED_{base_name}.txt")
        
        with open(new_path, "w", encoding="utf-8") as f:
            f.write(summary)
        return new_path
    except Exception as e:
        return f"Error: {e}"