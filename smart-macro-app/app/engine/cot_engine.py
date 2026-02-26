"""
cot_engine.py  —  Shared Agentic Chain-of-Thought streaming helper.

Usage in any engine:
    from app.engine.cot_engine import stream_cot_plan

    stream_cot_plan(
        llm,                  # Any OllamaLLM / Ollama instance
        prompt,               # The planning prompt string
        thought_callback,     # callable(str) or None — called per-token
    )
"""

from langchain_ollama import OllamaLLM



# ---------------------------------------------------------------------------
# Core streaming helper
# ---------------------------------------------------------------------------

def stream_cot_plan(llm, prompt: str, thought_callback=None):
    """
    Streams an LLM response token-by-token and fires thought_callback for each
    chunk received. Safe to call with thought_callback=None (silent fallback).

    Args:
        llm:              LangChain LLM instance that supports .stream()
        prompt:           The chain-of-thought prompt to send
        thought_callback: Optional callable(str) — receives each streamed token
    """
    if thought_callback is None:
        return  # No terminal attached — skip gracefully

    try:
        for chunk in llm.stream(prompt):
            if chunk:
                thought_callback(chunk)
    except Exception as e:
        thought_callback(f"\n[CoT stream error: {e}]\n")


# ---------------------------------------------------------------------------
# Prompt builders  (one per domain — keeps engines clean)
# ---------------------------------------------------------------------------

def make_dir_plan_prompt(tree_text: str, context: str) -> str:
    return (
        f"You are an expert software architect. I am about to scaffold this project structure:\n"
        f"```\n{tree_text[:800]}\n```\n"
        f"Detected stack: {context}\n\n"
        "Think step-by-step OUT LOUD. What folders should I create first? Which files are critical? "
        "What starter code patterns will I use? Keep thoughts concise, one sentence per step. "
        "Prefix each thought with 'Thinking:'. Begin."
    )


