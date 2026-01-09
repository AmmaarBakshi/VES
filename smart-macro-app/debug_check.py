import os
import sys

# List of critical files and the functions we need inside them
required_files = {
    "app/ai/prompts.py": "get_prompt",
    "app/gui/components.py": "StatusLabel",
    "app/utils/logger.py": "log_event",
    "app/engine/excel_agent.py": "process_excel_file",
    "app/engine/word_agent.py": "process_word_document",
    "app/engine/ppt_agent.py": "process_ppt_file",
    "app/engine/pdf_agent.py": "process_pdf_file",
}

print("--- DIAGNOSTIC CHECK ---")
all_good = True

for path, func_name in required_files.items():
    if not os.path.exists(path):
        print(f"❌ MISSING FILE: {path}")
        all_good = False
    else:
        # Check if file is empty
        if os.path.getsize(path) == 0:
            print(f"❌ EMPTY FILE: {path} (You need to paste the code into this!)")
            all_good = False
        else:
            # Check for the function name inside the text (simple check)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if f"def {func_name}" not in content and f"class {func_name}" not in content:
                    print(f"❌ MISSING CODE: {path} does not contain '{func_name}'")
                    all_good = False
                else:
                    print(f"✅ OK: {path}")

if all_good:
    print("\nAll files look correct! Try running 'python main.py' again.")
else:
    print("\n⚠️ Fix the files marked with ❌ above.")