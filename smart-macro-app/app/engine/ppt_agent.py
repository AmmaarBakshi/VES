import threading
import os
import json
import re
import time
import tempfile
import requests
from pptx import Presentation
from pptx.util import Pt, Inches, Emu
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.dml.color import RGBColor
from langchain_ollama import OllamaLLM
from app.engine.cot_engine import stream_cot_plan, make_ppt_plan_prompt

# ── Slide dimension constants (standard 10" x 7.5") ──────────────────────
SLIDE_W = Inches(10)
SLIDE_H = Inches(7.5)
IMG_W   = Inches(4.0)   # right 40% of slide
IMG_H   = Inches(4.5)
IMG_L   = Inches(5.8)   # left edge of image
IMG_T   = Inches(1.6)   # top (below title)
TXT_W   = Inches(5.5)   # text box capped to left side when image present


def download_slide_image(keyword: str, slide_index: int) -> str | None:
    """
    Download a free, watermark-free image from pollinations.ai.
    Returns the temp file path or None on failure.
    """
    try:
        safe_kw = keyword.strip().replace(" ", "%20")
        url = f"https://image.pollinations.ai/prompt/{safe_kw}?width=800&height=600&nologo=true"
        resp = requests.get(url, timeout=25)
        if resp.status_code == 200 and resp.content:
            tmp = os.path.join(tempfile.gettempdir(), f"slide_img_{slide_index}_{int(time.time())}.jpg")
            with open(tmp, "wb") as f:
                f.write(resp.content)
            print(f"[IMG] Downloaded image for slide {slide_index}: {tmp}")
            return tmp
        print(f"[IMG] Non-200 response ({resp.status_code}) for slide {slide_index}")
        return None
    except Exception as e:
        print(f"[IMG] Image download failed for slide {slide_index}: {e}")
        return None


