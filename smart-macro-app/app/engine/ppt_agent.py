import threading
import os
import json
import re
import time
from pptx import Presentation
from langchain_community.llms import Ollama

class PPTGenerator:
    def __init__(self):
        # Make sure this matches the model you have (llama3 or mistral)
        self.llm = Ollama(model="llama3") 

    def generate_ppt(self, topic, update_callback):
        def run():
            try:
                # --- Step 1: Research / Outline ---
                update_callback("step_1", "running")
                
                # STRICT PROMPT: We force the AI to return raw JSON data only.
                prompt = (
                    f"You are a presentation generator. Create a 5-slide presentation about '{topic}'. "
                    "Return ONLY a valid JSON array of objects. Do not include any conversational text. "
                    "The JSON must follow this format:\n"
                    "[\n"
                    "  {\"title\": \"Slide 1 Title\", \"content\": [\"Bullet 1\", \"Bullet 2\"]},\n"
                    "  {\"title\": \"Slide 2 Title\", \"content\": [\"Bullet 1\", \"Bullet 2\"]}\n"
                    "]"
                )
                
                response = self.llm.invoke(prompt)
                print(f"DEBUG AI RESPONSE: {response[:100]}...") # Print first 100 chars to debug
                
                update_callback("step_1", "done")

                # --- Step 2: Parsing Data ---
                update_callback("step_2", "running")
                slides_data = self._extract_json(response)
                
                if not slides_data:
                    raise Exception("AI response was not valid JSON. See terminal for details.")
                    
                update_callback("step_2", "done")

                # --- Step 3: Creating PPT File ---
                update_callback("step_3", "running")
                prs = Presentation()
                
                for slide_info in slides_data:
                    # Layout 1 is usually Title + Content
                    layout = prs.slide_layouts[1] 
                    slide = prs.slides.add_slide(layout)
                    
                    # Set Title
                    if slide.shapes.title:
                        slide.shapes.title.text = slide_info.get('title', 'Untitled')
                    
                    # Set Content
                    if len(slide.placeholders) > 1:
                        content_shape = slide.placeholders[1]
                        tf = content_shape.text_frame
                        tf.clear() # Remove "Click to add text"
                        
                        points = slide_info.get('content', [])
                        if isinstance(points, str): points = [points]
                            
                        for point in points:
                            p = tf.add_paragraph()
                            # Clean up text: remove **bold** markers and extra spaces
                            clean_text = str(point).replace("**", "").replace("* ", "").strip()
                            p.text = clean_text
                            p.level = 0
                
                # --- FILE SAVING FIX ---
                # We add a timestamp so we never get "Permission Denied" errors
                safe_topic = re.sub(r'[\\/*?:"<>|]', "", topic) # Remove bad chars
                filename = f"{safe_topic.replace(' ', '_')}_{int(time.time())}.pptx"
                output_path = os.path.join(os.getcwd(), filename)
                
                prs.save(output_path)
                
                update_callback("step_3", "done")
                update_callback("final", f"Saved as {filename}")
                
                # Optional: Auto-open the file
                try:
                    os.startfile(output_path)
                except:
                    pass

            except Exception as e:
                print(f"ERROR: {e}")
                update_callback("error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _extract_json(self, text):
        """
        Robustly finds JSON in the AI response, ignoring extra text.
        """
        try:
            # 1. Attempt to clean markdown code blocks (e.g. ```json ... ```)
            match = re.search(r'```json(.*?)```', text, re.DOTALL)
            if match:
                text = match.group(1)
            elif re.search(r'```(.*?)```', text, re.DOTALL):
                match = re.search(r'```(.*?)```', text, re.DOTALL)
                text = match.group(1)

            # 2. Find the first '[' and last ']' to isolate the array
            start = text.find('[')
            end = text.rfind(']')
            
            if start != -1 and end != -1:
                json_str = text[start : end+1]
                return json.loads(json_str)
            
            return None
        except Exception as e:
            print(f"JSON PARSE ERROR: {e}")
            return None


class PPTEnricher:
    """
    AI-powered PowerPoint enrichment for existing presentations.
    Enhances content, formatting, and structure of slides.
    """
    
    def __init__(self):
        from app.engine.content_enricher import ContentEnricher
        self.enricher = ContentEnricher()
    
    def enhance_presentation(self, ppt_path, options, style="professional", update_callback=None):
        """
        Main method to enhance an existing PowerPoint presentation.
        
        Args:
            ppt_path: Path to existing .pptx file
            options: Dict of enhancement options {
                'improve_text': bool,
                'auto_format': bool,
                'add_summaries': bool,
                'suggest_improvements': bool,
                'fix_consistency': bool
            }
            style: Target style (professional, casual, academic, technical)
            update_callback: Function to call with progress updates
        
        Returns:
            Path to enhanced presentation
        """
        def run():
            try:
                if update_callback:
                    update_callback("step_1", "running")
                
                # Load presentation
                prs = Presentation(ppt_path)
                total_slides = len(prs.slides)
                
                if update_callback:
                    update_callback("step_1", "done")
                    update_callback("step_2", "running")
                
                # Process each slide
                for idx, slide in enumerate(prs.slides):
                    if update_callback:
                        update_callback("progress", f"Processing slide {idx + 1} of {total_slides}")
                    
                    # Extract and enhance text from all shapes
                    for shape in slide.shapes:
                        if hasattr(shape, "text_frame"):
                            self._enhance_text_frame(shape.text_frame, options, style)
                        
                        # Handle tables
                        if hasattr(shape, "table"):
                            self._enhance_table(shape.table, options, style)
                    
                    # Add slide notes/summaries if requested
                    if options.get('add_summaries', False):
                        self._add_slide_summary(slide)
                
                if update_callback:
                    update_callback("step_2", "done")
                    update_callback("step_3", "running")
                
                # Apply formatting if requested
                if options.get('auto_format', False):
                    self._apply_formatting(prs)
                
                # Save enhanced presentation
                base_name = os.path.basename(ppt_path)
                name_without_ext = os.path.splitext(base_name)[0]
                output_path = os.path.join(
                    os.path.dirname(ppt_path),
                    f"{name_without_ext}_ENHANCED_{int(time.time())}.pptx"
                )
                
                prs.save(output_path)
                
                if update_callback:
                    update_callback("step_3", "done")
                    update_callback("final", f"Saved as {os.path.basename(output_path)}")
                
                # Try to open the file
                try:
                    os.startfile(output_path)
                except:
                    pass
                
                return output_path
                
            except Exception as e:
                print(f"PPT Enhancement Error: {e}")
                if update_callback:
                    update_callback("error", str(e))
                return None
        
        # Run in thread if callback provided, otherwise run synchronously
        if update_callback:
            threading.Thread(target=run, daemon=True).start()
        else:
            return run()
    
    def _enhance_text_frame(self, text_frame, options, style):
        """Enhance text within a text frame"""
        if not text_frame.text.strip():
            return
        
        for paragraph in text_frame.paragraphs:
            if not paragraph.text.strip():
                continue
            
            original_text = paragraph.text
            enhanced_text = original_text
            
            # Improve text quality
            if options.get('improve_text', False):
                enhanced_text = self.enricher.improve_text(enhanced_text, style=style)
            
            # Fix consistency
            if options.get('fix_consistency', False):
                enhanced_text = self.enricher.fix_grammar(enhanced_text)
                enhanced_text = self.enricher.enhance_clarity(enhanced_text)
            
            # Update paragraph text while preserving formatting
            if enhanced_text != original_text:
                # Clear existing runs and add new text
                paragraph.text = enhanced_text
    
    def _enhance_table(self, table, options, style):
        """Enhance text within table cells"""
        for row in table.rows:
            for cell in row.cells:
                if cell.text_frame and cell.text_frame.text.strip():
                    self._enhance_text_frame(cell.text_frame, options, style)
    
    def _add_slide_summary(self, slide):
        """Add a summary to slide notes"""
        # Collect all text from the slide
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text)
        
        if slide_text:
            combined_text = " ".join(slide_text)
            summary = self.enricher.summarize_content(combined_text, max_length=50)
            
            # Add to notes
            if summary:
                notes_slide = slide.notes_slide
                text_frame = notes_slide.notes_text_frame
                text_frame.text = f"Summary: {summary}"
    
    def _apply_formatting(self, prs):
        """Apply consistent formatting to all slides"""
        from pptx.util import Pt
        from pptx.enum.text import PP_ALIGN
        
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text_frame"):
                    text_frame = shape.text_frame
                    
                    for paragraph in text_frame.paragraphs:
                        # Set consistent font size for body text
                        for run in paragraph.runs:
                            if run.font.size is None or run.font.size < Pt(12):
                                run.font.size = Pt(14)
                        
                        # Ensure proper spacing
                        paragraph.space_before = Pt(6)
                        paragraph.space_after = Pt(6)
    
    def get_improvement_suggestions(self, ppt_path):
        """
        Analyze presentation and provide improvement suggestions.
        
        Args:
            ppt_path: Path to .pptx file
        
        Returns:
            List of suggestions
        """
        try:
            prs = Presentation(ppt_path)
            all_suggestions = []
            
            for idx, slide in enumerate(prs.slides):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text)
                
                if slide_text:
                    combined = " ".join(slide_text)
                    suggestions = self.enricher.suggest_improvements(
                        combined, 
                        context=f"PowerPoint slide {idx + 1}"
                    )
                    
                    if suggestions:
                        all_suggestions.append(f"Slide {idx + 1}:")
                        all_suggestions.extend(suggestions)
                        all_suggestions.append("")  # Blank line
            
            return all_suggestions
            
        except Exception as e:
            print(f"Error getting suggestions: {e}")
            return [f"Error: {str(e)}"]
