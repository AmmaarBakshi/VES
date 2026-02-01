import threading
import os
import json
import re
import time
from pptx import Presentation
from pptx.util import Pt
from pptx.enum.text import MSO_AUTO_SIZE
from langchain_ollama import OllamaLLM 

class PPTGenerator:
    def __init__(self):
        # Temperature 0.5 keeps it creative but less likely to break JSON format
        self.llm = OllamaLLM(model="llama3", temperature=0.5) 

    def generate_ppt(self, topic, update_callback):
        def run():
            try:
                # --- Step 1: Research ---
                update_callback("step_1", "running")
                print(f"\n[DEBUG] Sending prompt for: {topic}")
                
                # We ask for JSON, but we are prepared if it fails
                prompt = (
                    f"Create a 5-slide presentation about '{topic}'. "
                    "Output a JSON array of objects. "
                    "Format: [{\"title\": \"Slide Title\", \"content\": [\"Point 1\", \"Point 2\"]}]. "
                    "Make bullet points detailed and academic. "
                    "IMPORTANT: Do not use quotes \" inside the content strings unless escaped."
                )
                
                response = self.llm.invoke(prompt)
                print(f"[DEBUG] AI Response received ({len(response)} chars).")
                # print(response) # Uncomment to see full raw text in terminal
                
                update_callback("step_1", "done")

                # --- Step 2: Parsing (With Backup) ---
                update_callback("step_2", "running")
                
                # Try strict JSON first
                slides_data = self._extract_json(response)
                
                # If JSON fails, use the Backup Parser
                if not slides_data:
                    print("[DEBUG] JSON parse failed. Switching to Backup Text Parser.")
                    slides_data = self._parse_text_backup(response)
                
                if not slides_data:
                    raise Exception("Could not extract any slides from AI response.")
                    
                update_callback("step_2", "done")

                # --- Step 3: Build PPT ---
                update_callback("step_3", "running")
                prs = Presentation()
                
                for slide_info in slides_data:
                    layout = prs.slide_layouts[1] 
                    slide = prs.slides.add_slide(layout)
                    
                    # Title
                    if slide.shapes.title:
                        slide.shapes.title.text = slide_info.get('title', 'Untitled')
                    
                    # Content
                    if len(slide.placeholders) > 1:
                        body = slide.placeholders[1]
                        
                        # --- AUTO-FIT FIX ---
                        body.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
                        body.text_frame.word_wrap = True
                        
                        tf = body.text_frame
                        tf.clear() 
                        
                        content = slide_info.get('content', [])
                        if isinstance(content, str): content = [content]
                            
                        for point in content:
                            p = tf.add_paragraph()
                            p.text = str(point).replace("**", "").strip()
                            p.level = 0
                            p.space_after = Pt(10) # Nice spacing
                
                # Save
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', topic[:20])
                filename = f"{safe_name}_{int(time.time())}.pptx"
                path = os.path.join(os.getcwd(), filename)
                
                prs.save(path)
                
                update_callback("step_3", "done")
                update_callback("final", f"Saved as {filename}")
                
                try: os.startfile(path)
                except: pass

            except Exception as e:
                print(f"[ERROR] {e}")
                update_callback("error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _extract_json(self, text):
        """Try to find and parse JSON."""
        try:
            # Look for [ ... ]
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return None
        except:
            return None

    def _parse_text_backup(self, text):
        """
        FALLBACK: If JSON fails, manually find titles and bullets.
        This ensures you ALWAYS get a presentation.
        """
        slides = []
        current_slide = {}
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Detect Slide Title (looking for "Slide" or just bold text)
            if line.lower().startswith("slide") or "title:" in line.lower():
                if current_slide: slides.append(current_slide)
                # Clean title
                clean_title = re.sub(r'Slide \d+:?', '', line, flags=re.IGNORECASE).replace("Title:", "").strip()
                current_slide = {"title": clean_title, "content": []}
            
            # Detect Content (bullets -, *, or numbered 1.)
            elif line.startswith(('-', '*', '•')) or re.match(r'\d+\.', line):
                if "content" not in current_slide: current_slide["content"] = []
                # Clean bullet
                clean_point = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
                current_slide["content"].append(clean_point)
        
        if current_slide: slides.append(current_slide)
        
        # If fallback found nothing, create one generic slide so app doesn't crash
        if not slides:
            return [{"title": "Generated Presentation", "content": [text[:500] + "..."]}]
            
        return slides

# --- Keep Enricher Class to prevent Import Errors ---
class PPTEnricher:
    def __init__(self): pass
    def get_improvement_suggestions(self, path): return []
    def enhance_presentation(self, path, opts, style, cb): pass