class PPTGenerator:
    def __init__(self):
        # Temperature 0.7 for creative output
        self.llm = OllamaLLM(model="llama3", temperature=0.7)

    def generate_ppt(self, topic, update_callback, thought_callback=None):
        def run():
            try:
                # ── Agentic CoT: Stream planning thoughts before any work ──
                if thought_callback:
                    thought_callback(f"◆ Topic: {topic}\n\n")
                    plan_prompt = make_ppt_plan_prompt(topic)
                    stream_cot_plan(self.llm, plan_prompt, thought_callback)
                    thought_callback("\n\n─── Generating Presentation ───\n\n")

                # --- Step 1: Research & Scripting ---
                update_callback("step_1", "running")
                print(f"\n[DEBUG] Sending prompt for: {topic}")

                prompt = (
                    f"You are an expert professor and keynote speaker. Create a 5-slide presentation about '{topic}'.\n"
                    "REQUIREMENTS:\n"
                    "1. Content: Write 3-4 DETAILED bullet points per slide. Explain the 'Why' and 'How'.\n"
                    "2. Script: Write a VERY LONG, 150-WORD SPEECH for the speaker notes. Write exactly what the speaker should say.\n"
                    "3. Structure: Slide 1 is Title. Slides 2-5 are Content.\n"
                    "4. Image: For each CONTENT slide, provide a short, vivid 'image_keyword' (3-6 words) perfect for a stock image search.\n\n"
                    "OUTPUT FORMAT: Return ONLY a valid JSON array. No other text.\n"
                    "[\n"
                    "  {\n"
                    "    \"type\": \"title\",\n"
                    "    \"title\": \"Catchy Main Title\",\n"
                    "    \"subtitle\": \"Professional Subtitle\",\n"
                    "    \"notes\": \"(Opening Speech): Welcome everyone... [write 150 words here]\"\n"
                    "  },\n"
                    "  {\n"
                    "    \"type\": \"content\",\n"
                    "    \"title\": \"Slide Title\",\n"
                    "    \"content\": [\"Point 1: Detailed explanation...\", \"Point 2: Evidence and examples...\"],\n"
                    "    \"image_keyword\": \"renewable energy solar farm aerial\",\n"
                    "    \"notes\": \"(Script): On this slide... [write 150 words here]\"\n"
                    "  }\n"
                    "]"
                )

                response = self.llm.invoke(prompt)
                print(f"[DEBUG] AI Response received.")

                update_callback("step_1", "done")

                # --- Step 2: Parsing ---
                update_callback("step_2", "running")

                slides_data = self._extract_json(response)
                if not slides_data:
                    print("[DEBUG] JSON parse failed. Switching to Backup Text Parser.")
                    slides_data = self._parse_text_backup(response)

                if not slides_data:
                    raise Exception("Could not extract any slides from AI response.")

                update_callback("step_2", "done")

                # --- Step 3: Design & Build ---
                update_callback("step_3", "running")
                prs = Presentation()

                for i, slide_info in enumerate(slides_data):
                    is_title = (i == 0 or slide_info.get("type") == "title")
                    image_keyword = slide_info.get("image_keyword", "").strip()

                    # 1. Choose Layout
                    if is_title:
                        layout = prs.slide_layouts[0]  # Title Slide
                        slide = prs.slides.add_slide(layout)

                        if slide.shapes.title:
                            slide.shapes.title.text = slide_info.get('title', topic)
                        if len(slide.placeholders) > 1:
                            slide.placeholders[1].text = slide_info.get('subtitle', 'Generated by AI')

                    else:
                        layout = prs.slide_layouts[1]  # Content Slide
                        slide = prs.slides.add_slide(layout)

                        if slide.shapes.title:
                            slide.shapes.title.text = slide_info.get('title', 'Untitled')

                        # ── Content text box (shrunk to left if image available) ──
                        if len(slide.placeholders) > 1:
                            body = slide.placeholders[1]
                            tf = body.text_frame
                            tf.clear()

                            content = slide_info.get('content', [])
                            if isinstance(content, str):
                                content = [content]

                            for point in content:
                                p = tf.add_paragraph()
                                p.text = str(point).replace("**", "").strip()
                                p.level = 0
                                p.space_after = Pt(10)

                            # Shrink text box to left side when an image keyword is present
                            if image_keyword:
                                body.width = TXT_W

                        # ── Download & insert image on right side ──
                        if image_keyword:
                            img_path = download_slide_image(image_keyword, i)
                            if img_path and os.path.exists(img_path):
                                try:
                                    slide.shapes.add_picture(img_path, IMG_L, IMG_T, IMG_W, IMG_H)
                                    # Subtle rounded border via line (not native rounded corners in pptx)
                                except Exception as img_err:
                                    print(f"[IMG] Failed to place image on slide {i}: {img_err}")

                    # 2. Apply "Cyber Dark" Theme
                    self._apply_cyber_theme(slide)

                    # 3. Add Speaker Script (Notes)
                    if "notes" in slide_info:
                        if not slide.has_notes_slide:
                            slide.notes_slide
                        text_frame = slide.notes_slide.notes_text_frame
                        text_frame.text = slide_info["notes"]

                    # 4. FORCE AUTO-FIT on content placeholder
                    if not is_title and len(slide.placeholders) > 1:
                        body = slide.placeholders[1]
                        body.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
                        body.text_frame.word_wrap = True

                # Save
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', topic[:20])
                filename = f"{safe_name}_{int(time.time())}.pptx"
                path = os.path.join(os.getcwd(), filename)

                prs.save(path)

                update_callback("step_3", "done")
                update_callback("final", path)   # ← full path now for download button

                try:
                    os.startfile(path)
                except:
                    pass

            except Exception as e:
                print(f"[ERROR] {e}")
                import traceback; traceback.print_exc()
                update_callback("error", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _apply_cyber_theme(self, slide):
        """Applies 'Cyber Dark' theme WITHOUT breaking Auto-Fit."""
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(18, 18, 18)

        if slide.shapes.title:
            title = slide.shapes.title
            for paragraph in title.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = RGBColor(0, 240, 255)
                    run.font.bold = True
                    run.font.name = "Arial"

        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            if shape == slide.shapes.title:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)
                    run.font.name = "Arial"

    def _extract_json(self, text):
        try:
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return None
        except:
            return None

    def _parse_text_backup(self, text):
        """Fallback if JSON fails."""
        slides = []
        current = {}
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if "Slide" in line or "Title:" in line:
                if current:
                    slides.append(current)
                title = line.split(":")[-1].strip()
                current = {"title": title, "content": [], "notes": "AI generated content."}
            elif line.startswith("-") or line.startswith("*"):
                if "content" in current:
                    current["content"].append(line[1:].strip())
        if current:
            slides.append(current)

        if not slides:
            return [{"title": "Presentation", "content": ["Content generated successfully."], "notes": "End of presentation."}]
        return slides


# --- Keep Enricher Class ---
class PPTEnricher:
    def __init__(self): pass
    def get_improvement_suggestions(self, path): return []
    def enhance_presentation(self, path, opts, style, cb): pass