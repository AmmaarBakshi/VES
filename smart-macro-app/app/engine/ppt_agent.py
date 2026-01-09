import os
from pptx import Presentation
from app.ai.llm_client import query_ollama
from app.ai.prompts import get_prompt

def process_ppt_file(file_path, instruction):
    try:
        prs = Presentation(file_path)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    prompt = get_prompt(instruction, shape.text)
                    new_text = query_ollama(prompt)
                    shape.text = new_text

        base_name = os.path.basename(file_path)
        new_path = os.path.join(os.path.dirname(file_path), f"PROCESSED_{base_name}")
        prs.save(new_path)
        return new_path
    except Exception as e:
        return f"Error: {e}"