def make_ppt_plan_prompt(topic: str) -> str:
    return (
        f"You are preparing a 5-slide PowerPoint presentation about: '{topic}'.\n"
        "Think step-by-step OUT LOUD. What is the best angle? What 4 content slides will you cover? "
        "What evidence or examples will make each slide compelling? "
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


def make_pdf_plan_prompt(topic: str) -> str:
    return (
        f"You are about to write a professional PDF document about: '{topic}'.\n"
        "Think step-by-step OUT LOUD. What is the core thesis? What sections will you include? "
        "What tone and structure will make this a high-quality document? "
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


def make_word_plan_prompt(instruction: str, paragraph_count: int) -> str:
    return (
        f"You are about to process a Word document with {paragraph_count} paragraphs.\n"
        f"User instruction: '{instruction}'\n"
        "Think step-by-step OUT LOUD. How will you approach each paragraph? "
        "What style changes will you make? What will you preserve?\n"
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


def make_excel_plan_prompt(instruction: str, row_count: int, col_names: list) -> str:
    cols = ", ".join(col_names[:6])
    return (
        f"You are about to process an Excel file with {row_count} rows. Columns: {cols}.\n"
        f"User instruction: '{instruction}'\n"
        "Think step-by-step OUT LOUD. How will you analyze each column? "
        "What transformations seem relevant? What output format?\n"
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


def make_smart_fill_plan_prompt(template_text: str, data_text: str) -> str:
    template_preview = template_text[:300]
    data_preview = data_text[:300]
    return (
        f"You are about to merge data into a document template.\n"
        f"Template preview:\n{template_preview}\n\nData preview:\n{data_preview}\n\n"
        "Think step-by-step OUT LOUD. Which placeholders do you see? "
        "Which data fields map to which placeholders? What tone to adopt?\n"
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


def make_enhance_plan_prompt(file_type: str, options: dict, style: str) -> str:
    active = [k for k, v in options.items() if v]
    opts_str = ", ".join(active) if active else "general improvements"
    return (
        f"You are about to enhance a {file_type} document in '{style}' style.\n"
        f"Options enabled: {opts_str}.\n"
        "Think step-by-step OUT LOUD. What will you change first? "
        "How will you preserve the original meaning while improving quality?\n"
        "Keep thoughts concise, one line per step. Prefix each with 'Thinking:'. Begin."
    )


# ---------------------------------------------------------------------------
# Conversational Q&A — Clarification generators (per domain)
# ---------------------------------------------------------------------------

# Short, targeted questions for the AI to ask the USER before execution.
_CLARIFY_PROMPTS = {
    "ppt": (
        "You are about to create a PowerPoint presentation. Ask the user exactly 3 concise, "
        "friendly clarifying questions to improve the output. Cover: (1) number of slides or depth, "
        "(2) target audience, (3) tone (formal/casual/technical). "
        "Format: one question per line, no numbering, no intro sentence. Just the 3 questions."
    ),
    "pdf": (
        "You are about to write a professional PDF document. Ask the user exactly 3 concise, "
        "friendly clarifying questions. Cover: (1) desired document length, "
        "(2) academic or professional or casual tone, (3) any specific sections to include. "
        "Format: one question per line, no numbering, no intro sentence. Just the 3 questions."
    ),
    "word_process": (
        "You are about to process a Word document with AI. Ask the user exactly 2 concise "
        "clarifying questions. Cover: (1) whether to preserve the original structure, "
        "(2) any specific style or terminology requirements. "
        "Format: one question per line, no numbering, no intro. Just the 2 questions."
    ),
    "excel_process": (
        "You are about to process an Excel file with AI. Ask the user exactly 2 concise "
        "clarifying questions. Cover: (1) which columns matter most, "
        "(2) preferred output format or any columns to skip. "
        "Format: one question per line, no numbering, no intro. Just the 2 questions."
    ),
    "enhance": (
        "You are about to enhance a document. Ask the user exactly 2 concise "
        "clarifying questions. Cover: (1) what matters most — grammar, tone, or structure, "
        "(2) any sections that must NOT be changed. "
        "Format: one question per line, no numbering, no intro. Just the 2 questions."
    ),
    "smart_fill": (
        "You are about to fill a document template with data. Ask the user exactly 2 concise "
        "clarifying questions. Cover: (1) any placeholders to leave empty, "
        "(2) the preferred date/number format to use. "
        "Format: one question per line, no numbering, no intro. Just the 2 questions."
    ),
    "directory": (
        "You are about to scaffold a code project from a directory tree. Ask the user exactly "
        "2 concise clarifying questions. Cover: (1) development or production scaffolding, "
        "(2) whether any files should be left empty (no starter code). "
        "Format: one question per line, no numbering, no intro. Just the 2 questions."
    ),
}


def generate_clarifications(llm, task_type: str) -> str:
    """
    Generate 2-3 clarifying questions for the given task type.

    Args:
        llm:       An OllamaLLM instance (can be the engine's own llm)
        task_type: One of 'ppt', 'pdf', 'word_process', 'excel_process',
                   'enhance', 'smart_fill', 'directory'

    Returns:
        A multi-line string with one question per line.
    """
    prompt = _CLARIFY_PROMPTS.get(task_type, (
        "Ask the user 2 short clarifying questions about their task before you start. "
        "One question per line. No intro. Just the questions."
    ))
    try:
        return llm.invoke(prompt).strip()
    except Exception as e:
        return f"What specific outcome are you looking for?\n(Could not generate questions: {e})"


def stream_clarifications(llm, task_type: str, token_callback):
    """
    Stream clarifying questions token-by-token into token_callback(str).
    Uses .stream() for a live typing effect in the chat panel.
    """
    prompt = _CLARIFY_PROMPTS.get(task_type, (
        "Ask the user 2 short clarifying questions. One per line. No intro."
    ))
    try:
        for chunk in llm.stream(prompt):
            if chunk:
                token_callback(chunk)
    except Exception as e:
        token_callback(f"\nWhat specific outcome are you looking for?\n")
