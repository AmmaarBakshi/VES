import os
import threading
import re
import time
from langchain_ollama import OllamaLLM
from app.utils.config_loader import load_ai_config
from app.engine.cot_engine import stream_cot_plan, make_dir_plan_prompt

class SmartScaffolder:
    def __init__(self):
        config = load_ai_config()
        model_name = config.get("active_model", "llama3.2")
        self.llm = OllamaLLM(model=model_name, temperature=0.4)

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

    # Binary / generated file extensions that should not have content generated
    BINARY_EXTENSIONS = [
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg',
        '.pyc', '.pyo', '.exe', '.dll', '.so',
        '.zip', '.gz', '.tar', '.rar', '.7z',
        '.db', '.sqlite', '.sqlite3',
        '.ico', '.cur',
        '.woff', '.woff2', '.ttf', '.otf', '.eot',
        '.mp4', '.mp3', '.wav', '.avi', '.mkv',
        '.pdf',
    ]

    def generate_content(self, filename, tree_text, context):
        try:
            if any(filename.lower().endswith(ext) for ext in self.BINARY_EXTENSIONS):
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
            elif filename == ".env":
                prompt = f"Standard .env template for a {context} project. Return key=value pairs only. No real secrets."
            else:
                prompt = (
                    f"Write professional starter code for '{filename}' in a {context} project.\n"
                    f"Structure:\n{tree_text}\n"
                    "Return ONLY the code. No markdown formatting."
                )
            
            response = self.llm.invoke(prompt)
            return re.sub(r'^```[a-zA-Z]*\n|```$', '', response.strip(), flags=re.MULTILINE)

        except Exception as e:
            return f"# Error generating content: {e}"


def _is_file_entry(name: str) -> bool:
    """
    Robustly decide if a tree entry is a file.
    Handles hidden-dot files (.env, .gitignore, .htaccess) and 
    avoids misclassifying Dockerfile, docker-compose.yml, etc.
    """
    # Explicit dotfiles (hidden files starting with '.' — no extension after dot)
    if name.startswith('.') and name.count('.') == 1:
        return True  # .env, .gitignore, .htaccess etc.

    # Has a real extension (and doesn't start with 'docker' without dot)
    if '.' in name and not name.startswith('docker'):
        return True

    # docker-compose.yml etc. should still be treated as files
    if '.' in name:
        return True

    return False


def parse_tree_to_list(tree_text: str) -> list[dict]:
    """
    Parse a tree text into a flat list of dicts:
      [{'name': str, 'type': 'file'|'folder', 'depth': int}, ...]
    Used for the Preview panel before building.
    Handles both ASCII (+-- \\--) and Unicode (├── └──) tree styles.
    """
    # Unicode box-drawing chars used in tree diagrams
    _BOX = '\u2502\u251c\u2514\u2500\u252c\u2524'  # │ ├ └ ─ ┬ ┤

    entries = []
    for line in tree_text.split('\n'):
        if not line.strip():
            continue

        # Indent calculation — count leading whitespace, │, | chars
        raw_indent = 0
        for char in line:
            if char in (' ', '|', '\u2502'):  # space, pipe, │
                raw_indent += 1
            elif char == '\t':
                raw_indent += 4
            elif char in _BOX:                 # box-drawing chars count as 1
                raw_indent += 1
            else:
                break

        clean_name = line.strip()
        # Strip leading box-drawing / ASCII tree prefix characters
        # Handles: ├── └── +-- \-- |-- and combinations thereof
        clean_name = re.sub(
            r'^[\u2502\u251c\u2514\u2500\u252c\u2524\|\+\`\\\s]*'
            r'[\u2500\-\u2014]+\s*',
            '',
            clean_name
        )
        clean_name = clean_name.split('#')[0].strip().replace('/', '')

        if not clean_name:
            continue

        entry_type = "file" if _is_file_entry(clean_name) else "folder"
        entries.append({
            'name': clean_name,
            'type': entry_type,
            'depth': raw_indent,
        })

    return entries


# Init Engine (module-level singleton)
scaffolder = SmartScaffolder()


