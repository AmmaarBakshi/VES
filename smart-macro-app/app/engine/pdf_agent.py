import threading
import os
from langchain_ollama import OllamaLLM
from app.engine.cot_engine import stream_cot_plan, make_pdf_plan_prompt

# IMPORTS: We import the function from the neighboring file 'pdf_maker.py'
try:
    from app.engine.pdf_maker import create_filled_pdf
except ImportError:
    from .pdf_maker import create_filled_pdf

class PDFAgent:
    def __init__(self):
        # Ensure Ollama is running in your terminal!
        self.llm = OllamaLLM(model="llama3")

    def generate_smart_pdf(self, topic, update_callback, thought_callback=None):
        """
        topic: The user's input string
        update_callback: A function to update the UI
        thought_callback: Optional callable(str) — receives streaming CoT thoughts
        """
        def run():
            try:
                # ── Agentic CoT: Stream planning thoughts before any work ──
                if thought_callback:
                    thought_callback(f"◆ Topic: {topic}\n\n")
                    plan_prompt = make_pdf_plan_prompt(topic)
                    stream_cot_plan(self.llm, plan_prompt, thought_callback)
                    thought_callback("\n\n─── Writing Document ───\n\n")

                # --- Step 1: AI Writing Content ---
                update_callback("step_1", "running")
                
                prompt = (
                    f"Write a professional, well-structured document about: '{topic}'. "
                    "Do not use markdown symbols like ** or ##. "
                    "Just write clean, readable text with paragraphs."
                )
                
                generated_content = self.llm.invoke(prompt)
                update_callback("step_1", "done")

                # --- Step 2: Generating PDF File ---
                update_callback("step_2", "running")
                
                filename = f"{topic.replace(' ', '_')}_generated.pdf"
                output_path = os.path.join(os.getcwd(), filename)
                
                result = create_filled_pdf(generated_content, output_path)
                
                if result and "Error" in str(result):
                    raise Exception(str(result))
                    
                update_callback("step_2", "done")
                update_callback("final", output_path)   # full path for download button

            except Exception as e:
                print(f"Error: {e}")
                update_callback("error", str(e))

        threading.Thread(target=run, daemon=True).start()