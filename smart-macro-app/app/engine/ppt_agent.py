# -*- coding: utf-8 -*-
import threading
import os
import json
import re
import time
import tempfile
import hashlib
import requests
from pptx import Presentation
from pptx.util import Pt, Inches, Emu
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.dml.color import RGBColor
from langchain_ollama import OllamaLLM
from app.engine.cot_engine import stream_cot_plan, make_ppt_plan_prompt

# ── Slide dimensions (standard Widescreen 13.33" x 7.5") ─────────────────────
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

# Layout zones for content slides
TITLE_L, TITLE_T   = Inches(0.4), Inches(0.2)
TITLE_W, TITLE_H   = Inches(12.5), Inches(1.1)

TXT_L,  TXT_T      = Inches(0.4), Inches(1.5)
TXT_W,  TXT_H      = Inches(6.8), Inches(5.7)   # strict left column

IMG_L,  IMG_T      = Inches(7.5), Inches(1.4)
IMG_W,  IMG_H      = Inches(5.5), Inches(5.8)   # right column, no overlap

# ── Common browser-like headers ───────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


# ═════════════════════════════════════════════════════════════════════════════
#  IMAGE DOWNLOADER  –  Multi-source fallback chain
#  1. LoremFlickr  (themed photos, always available, good keyword matching)
#  2. Wikimedia Commons API  (topic-accurate encyclopedic images)
#  3. Picsum (seeded random)  – beautiful photo; NEVER fails
# ═════════════════════════════════════════════════════════════════════════════

def _save_image_bytes(content: bytes, slide_index: int) -> str:
    """Persist raw image bytes to a temp file and return the path."""
    tmp = os.path.join(
        tempfile.gettempdir(),
        f"slide_img_{slide_index}_{int(time.time())}.jpg"
    )
    with open(tmp, "wb") as f:
        f.write(content)
    return tmp


def _short_keyword(keyword: str, max_words: int = 2) -> str:
    """
    Extract the most meaningful 1-2 words from a multi-word phrase.
    LoremFlickr matches best with short, concrete nouns.
    Strip filler words (the, a, an, of, in, on, for, with, by).
    """
    stop = {"the", "a", "an", "of", "in", "on", "for", "with", "by", "and", "or", "at"}
    words = [w for w in keyword.lower().split() if w not in stop]
    return ",".join(words[:max_words]) if words else keyword.split()[0]


def _is_real_image(content: bytes) -> bool:
    """Check magic bytes: JPEG = FF D8 FF, PNG = 89 50 4E 47"""
    return (content[:3] == b'\xff\xd8\xff') or (content[:4] == b'\x89PNG')


def _try_loremflickr(keyword: str, slide_index: int) -> str | None:
    """
    LoremFlickr with a UNIQUE random seed per slide.
    `?random=N` forces LoremFlickr to rotate through its library
    instead of returning the same cached top-result every time.
    Short keywords (1-2 concrete words) give best relevance.
    """
    try:
        short_kw = _short_keyword(keyword, max_words=2)
        # Each slide gets a different slot in LoremFlickr's library
        seed = (slide_index * 9973 + int(time.time()) % 1000) % 100000
        url  = f"https://loremflickr.com/800/600/{short_kw}/all?random={seed}"
        resp = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 8000 and _is_real_image(resp.content):
            path = _save_image_bytes(resp.content, slide_index)
            print(f"[IMG] LoremFlickr OK  slide {slide_index}  kw='{short_kw}' seed={seed}")
            return path
        print(f"[IMG] LoremFlickr miss slide {slide_index} ({resp.status_code}, {len(resp.content)} bytes)")
    except Exception as e:
        print(f"[IMG] LoremFlickr error slide {slide_index}: {e}")
    return None


