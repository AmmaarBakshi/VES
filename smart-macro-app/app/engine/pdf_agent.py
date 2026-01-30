import threading
import os
from langchain_community.llms import Ollama

# IMPORTS: We import the function from the neighboring file 'pdf_maker.py'
try:
    from app.engine.pdf_maker import create_filled_pdf
except ImportError:
    # If Python gets confused about paths, we try a relative import
    from .pdf_maker import create_filled_pdf

class PDFAgent:
    def __init__(self):
        # Ensure Ollama is running in your terminal!
        self.llm = Ollama(model="llama3")

    def generate_smart_pdf(self, topic, update_callback):
        """
        topic: The user's input string
        update_callback: A function to update the UI
        """
        def run():
            try:
                # --- Step 1: AI Writing Content ---
                update_callback("step_1", "running")
                
                prompt = (
                    f"Write a professional, well-structured document about: '{topic}'. "
                    "Do not use markdown symbols like ** or ##. "
                    "Just write clean, readable text with paragraphs."
                )
                
                # Get text from AI
                generated_content = self.llm.invoke(prompt)
                update_callback("step_1", "done")

                # --- Step 2: Generating PDF File ---
                update_callback("step_2", "running")
                
                # Define filename
                filename = f"{topic.replace(' ', '_')}_generated.pdf"
                # Save it in the current working directory
                output_path = os.path.join(os.getcwd(), filename)
                
                # Call the function you already have in pdf_maker.py
                result = create_filled_pdf(generated_content, output_path)
                
                # Check if your pdf_maker returned an error string
                if result and "Error" in str(result):
                    raise Exception(str(result))
                    
                update_callback("step_2", "done")
                update_callback("final", f"Saved as {filename}")

            except Exception as e:
                print(f"Error: {e}")
                update_callback("error", str(e))

        # Run in background thread so UI doesn't freeze
        threading.Thread(target=run, daemon=True).start()