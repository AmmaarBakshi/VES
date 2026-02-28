"""
Batch Processing Engine
=======================
Scans a folder, identifies file types, and dispatches each file to the
correct agent engine for AI processing — all in a background thread.

Supported actions:
  - enhance_docs    → Word (.docx) enrich
  - format_excel    → Excel (.xlsx / .csv) enrich + format
  - smart_process   → Run a custom AI instruction on docx/xlsx files
  - generate_summary → Summarize each file's text content via PDF/Word reader
"""

import os
import threading
import time
from typing import Callable, Optional

# ── File type maps ──────────────────────────────────────────────────────────
WORD_EXTS   = {".docx"}
EXCEL_EXTS  = {".xlsx", ".xls", ".csv"}
PPT_EXTS    = {".pptx", ".ppt"}
PDF_EXTS    = {".pdf"}
ALL_EXTS    = WORD_EXTS | EXCEL_EXTS | PPT_EXTS | PDF_EXTS

ACTION_LABELS = {
    "enhance_docs":      "AI Enhance (Grammar, Clarity, Formatting)",
    "format_excel":      "Format & Enrich Excel / CSV",
    "smart_process":     "Smart Process (Custom AI Instruction)",
    "generate_summary":  "Generate Summary Report",
}


def scan_folder(folder: str, exts: set | None = None) -> list[str]:
    """Return all files in folder (non-recursive) matching exts filter."""
    exts = exts or ALL_EXTS
    files = []
    try:
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in exts:
                files.append(path)
    except Exception as e:
        print(f"[Batch] Scan error: {e}")
    return files


# ── Callbacks type hint helper ───────────────────────────────────────────────
# status_cb(filepath, status)   status ∈ 'pending'|'running'|'done'|'error'
# thought_cb(text)              streams CoT reasoning tokens
# finish_cb(summary_dict)       called when all files are processed


def run_batch(
    folder: str,
    action: str,
    instruction: str,                   # used for smart_process
    status_cb: Callable,
    thought_cb: Callable,
    finish_cb: Callable,
    options: Optional[dict] = None,
    style: str = "professional",
):
    """
    Runs the batch job in a daemon thread.
    Calls status_cb / thought_cb / finish_cb from that thread.
    """
    def _worker():
        files = scan_folder(folder)
        if not files:
            thought_cb("No supported files found in the selected folder.\n")
            finish_cb({"processed": 0, "errors": 0, "skipped": 0})
            return

        thought_cb(f"Batch Mode -- {ACTION_LABELS.get(action, action)}\n")
        thought_cb(f"Folder: {folder}\n")
        thought_cb(f"Files found: {len(files)}\n\n")

        results = {"processed": 0, "errors": 0, "skipped": 0}
        output_paths = []

        for filepath in files:
            ext  = os.path.splitext(filepath)[1].lower()
            name = os.path.basename(filepath)

            status_cb(filepath, "running")
            thought_cb(f"--- Processing: {name} ---\n")

            try:
                out = _dispatch(filepath, ext, action, instruction, options, style, thought_cb)
                if out and not str(out).startswith("Error"):
                    status_cb(filepath, "done")
                    output_paths.append(str(out))
                    results["processed"] += 1
                    thought_cb(f"Done -> {os.path.basename(str(out))}\n\n")
                else:
                    status_cb(filepath, "error")
                    results["errors"] += 1
                    thought_cb(f"Failed: {out}\n\n")

            except Exception as e:
                status_cb(filepath, "error")
                results["errors"] += 1
                thought_cb(f"Exception: {e}\n\n")

        thought_cb(
            f"\n{'='*40}\n"
            f"Processed : {results['processed']}\n"
            f"Errors    : {results['errors']}\n"
            f"Skipped   : {results['skipped']}\n"
        )
        results["output_paths"] = output_paths
        finish_cb(results)

    threading.Thread(target=_worker, daemon=True).start()