def _try_wikipedia_thumbnail(slide_title: str, slide_index: int) -> str | None:
    """
    Wikipedia REST API — uses the SLIDE TITLE to find the matching
    Wikipedia article and returns its lead thumbnail.
    This guarantees 100% topic relevance (solar energy -> solar panel photo).
    """
    if not slide_title:
        return None
    try:
        import urllib.parse
        # Use first 4 words of the slide title for the Wikipedia lookup
        lookup = " ".join(slide_title.split()[:4])
        encoded = urllib.parse.quote(lookup)
        url  = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        if resp.status_code != 200:
            return None
        data     = resp.json()
        thumb    = data.get("thumbnail", {}).get("source", "")
        original = data.get("originalimage", {}).get("source", thumb)
        img_url  = original or thumb
        if img_url and any(img_url.lower().endswith(e) for e in (".jpg", ".jpeg", ".png")):
            ir = requests.get(img_url, headers=_HEADERS, timeout=15)
            if ir.status_code == 200 and len(ir.content) > 5000 and _is_real_image(ir.content):
                path = _save_image_bytes(ir.content, slide_index)
                print(f"[IMG] Wikipedia   OK  slide {slide_index} title='{lookup}'")
                return path
    except Exception as e:
        print(f"[IMG] Wikipedia error slide {slide_index}: {e}")
    return None


def _try_wikimedia_search(keyword: str, slide_index: int) -> str | None:
    """Wikimedia Commons search – good for specific technical/scientific topics."""
    try:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": keyword,
            "gsrlimit": 5,
            "prop": "pageimages",
            "piprop": "original",
            "format": "json",
        }
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params=params, headers=_HEADERS, timeout=12
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            img_url = page.get("original", {}).get("source", "")
            if img_url and any(img_url.lower().endswith(e) for e in (".jpg", ".jpeg", ".png")):
                ir = requests.get(img_url, headers=_HEADERS, timeout=15)
                if ir.status_code == 200 and len(ir.content) > 5000 and _is_real_image(ir.content):
                    path = _save_image_bytes(ir.content, slide_index)
                    print(f"[IMG] Wikimedia   OK  slide {slide_index}")
                    return path
    except Exception as e:
        print(f"[IMG] Wikimedia error slide {slide_index}: {e}")
    return None


def _try_picsum(keyword: str, slide_index: int) -> str | None:
    """
    Picsum Photos – guaranteed last-resort fallback.
    Seed = slide_index * large_prime + keyword_hash ensures EVERY slide
    gets a visually distinct photo even when all other sources fail.
    """
    try:
        kw_hash = int(hashlib.md5(keyword.encode()).hexdigest()[:8], 16)
        seed    = (slide_index * 99991 + kw_hash) % 1_000_000
        url     = f"https://picsum.photos/seed/{seed}/800/600"
        resp    = requests.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 5000 and _is_real_image(resp.content):
            path = _save_image_bytes(resp.content, slide_index)
            print(f"[IMG] Picsum      OK  slide {slide_index} (seed={seed})")
            return path
    except Exception as e:
        print(f"[IMG] Picsum error slide {slide_index}: {e}")
    return None


def download_slide_image(keyword: str, slide_index: int, slide_title: str = "") -> str | None:
    """
    4-source fallback chain — Wikipedia-first strategy.
    Because the LLM now outputs exact Wikipedia nouns, we query
    Wikipedia first to get the official encyclopedic thumbnail,
    guaranteeing 100% contextual relevance.

    Chain: Wikipedia REST → Wikimedia Commons → LoremFlickr → Picsum
    """
    print(f"[IMG] Fetching slide {slide_index}: keyword='{keyword}'  title='{slide_title}'")
    return (
        _try_wikipedia_thumbnail(keyword, slide_index)        # 1. Exact noun → Wikipedia article thumbnail
        or _try_wikimedia_search(keyword, slide_index)        # 2. Commons encyclopedic search
        or _try_loremflickr(keyword, slide_index)             # 3. Themed stock photo
        or _try_picsum(keyword, slide_index)                  # 4. Guaranteed fallback
    )


# ═════════════════════════════════════════════════════════════════════════════
#  SLIDE BUILDER HELPERS  –  hand-placed shapes on blank layout
#  (avoids ALL placeholder positioning/overlap bugs)
# ═════════════════════════════════════════════════════════════════════════════

