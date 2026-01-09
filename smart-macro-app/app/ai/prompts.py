SYSTEM_PROMPT = """
You are a highly efficient text processing assistant. 
Your goal is to improve, format, or summarize text based on the user's specific instruction.
Do NOT add conversational filler like "Here is the text." Just output the result.
"""

def get_prompt(instruction, content):
    """
    Helper to create a consistent prompt format.
    """
    return f"Instruction: {instruction}\n\nContent to Process:\n{content}"