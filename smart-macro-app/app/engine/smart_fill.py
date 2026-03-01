from app.ai.llm_client import query_ollama
from langchain_ollama import OllamaLLM
from app.engine.cot_engine import stream_cot_plan, make_smart_fill_plan_prompt
from app.utils.config_loader import load_ai_config

# Shared LLM for CoT planning
_plan_llm = None
def _get_plan_llm():
    global _plan_llm
    if _plan_llm is None:
        config = load_ai_config()
        model_name = config.get("active_model", "llama3.2")
        _plan_llm = OllamaLLM(model=model_name, temperature=0.5)
    return _plan_llm


def smart_fill_content(data_text, template_text, reference_text="None", thought_callback=None):
    """
    Merges data into a template using a reference style.
    thought_callback: optional callable(str) for streaming CoT reasoning.
    """
    # ── Agentic CoT: Stream planning thoughts before generating ──
    if thought_callback:
        thought_callback("◆ Analyzing template and data...\n\n")
        plan_prompt = make_smart_fill_plan_prompt(template_text, data_text)
        stream_cot_plan(_get_plan_llm(), plan_prompt, thought_callback)
        thought_callback("\n\n─── Generating Document ───\n\n")

    prompt = f"""
    You are a smart document filler.
    
    1. REFERENCE STYLE (Mimic this tone/format):
    {reference_text}
    
    2. DATA SOURCE (Use these facts):
    {data_text}
    
    3. TEMPLATE (Fill in the placeholders like [NAME], [DATE] using the Data):
    {template_text}
    
    OUTPUT:
    Output ONLY the final filled document. Do not include "Here is the document".
    """
    
    return query_ollama(prompt)