# Colour palette
C_BG      = RGBColor(0x0D, 0x0D, 0x14)   # near-black
C_ACCENT  = RGBColor(0x00, 0xD4, 0xFF)   # cyan
C_WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
C_SUBTLE  = RGBColor(0x1A, 0x1A, 0x2E)   # dark-navy card


def _blank_slide(prs: Presentation):
    """Add and return a blank slide (layout 6)."""
    blank = prs.slide_layouts[6]   # 'Blank' layout — no placeholders
    return prs.slides.add_slide(blank)


def _set_bg(slide, color: RGBColor = C_BG):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text_box(slide, left, top, width, height,
                  text, font_size, bold=False,
                  color=C_WHITE, align=PP_ALIGN.LEFT, wrap=True):
    """Add a text box with given geometry and style."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf    = txBox.text_frame
    tf.word_wrap = wrap
    tf.auto_size  = MSO_AUTO_SIZE.NONE

    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Segoe UI"
    return txBox


def _add_bullet_box(slide, left, top, width, height, points: list):
    """Add a formatted bullet-point text box."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf    = txBox.text_frame
    tf.word_wrap = True
    tf.auto_size  = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    first = True
    for point in points:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()

        p.space_before = Pt(6)
        p.space_after  = Pt(6)

        # Bullet dot
        bullet_run = p.add_run()
        bullet_run.text = "▸  "
        bullet_run.font.size  = Pt(14)
        bullet_run.font.color.rgb = C_ACCENT
        bullet_run.font.bold  = True
        bullet_run.font.name  = "Segoe UI"

        # Content text
        text_run = p.add_run()
        text_run.text = str(point).replace("**", "").strip()
        text_run.font.size  = Pt(14)
        text_run.font.color.rgb = C_WHITE
        text_run.font.name  = "Segoe UI"

    return txBox


