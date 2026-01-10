import customtkinter as ctk
from tkinter import filedialog, END
import threading
import os
import time

# --- IMPORTS FROM YOUR PROJECT MODULES ---
from app.utils.config_loader import save_macro, load_macros
from app.engine.directory_maker import create_directory_from_text
from app.engine.word_agent import process_word_document
from app.engine.excel_agent import process_excel_file
from app.engine.ppt_agent import process_ppt_file
from app.engine.pdf_agent import process_pdf_file
from app.engine.smart_fill import smart_fill_content
from app.engine.pdf_maker import create_filled_pdf

# NEW IMPORT: The Advanced Recorder Tab
# (Make sure you created app/gui/recorder_tab.py from the previous step!)
from app.gui.recorder_tab import RecorderTab

# --- UI SETTINGS ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Macro Station")
        self.geometry("1000x800")

        # --- TABS LAYOUT ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=20)

        # Create Tabs
        self.tab_process = self.tab_view.add("Smart Process")
        self.tab_fill = self.tab_view.add("Smart Fill")
        self.tab_recorder = self.tab_view.add("Action Recorder")
        self.tab_dir = self.tab_view.add("Directory Maker")

        # Setup Content for each Tab
        self.setup_process_tab()
        self.setup_fill_tab()
        self.setup_recorder_tab()
        self.setup_dir_tab()

    # ========================================================
    # TAB 1: SMART PROCESS (File Automation)
    # ========================================================
    def setup_process_tab(self):
        frame = self.tab_process
        
        # 1. Header & Macro Selector
        top_frame = ctk.CTkFrame(frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(top_frame, text="Instruction:", font=("Arial", 14, "bold")).pack(side="left")
        
        # Load macros into dropdown
        macro_names = ["Custom"] + list(load_macros().keys())
        self.macro_combo = ctk.CTkComboBox(top_frame, values=macro_names, command=self.load_macro_choice)
        self.macro_combo.pack(side="right", padx=10)
        ctk.CTkLabel(top_frame, text="Load Macro:").pack(side="right")

        # 2. Instruction Input
        self.input_instruction = ctk.CTkEntry(frame, placeholder_text="E.g., 'Summarize this' or 'Format as Invoice'", height=40)
        self.input_instruction.pack(fill="x", pady=5)
        
        # Save Macro Button
        btn_save_macro = ctk.CTkButton(frame, text="Save as Macro", width=100, fg_color="gray", command=self.save_current_macro)
        btn_save_macro.pack(anchor="e", pady=5)

        # 3. File Selection
        self.btn_select = ctk.CTkButton(frame, text="Select File (Docx, Xlsx, PPT, PDF)", command=self.select_file, height=40)
        self.btn_select.pack(fill="x", pady=10)
        
        self.lbl_file = ctk.CTkLabel(frame, text="No file selected", text_color="gray")
        self.lbl_file.pack()

        # 4. Progress Bar
        self.progress = ctk.CTkProgressBar(frame, orientation="horizontal")
        self.progress.set(0)
        self.progress.pack(fill="x", pady=20)
        
        # 5. Run Button
        self.btn_run = ctk.CTkButton(frame, text="▶ RUN ACTION", fg_color="green", height=50, command=self.start_processing)
        self.btn_run.pack(fill="x", pady=10)

        # 6. Result Log
        self.txt_log = ctk.CTkTextbox(frame, height=150)
        self.txt_log.pack(fill="x", pady=10)
        self.txt_log.insert("0.0", "System Ready...\n")

    def select_file(self):
        file_types = [
            ("All Supported", "*.docx;*.xlsx;*.pptx;*.pdf"),
            ("Word", "*.docx"), ("Excel", "*.xlsx"), 
            ("PowerPoint", "*.pptx"), ("PDF", "*.pdf")
        ]
        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.selected_file = path
            self.lbl_file.configure(text=f"Selected: {os.path.basename(path)}")
            self.log(f"Selected: {path}")

    def start_processing(self):
        if not hasattr(self, 'selected_file'):
            self.log("Please select a file first.")
            return

        instruction = self.input_instruction.get()
        self.progress.start() # Makes the bar pulse
        self.btn_run.configure(state="disabled")
        
        # Run inside a thread to keep GUI responsive
        threading.Thread(target=self.run_ai_logic, args=(self.selected_file, instruction)).start()

    def run_ai_logic(self, path, instruction):
        self.log(f"Processing {os.path.basename(path)}...")
        result = None
        
        try:
            if path.endswith(".docx"):
                result = process_word_document(path, instruction)
            elif path.endswith(".xlsx"):
                result = process_excel_file(path, instruction)
            elif path.endswith(".pptx"):
                result = process_ppt_file(path, instruction)
            elif path.endswith(".pdf"):
                result = process_pdf_file(path, instruction)
            else:
                result = "Error: Unsupported file type."
        except Exception as e:
            result = f"Critical Error: {e}"

        self.after(0, lambda: self.finish_processing(result))

    def finish_processing(self, result):
        self.progress.stop()
        self.progress.set(1) # Full bar
        self.btn_run.configure(state="normal")
        
        if result and "Error" not in result:
            self.log(f"✅ Success! Saved to: {result}")
            # Optional: Open the folder
            # os.startfile(os.path.dirname(result)) 
        else:
            self.log(f"❌ {result}")

    def log(self, msg):
        self.txt_log.insert(END, f"{msg}\n")
        self.txt_log.see(END)

    # --- MACRO SAVING LOGIC ---
    def save_current_macro(self):
        dialog = ctk.CTkInputDialog(text="Name this Macro:", title="Save Macro")
        name = dialog.get_input()
        instruction = self.input_instruction.get()
        if name and instruction:
            save_macro(name, instruction)
            # Refresh list
            new_values = ["Custom"] + list(load_macros().keys())
            self.macro_combo.configure(values=new_values)
            self.log(f"Macro '{name}' saved!")

    def load_macro_choice(self, choice):
        macros = load_macros()
        if choice in macros:
            self.input_instruction.delete(0, END)
            self.input_instruction.insert(0, macros[choice])

    # ========================================================
    # TAB 2: SMART FILL (Data + Template -> PDF)
    # ========================================================
    def setup_fill_tab(self):
        frame = self.tab_fill
        
        # 1. Data Input
        ctk.CTkLabel(frame, text="1. Paste Data (JSON, CSV, or messy notes):").pack(anchor="w", padx=10)
        self.txt_data = ctk.CTkTextbox(frame, height=100)
        self.txt_data.pack(fill="x", padx=10, pady=5)
        
        # 2. Template Input
        ctk.CTkLabel(frame, text="2. Paste Template (with placeholders like [NAME]):").pack(anchor="w", padx=10)
        self.txt_template = ctk.CTkTextbox(frame, height=100)
        self.txt_template.pack(fill="x", padx=10, pady=5)
        
        # 3. Reference Input (Optional)
        ctk.CTkLabel(frame, text="3. Paste Reference Style (Optional - e.g. 'Formal Letter'):").pack(anchor="w", padx=10)
        self.txt_ref = ctk.CTkEntry(frame, placeholder_text="E.g., generic professional tone")
        self.txt_ref.pack(fill="x", padx=10, pady=5)
        
        # 4. Generate Button
        self.btn_fill = ctk.CTkButton(frame, text="Generate Filled Document", fg_color="purple", command=self.run_smart_fill)
        self.btn_fill.pack(pady=15)
        
        # 5. Output Area
        ctk.CTkLabel(frame, text="Result:").pack(anchor="w", padx=10)
        self.txt_fill_result = ctk.CTkTextbox(frame, height=150)
        self.txt_fill_result.pack(fill="both", expand=True, padx=10, pady=10)

    def run_smart_fill(self):
        data = self.txt_data.get("0.0", END).strip()
        template = self.txt_template.get("0.0", END).strip()
        ref = self.txt_ref.get().strip()
        
        if not data or not template:
            self.txt_fill_result.insert(END, "❌ Error: Please provide Data and Template.\n")
            return

        self.btn_fill.configure(state="disabled", text="Generating...")
        
        # Run in thread
        threading.Thread(target=self.thread_smart_fill, args=(data, template, ref)).start()

    def thread_smart_fill(self, data, template, ref):
        # 1. Get Text from AI
        ai_text = smart_fill_content(data, template, ref)
        
        # 2. Generate PDF using our new module
        filename = f"Generated_Doc_{int(time.time())}.pdf"
        output_path = os.path.join("user_data", filename)
        
        # Ensure user_data exists
        os.makedirs("user_data", exist_ok=True)
        
        final_path = create_filled_pdf(ai_text, output_path)
        
        self.after(0, lambda: self.finish_smart_fill(ai_text, final_path))

    def finish_smart_fill(self, text_result, pdf_path):
        self.txt_fill_result.delete("0.0", END)
        self.txt_fill_result.insert("0.0", text_result)
        self.btn_fill.configure(state="normal", text="Generate Filled Document")
        
        # Show PDF Success link
        if "Error" not in pdf_path:
            # Add a button or label to show success
            ctk.CTkLabel(self.tab_fill, text=f"✅ PDF Saved: {pdf_path}", text_color="green").pack()
            try:
                os.startfile(pdf_path) # Auto-open PDF on Windows
            except:
                pass

    # ========================================================
    # TAB 3: ACTION RECORDER (ADVANCED INTEGRATION)
    # ========================================================
    def setup_recorder_tab(self):
        """
        Embeds the advanced RecorderTab we created separately.
        """
        # We simply create the RecorderTab class and attach it to this tab's frame.
        self.recorder_ui = RecorderTab(self.tab_recorder)
        self.recorder_ui.pack(fill="both", expand=True)

    # ========================================================
    # TAB 4: DIRECTORY MAKER (Text -> Folders)
    # ========================================================
    def setup_dir_tab(self):
        frame = self.tab_dir
        
        ctk.CTkLabel(frame, text="Paste Directory Tree Structure:", font=("Arial", 14, "bold")).pack(pady=5)
        
        self.txt_tree = ctk.CTkTextbox(frame, height=300, font=("Courier", 12))
        self.txt_tree.pack(fill="x", pady=10)
        
        self.btn_select_dir = ctk.CTkButton(frame, text="Select Target Folder", command=self.select_target_dir)
        self.btn_select_dir.pack(pady=5)
        
        self.lbl_target = ctk.CTkLabel(frame, text="Target: Current Folder")
        self.lbl_target.pack()
        
        self.btn_create_tree = ctk.CTkButton(frame, text="Generate Directory Structure", fg_color="orange", command=self.generate_tree)
        self.btn_create_tree.pack(pady=20)

    def select_target_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.target_dir = path
            self.lbl_target.configure(text=f"Target: {path}")

    def generate_tree(self):
        text = self.txt_tree.get("0.0", END)
        target = getattr(self, 'target_dir', os.getcwd())
        
        msg = create_directory_from_text(target, text)
        
        # Show result in a popup
        popup = ctk.CTkToplevel(self)
        popup.geometry("400x150")
        popup.title("Result")
        ctk.CTkLabel(popup, text=msg, wraplength=380).pack(pady=20)
        ctk.CTkButton(popup, text="OK", command=popup.destroy).pack()