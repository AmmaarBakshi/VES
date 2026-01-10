from app.ai.llm_client import query_ollama

def smart_fill_content(data_text, template_text, reference_text="None"):
    """
    Merges data into a template using a reference style.
    """
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