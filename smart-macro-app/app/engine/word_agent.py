import os
from docx import Document
from app.ai.llm_client import query_ollama

def process_word_document(file_path, instruction="Fix grammar and make professional"):
    """
    Reads a .docx file, processes each paragraph with AI, and saves a new copy.
    """
    try:
        doc = Document(file_path)
        
        # Loop through paragraphs (skipping empty ones to save time)
        total_paragraphs = len([p for p in doc.paragraphs if p.text.strip()])
        processed_count = 0

        print(f"Processing {total_paragraphs} paragraphs...")

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                # Send original text + user instruction to AI
                full_prompt = f"Instruction: {instruction}\n\nText: {paragraph.text}"
                
                # Get result from AI
                new_text = query_ollama(full_prompt)
                
                # Replace text in the document
                paragraph.text = new_text
                processed_count += 1
                print(f" - Processed paragraph {processed_count}/{total_paragraphs}")

        # Save the new file
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        new_path = os.path.join(dir_name, f"PROCESSED_{base_name}")
        
        doc.save(new_path)
        return new_path

    except Exception as e:
        print(f"Error processing file: {e}")
        return None