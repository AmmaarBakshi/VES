import os

def create_directory_from_text(root_path, tree_text):
    """
    Parses a directory tree text and creates the actual folders/files.
    """
    lines = tree_text.split('\n')
    path_stack = [] # Keeps track of the current path depth
    
    try:
        # Create root if it doesn't exist
        os.makedirs(root_path, exist_ok=True)
        
        for line in lines:
            stripped = line.strip()
            if not stripped or "│" not in line and "├──" not in line and "└──" not in line and "/" not in line:
                continue

            # Calculate depth based on indentation or special chars
            # Simple heuristic: count spaces/tabs or tree markers
            depth = 0
            clean_name = stripped
            
            # Remove tree markers to get the clean name
            for marker in ["├──", "└──", "│", "|--", "`--"]:
                if marker in line:
                    clean_name = line.split(marker)[-1].strip()
                    # Depth estimation: characters before the marker
                    prefix = line.split(marker)[0]
                    depth = len(prefix) // 4 # Standard tree indent is 4 chars
                    break
            
            # Remove comments (anything after #)
            clean_name = clean_name.split('#')[0].strip()
            if not clean_name: continue

            # Adjust stack to current depth
            while len(path_stack) > depth:
                path_stack.pop()
                
            # Construct full path
            current_parent = path_stack[-1] if path_stack else root_path
            full_path = os.path.join(current_parent, clean_name)
            
            # Check if it's a file or directory (Files usually have extensions or no trailing /)
            # User example shows files like 'main.py' and folders like 'app/'
            if "." in clean_name or clean_name == "requirements.txt" or clean_name == ".gitignore":
                # It's a file
                with open(full_path, 'w') as f:
                    f.write("") # Create empty file
            else:
                # It's a directory
                os.makedirs(full_path, exist_ok=True)
                path_stack.append(full_path)
                
        return f"Success! Structure created at {root_path}"
    except Exception as e:
        return f"Error creating structure: {e}"