def create_directory_from_text(root_path, tree_text, update_callback=None, thought_callback=None):
    """
    Robust parser with REAL-TIME UI UPDATES and Agentic Chain-of-Thought streaming.

    Args:
        root_path:        Absolute path where the project will be created.
        tree_text:        The directory tree text (e.g. copied from an AI response).
        update_callback:  callable(status: str, msg: str) — 'start'|'running'|'done'|'error'
        thought_callback: callable(str) — called token-by-token with CoT reasoning text.
    
    Returns:
        The root_path string (so the caller can open it in Explorer etc.)
    """
    lines = tree_text.split('\n')

    def run_scaffold():
        # path_stack lives INSIDE the thread to prevent shared-state corruption
        # if the function is called twice in quick succession.
        path_stack = [(-1, root_path)]
        failed_files = []
        # Track sibling names per parent to detect duplicates
        #   key = parent_path, value = set of child names already seen
        seen_names: dict[str, set] = {}

        try:
            # 1. Notify Start
            if update_callback:
                update_callback("start", "🚀 Analysing structure...")
            os.makedirs(root_path, exist_ok=True)

            # 2. Detect Context
            project_context = scaffolder.identify_context(tree_text)
            if update_callback:
                update_callback("running", f"💡 Detected Stack: {project_context}")

            # 3. ── Agentic CoT: Stream the plan before doing any work ──
            if thought_callback:
                thought_callback(f"◆ Stack detected: {project_context}\n\n")
                plan_prompt = make_dir_plan_prompt(tree_text, project_context)
                stream_cot_plan(scaffolder.llm, plan_prompt, thought_callback)
                thought_callback("\n\n─── Executing Plan ───\n\n")

            time.sleep(0.3)

            # 4. Build Loop
            for line in lines:
                if not line.strip():
                    continue

                # Indent Calculation
                raw_indent = 0
                _BOX = '\u2502\u251c\u2514\u2500\u252c\u2524'
                for char in line:
                    if char in (' ', '|', '\u2502'):
                        raw_indent += 1
                    elif char == '\t':
                        raw_indent += 4
                    elif char in _BOX:
                        raw_indent += 1
                    else:
                        break

                # Name Cleanup — strip ASCII and Unicode tree prefixes
                clean_name = line.strip()
                clean_name = re.sub(
                    r'^[\u2502\u251c\u2514\u2500\u252c\u2524\|\+\`\\\s]*'
                    r'[\u2500\-\u2014]+\s*',
                    '',
                    clean_name
                )
                clean_name = clean_name.split('#')[0].strip().replace('/', '')

                if not clean_name:
                    continue

                # Stack Management
                while len(path_stack) > 1 and path_stack[-1][0] >= raw_indent:
                    path_stack.pop()

                current_parent = path_stack[-1][1]
                full_path = os.path.join(current_parent, clean_name)

                # ── Duplicate sibling detection ──
                siblings = seen_names.setdefault(current_parent, set())
                if clean_name in siblings:
                    if thought_callback:
                        thought_callback(
                            f"  ⚠️  Duplicate name '{clean_name}' under '{os.path.basename(current_parent)}' — skipping.\n"
                        )
                    continue
                siblings.add(clean_name)

                # File vs Folder Logic (fixed to handle .env, .gitignore etc.)
                if _is_file_entry(clean_name):
                    if update_callback:
                        update_callback("running", f"📝 Writing code for {clean_name}...")
                    content = scaffolder.generate_content(clean_name, tree_text, project_context)
                    try:
                        with open(full_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        if thought_callback:
                            thought_callback(f"  ✔ Created file: {clean_name}\n")
                    except Exception as e:
                        failed_files.append((clean_name, str(e)))
                        if thought_callback:
                            thought_callback(f"  ✘ Failed to write {clean_name}: {e}\n")
                else:
                    if update_callback:
                        update_callback("running", f"📂 Creating folder {clean_name}...")
                    os.makedirs(full_path, exist_ok=True)
                    path_stack.append((raw_indent, full_path))
                    if thought_callback:
                        thought_callback(f"  📁 Folder: {clean_name}\n")

            # 5. Summary
            if failed_files and thought_callback:
                thought_callback(f"\n⚠️  {len(failed_files)} file(s) could not be written:\n")
                for name, err in failed_files:
                    thought_callback(f"   • {name}: {err}\n")

            if update_callback:
                update_callback("done", f"✅ Project built at {root_path}")

        except Exception as e:
            if update_callback:
                update_callback("error", f"❌ Error: {e}")

    # Run in background
    threading.Thread(target=run_scaffold, daemon=True).start()
    return root_path