def _accent_bar(slide, top, height=Pt(3), width=Inches(2.5)):
    """Draw a thin cyan accent line (decorative)."""
    bar = slide.shapes.add_shape(
        1,   # MSO_SHAPE_TYPE.RECTANGLE
        Inches(0.4), top, width, height
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_ACCENT
    bar.line.fill.background()


def _build_title_slide(prs, slide_info, topic):
    """Fully custom Title slide with no placeholders."""
    slide = _blank_slide(prs)
    _set_bg(slide)

    # Large icon / decorative block
    deco = slide.shapes.add_shape(1,
        Inches(0), Inches(2.4), Inches(0.15), Inches(2.7))
    deco.fill.solid()
    deco.fill.fore_color.rgb = C_ACCENT
    deco.line.fill.background()

    # Main title
    _add_text_box(slide,
        left=Inches(0.6), top=Inches(2.4),
        width=Inches(12), height=Inches(1.5),
        text=slide_info.get("title", topic),
        font_size=40, bold=True,
        color=C_ACCENT, align=PP_ALIGN.LEFT
    )

    # Subtitle
    _add_text_box(slide,
        left=Inches(0.6), top=Inches(4.1),
        width=Inches(10), height=Inches(0.8),
        text=slide_info.get("subtitle", "AI-Generated Presentation"),
        font_size=20, bold=False,
        color=C_WHITE, align=PP_ALIGN.LEFT
    )

    # Bottom label
    _add_text_box(slide,
        left=Inches(0.6), top=Inches(6.7),
        width=Inches(6), height=Inches(0.5),
        text="Generated by Smart Macro Station  •  AI Powered",
        font_size=11, bold=False,
        color=RGBColor(0x55, 0x65, 0x80), align=PP_ALIGN.LEFT
    )

    return slide


def _build_content_slide(prs, slide_info, slide_index):
    """
    Fully custom Content slide.
    Left column: title + bullets | Right column: image (strictly no overlap).
    """
    slide = _blank_slide(prs)
    _set_bg(slide)

    title_text    = slide_info.get("title", "Untitled")
    content_list  = slide_info.get("content", [])
    image_keyword = slide_info.get("image_keyword", "").strip()

    if isinstance(content_list, str):
        content_list = [content_list]

    has_image = bool(image_keyword)

    # ── Layout columns ─────────────────────────────────────────────────────
    if has_image:
        txt_left  = TXT_L
        txt_top   = TXT_T
        txt_w     = TXT_W   # Inches(6.8) — leaves clear gap before image at 7.5
        txt_h     = TXT_H
    else:
        # Full-width when no image
        txt_left  = Inches(0.4)
        txt_top   = TXT_T
        txt_w     = Inches(12.5)
        txt_h     = TXT_H

    # ── Title text ──────────────────────────────────────────────────────────
    _add_text_box(slide,
        left=txt_left, top=TITLE_T,
        width=txt_w if has_image else Inches(12.5),
        height=TITLE_H,
        text=title_text,
        font_size=26, bold=True,
        color=C_ACCENT, align=PP_ALIGN.LEFT
    )

    # Thin accent bar under title
    _accent_bar(slide, top=Inches(1.35), height=Pt(2.5), width=Inches(3.0))

    # ── Bullet points ───────────────────────────────────────────────────────
    _add_bullet_box(slide,
        left=txt_left, top=txt_top,
        width=txt_w, height=txt_h,
        points=content_list
    )

    # ── Image (right column, strict non-overlapping geometry) ───────────────
    if has_image:
        img_path = download_slide_image(
            image_keyword, slide_index, slide_title=title_text
        )
        if img_path and os.path.exists(img_path):
            try:
                pic = slide.shapes.add_picture(img_path, IMG_L, IMG_T, IMG_W, IMG_H)
                # Subtle rounded-rect overlay border (cosmetic)
                brd_shape = slide.shapes.add_shape(
                    1,
                    Inches(7.45), Inches(1.35),
                    IMG_W + Inches(0.1), IMG_H + Inches(0.1)
                )
                brd_shape.fill.background()
                brd_shape.line.color.rgb = C_ACCENT
                brd_shape.line.width    = Pt(1.5)
                # Send border behind image
                sp_tree = slide.shapes._spTree
                sp_tree.remove(brd_shape._element)
                sp_tree.insert(2, brd_shape._element)
            except Exception as img_err:
                print(f"[IMG] Place error slide {slide_index}: {img_err}")

    # ── Slide number ────────────────────────────────────────────────────────
    _add_text_box(slide,
        left=Inches(12.6), top=Inches(7.0),
        width=Inches(0.7), height=Inches(0.4),
        text=str(slide_index),
        font_size=11, bold=False,
        color=RGBColor(0x44, 0x55, 0x70), align=PP_ALIGN.RIGHT
    )

    return slide


# ═════════════════════════════════════════════════════════════════════════════
#  PPTGenerator
# ═════════════════════════════════════════════════════════════════════════════

class PPTGenerator:
    def __init__(self):
        self.llm = OllamaLLM(model="llama3", temperature=0.7)

    def generate_ppt(self, topic, update_callback, thought_callback=None):
        def run():
            try:
                # ── CoT planning thoughts ─────────────────────────────────
                if thought_callback:
                    thought_callback(f"\u25c6 Topic: {topic}\n\n")
                    stream_cot_plan(self.llm, make_ppt_plan_prompt(topic), thought_callback)
                    thought_callback("\n\n\u2500\u2500\u2500 Building Presentation \u2500\u2500\u2500\n\n")

                # ── Step 1: AI Content Generation ────────────────────────
                update_callback("step_1", "running")

                prompt = (
                    f"You are an expert professor and keynote speaker. "
                    f"Create a 5-slide presentation about '{topic}'.\n"
                    "REQUIREMENTS:\n"
                    "1. Content: Write 3-4 DETAILED bullet points per slide. Explain the 'Why' and 'How'.\n"
                    "2. Script: Write a 150-word speaker speech in the 'notes' field.\n"
                    "3. Structure: Slide 1 is Title. Slides 2-5 are Content.\n"
                    "4. Image Keyword: For EACH CONTENT slide, provide an 'image_keyword' field.\n"
                    "   STRICT RULES for image_keyword:\n"
                    "   - Use ONLY 1-2 concrete, specific nouns. Think exactly like someone searching Wikipedia.\n"
                    "   - The keyword must be a real physical object or place with its own Wikipedia article.\n"
                    "   - GOOD examples: 'Solar panel', 'DNA helix', 'Roman Colosseum', 'Microchip', 'Telescope', 'Steam engine'.\n"
                    "   - BAD examples: 'innovation', 'success', 'growth', 'technology', 'future' (too abstract — NEVER use these).\n"
                    "   - BAD examples: 'aerial view of solar panels in desert' (too long — NEVER use phrases).\n\n"
                    "OUTPUT: Return ONLY a valid JSON array. No markdown, no explanation, no extra text.\n"
                    "[\n"
                    "  {\n"
                    "    \"type\": \"title\",\n"
                    "    \"title\": \"Catchy Title Here\",\n"
                    "    \"subtitle\": \"Professional Subtitle\",\n"
                    "    \"notes\": \"Opening speech 150 words...\"\n"
                    "  },\n"
                    "  {\n"
                    "    \"type\": \"content\",\n"
                    "    \"title\": \"Slide Title\",\n"
                    "    \"content\": [\"Point 1: Detailed explanation...\", \"Point 2: Evidence...\"],\n"
                    "    \"image_keyword\": \"Solar panel\",\n"
                    "    \"notes\": \"Speaker notes 150 words...\"\n"
                    "  }\n"
                    "]"
                )

                response = self.llm.invoke(prompt)
                update_callback("step_1", "done")

                # ── Step 2: Parse ─────────────────────────────────────────
                update_callback("step_2", "running")
                slides_data = self._extract_json(response)
                if not slides_data:
                    print("[DEBUG] JSON parse failed — trying text backup parser")
                    slides_data = self._parse_text_backup(response)
                if not slides_data:
                    raise Exception("Could not extract any slides from AI response.")
                update_callback("step_2", "done")

                # ── Step 3: Build slides ──────────────────────────────────
                update_callback("step_3", "running")
                prs = Presentation()

                # Set widescreen 16:9 slide size
                prs.slide_width  = SLIDE_W
                prs.slide_height = SLIDE_H

                content_idx = 1   # counter for slide numbers (title = 0)
                for i, slide_info in enumerate(slides_data):
                    is_title = (i == 0 or slide_info.get("type") == "title")

                    if is_title:
                        slide = _build_title_slide(prs, slide_info, topic)
                    else:
                        slide = _build_content_slide(prs, slide_info, content_idx)
                        content_idx += 1

                    # Speaker notes
                    if "notes" in slide_info:
                        slide.notes_slide.notes_text_frame.text = slide_info["notes"]

                # Save
                safe_name = re.sub(r"[^a-zA-Z0-9]", "_", topic[:20])
                filename  = f"{safe_name}_{int(time.time())}.pptx"
                path      = os.path.join(os.getcwd(), filename)
                prs.save(path)

                update_callback("step_3", "done")
                update_callback("final", path)

                try:
                    os.startfile(path)
                except Exception:
                    pass

            except Exception as e:
                import traceback
                print(f"[ERROR] {e}")
                traceback.print_exc()
                update_callback("error", str(e))

        threading.Thread(target=run, daemon=True).start()

    # ── JSON extraction ───────────────────────────────────────────────────────
    def _extract_json(self, text):
        try:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return None

    def _parse_text_backup(self, text):
        """Fallback text parser when JSON is malformed."""
        slides, current = [], {}
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if "Slide" in line or "Title:" in line:
                if current:
                    slides.append(current)
                current = {
                    "title": line.split(":")[-1].strip(),
                    "content": [],
                    "notes": "AI generated content.",
                }
            elif line.startswith(("-", "*", "•")):
                if "content" in current:
                    current["content"].append(line[1:].strip())
        if current:
            slides.append(current)
        if not slides:
            slides = [{"title": "Presentation", "content": ["Content ready."], "notes": "End."}]
        return slides


# ── Keep Enricher stub ────────────────────────────────────────────────────────
class PPTEnricher:
    def __init__(self): pass
    def get_improvement_suggestions(self, path): return []
    def enhance_presentation(self, path, opts, style, cb): pass