import os
import threading
import re
import time
from langchain_ollama import OllamaLLM

class SmartScaffolder:
    def __init__(self):
        self.llm = OllamaLLM(model="llama3", temperature=0.4)

    def identify_context(self, tree_text):
        try:
            prompt = (
                f"Analyze this directory structure:\n{tree_text}\n\n"
                "Identify the programming language or framework (e.g., Python Flask, React, Data Science).\n"
                "Return ONLY the name of the tech stack."
            )
            return self.llm.invoke(prompt).strip()
        except:
            return "General Code"

    def generate_content(self, filename, tree_text, context):
        try:
            if any(ext in filename for ext in ['.png', '.jpg', '.pyc', '.exe']):
                return ""

            if filename.lower() == "readme.md":
                prompt = (
                    f"Write a professional README.md for a {context} project.\n"
                    f"Structure:\n{tree_text}\n\n"
                    "Include Title, Description, and Run Instructions. Return Markdown only."
                )
            elif filename == "requirements.txt":
                prompt = f"List standard {context} libraries for this structure. Return list only."
            elif filename == ".gitignore":
                prompt = f"Standard .gitignore for {context}. Return content only."
            else:
                prompt = (
                    f"Write professional starter code for '{filename}' in a {context} project.\n"
                    f"Structure:\n{tree_text}\n"
                    "Return ONLY the code. No markdown formatting."
                )
            
            response = self.llm.invoke(prompt)
            return re.sub(r'^```[a-zA-Z]*\n|```$', '', response.strip(), flags=re.MULTILINE)

        except Exception as e:
            return f"# Error: {e}"

# Init Engine
scaffolder = SmartScaffolder()

def create_directory_from_text(root_path, tree_text, update_callback=None):
    """
    Robust parser with REAL-TIME UI UPDATES.
    """
    lines = tree_text.split('\n')
    path_stack = [(-1, root_path)]
    
    def run_scaffold():
        try:
            # 1. Notify Start
            if update_callback: update_callback("start", "🚀 Analyzing structure...")
            os.makedirs(root_path, exist_ok=True)
            
            # 2. Detect Context
            project_context = scaffolder.identify_context(tree_text)
            if update_callback: update_callback("running", f"💡 Detected Stack: {project_context}")
            time.sleep(1) # Small pause so user sees the text

            # 3. Build Loop
            for line in lines:
                if not line.strip(): continue
                
                # Indent Calculation
                raw_indent = 0
                for char in line:
                    if char in [' ', '│', '|']: raw_indent += 1
                    elif char == '\t': raw_indent += 4
                    else: break
                
                # Name Cleanup
                clean_name = line.strip()
                clean_name = re.sub(r'^[\│\|\+\`\s]*[\-\—]+\s*', '', clean_name)
                clean_name = clean_name.split('#')[0].strip().replace("/", "")
                
                if not clean_name: continue

                # Stack Management
                while len(path_stack) > 1 and path_stack[-1][0] >= raw_indent:
                    path_stack.pop()

                current_parent = path_stack[-1][1]
                full_path = os.path.join(current_parent, clean_name)

                # File vs Folder Logic
                is_file = "." in clean_name and not clean_name.startswith("docker") 
                
                if is_file:
                    # UPDATE UI: Show exactly what file is being written
                    if update_callback: update_callback("running", f"📝 Writing code for {clean_name}...")
                    
                    content = scaffolder.generate_content(clean_name, tree_text, project_context)
                    try:
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                    except: pass
                else:
                    if update_callback: update_callback("running", f"📂 Creating folder {clean_name}...")
                    os.makedirs(full_path, exist_ok=True)
                    path_stack.append((raw_indent, full_path))

            # 4. Notify Finish
            if update_callback: update_callback("done", f"✅ Success! Project built at {root_path}")
            
        except Exception as e:
            if update_callback: update_callback("error", f"❌ Error: {e}")

    # Run in background
    threading.Thread(target=run_scaffold, daemon=True).start()