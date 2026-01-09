import pandas as pd
import os
from app.ai.llm_client import query_ollama
from app.ai.prompts import get_prompt

def process_excel_file(file_path, instruction):
    """
    Reads an Excel file, applies AI to the first column, and saves the result.
    """
    try:
        print(f"Reading Excel: {file_path}")
        df = pd.read_excel(file_path)
        
        # Default to first column
        col_name = df.columns[0]
        
        results = []
        for val in df[col_name]:
            if pd.isna(val) or str(val).strip() == "":
                results.append("")
                continue
            
            # Use the helper to format the prompt
            prompt = get_prompt(instruction, str(val))
            resp = query_ollama(prompt)
            results.append(resp)

        df['AI_Output'] = results
        
        base_name = os.path.basename(file_path)
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, f"PROCESSED_{base_name}")
        
        df.to_excel(new_path, index=False)
        return new_path
    except Exception as e:
        print(f"Excel Error: {e}")
        return f"Error: {e}"