def _dispatch(filepath, ext, action, instruction, options, style, thought_cb):
    """Route a single file to the correct engine based on action + ext."""

    opts = options or {
        "improve_content":    True,
        "fix_consistency":    True,
        "add_summaries":      True,
        "auto_format":        True,
        "improve_paragraphs": True,
        "add_summary":        True,
    }

    # ── ENHANCE DOCS ────────────────────────────────────────────────────────
    if action == "enhance_docs":
        if ext in WORD_EXTS:
            from app.engine.word_agent import enrich_word_document
            return enrich_word_document(filepath, opts, style=style, thought_callback=thought_cb)
        elif ext in EXCEL_EXTS:
            from app.engine.excel_agent import enrich_excel_file
            return enrich_excel_file(filepath, opts, style=style, thought_callback=thought_cb)
        elif ext in PPT_EXTS:
            return _enrich_pptx(filepath, opts, style, thought_cb)
        else:
            thought_cb(f"Skipping unsupported type for enhance: {ext}\n")
            return None

    # ── FORMAT EXCEL ────────────────────────────────────────────────────────
    elif action == "format_excel":
        if ext in EXCEL_EXTS:
            from app.engine.excel_agent import enrich_excel_file
            return enrich_excel_file(filepath, opts, style=style, thought_callback=thought_cb)
        else:
            thought_cb(f"Skipping non-Excel file: {os.path.basename(filepath)}\n")
            return "skipped"

    # ── SMART PROCESS ───────────────────────────────────────────────────────
    elif action == "smart_process":
        if ext in WORD_EXTS:
            from app.engine.word_agent import process_word_document
            return process_word_document(filepath, instruction, thought_callback=thought_cb)
        elif ext in EXCEL_EXTS:
            from app.engine.excel_agent import process_excel_file
            return process_excel_file(filepath, instruction, thought_callback=thought_cb)
        else:
            thought_cb(f"Smart Process supports .docx/.xlsx only -- skipping {ext}\n")
            return "skipped"

    # ── GENERATE SUMMARY ────────────────────────────────────────────────────
    elif action == "generate_summary":
        return _generate_file_summary(filepath, ext, thought_cb)

    else:
        thought_cb(f"Unknown action: {action}\n")
        return "skipped"


def _enrich_pptx(filepath, opts, style, thought_cb):
    """
    Open an existing .pptx and apply light AI enrichment.
    Saves as <name>_ENHANCED.pptx beside the original.
    """
    try:
        import time as _t
        from pptx import Presentation
        from app.engine.content_enricher import ContentEnricher

        enricher = ContentEnricher()
        prs = Presentation(filepath)

        thought_cb(f"  Slides found: {len(prs.slides)}\n")

        for i, slide in enumerate(prs.slides):
            thought_cb(f"  Slide {i+1}/{len(prs.slides)}...\n")
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if run.text and len(run.text.split()) > 3:
                            if opts.get("improve_paragraphs") or opts.get("improve_content"):
                                run.text = enricher.improve_text(
                                    run.text, style=style, intensity="light"
                                )

        name = os.path.splitext(os.path.basename(filepath))[0]
        out  = os.path.join(
            os.path.dirname(filepath),
            f"{name}_ENHANCED_{int(_t.time())}.pptx"
        )
        prs.save(out)
        return out
    except Exception as e:
        print(f"[Batch] PPT enrich error: {e}")
        return f"Error: {e}"


def _generate_file_summary(filepath, ext, thought_cb):
    """
    Extract text from a file and write an AI summary to a .txt report.
    """
    try:
        import time as _t
        from app.engine.content_enricher import ContentEnricher

        enricher = ContentEnricher()
        raw_text = ""

        if ext in WORD_EXTS:
            from docx import Document
            doc = Document(filepath)
            raw_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

        elif ext in EXCEL_EXTS:
            import pandas as pd
            if ext == ".csv":
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            raw_text = df.to_string(index=False)[:3000]

        elif ext in PPT_EXTS:
            from pptx import Presentation
            prs = Presentation(filepath)
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        parts.append(shape.text_frame.text)
            raw_text = "\n".join(parts)

        elif ext in PDF_EXTS:
            thought_cb("  PDF summary: reading text...\n")
            try:
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    raw_text = "\n".join(
                        page.extract_text() or "" for page in pdf.pages
                    )[:3000]
            except ImportError:
                raw_text = "[pdfplumber not installed -- install with: pip install pdfplumber]"

        if not raw_text.strip():
            return "Error: No text content found"

        thought_cb("  Generating AI summary...\n")
        summary = enricher.summarize_content(raw_text[:2000], max_length=150)

        name = os.path.splitext(os.path.basename(filepath))[0]
        out  = os.path.join(
            os.path.dirname(filepath),
            f"{name}_SUMMARY_{int(_t.time())}.txt"
        )
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"=== AI Summary: {os.path.basename(filepath)} ===\n\n")
            f.write(summary)
            f.write("\n\n=== Source Text Preview ===\n\n")
            f.write(raw_text[:500])
        return out

    except Exception as e:
        print(f"[Batch] Summary error: {e}")
        return f"Error: {e}"
