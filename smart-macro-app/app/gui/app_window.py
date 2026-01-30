import customtkinter as ctk
from tkinter import filedialog, END
import threading
import os
import time

# --- IMPORTS FROM YOUR PROJECT MODULES ---
from app.utils.config_loader import save_macro, load_macros
from app.utils.ollama_manager import get_ollama_manager
from app.engine.directory_maker import create_directory_from_text
from app.engine.word_agent import process_word_document
from app.engine.excel_agent import process_excel_file
from app.engine.smart_fill import smart_fill_content
from app.engine.pdf_maker import create_filled_pdf

# --- NEW IMPORTS FOR PPT & PDF AGENTS ---
from app.engine.ppt_agent import PPTGenerator, PPTEnricher
from app.engine.pdf_agent import PDFAgent
from app.engine.excel_agent import enrich_excel_file, suggest_excel_improvements
from app.engine.word_agent import enrich_word_document, suggest_word_improvements

# --- IMPORT: The Advanced Recorder Tab ---
from app.gui.recorder_tab import RecorderTab

# --- UI SETTINGS ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Macro Station")
        self.geometry("1100x850")
        
        # --- OLLAMA STATUS INDICATOR ---
        self.status_frame = ctk.CTkFrame(self, height=30)
        self.status_frame.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(self.status_frame, text="Ollama Status:", font=("Arial", 11)).pack(side="left", padx=10)
        self.ollama_status_label = ctk.CTkLabel(self.status_frame, text="● Checking...", text_color="orange", font=("Arial", 11, "bold"))
        self.ollama_status_label.pack(side="left")
        
        # Check Ollama status
        self.check_ollama_status()

        # --- TABS LAYOUT ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(fill="both", expand=True, padx=20, pady=20)

        # Create Tabs
        self.tab_process = self.tab_view.add("Smart Process")
        self.tab_ppt = self.tab_view.add("PPT Maker")        # <--- NEW TAB
        self.tab_pdf = self.tab_view.add("Smart PDF Writer") # <--- NEW TAB
        self.tab_enhance = self.tab_view.add("AI Enhance")   # <--- AI ENRICHMENT TAB
        self.tab_fill = self.tab_view.add("Smart Fill")
        self.tab_recorder = self.tab_view.add("Action Recorder")
        self.tab_dir = self.tab_view.add("Directory Maker")

       # Initialize New Engines
        self.ppt_engine = PPTGenerator()
        self.ppt_enricher = PPTEnricher()
        self.pdf_engine = PDFAgent()

        # Setup Content for each Tab
        self.setup_process_tab()
        self.setup_ppt_ui()         # <--- NEW SETUP
        self.setup_pdf_ui()         # <--- NEW SETUP
        self.setup_enhance_tab()    # <--- AI ENHANCE SETUP
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
            # Note: process_ppt_file might need to be imported if you have a separate one for 'editing' vs 'creating'
            # elif path.endswith(".pptx"):
            #    result = process_ppt_file(path, instruction)
            else:
                result = "Error: Unsupported file type for this tab."
        except Exception as e:
            result = f"Critical Error: {e}"

        self.after(0, lambda: self.finish_processing(result))

    def finish_processing(self, result):
        self.progress.stop()
        self.progress.set(1) # Full bar
        self.btn_run.configure(state="normal")
        
        if result and "Error" not in result:
            self.log(f"✅ Success! Saved to: {result}")
        else:
            self.log(f"❌ {result}")

    def log(self, msg):
        self.txt_log.insert(END, f"{msg}\n")
        self.txt_log.see(END)

    def save_current_macro(self):
        dialog = ctk.CTkInputDialog(text="Name this Macro:", title="Save Macro")
        name = dialog.get_input()
        instruction = self.input_instruction.get()
        if name and instruction:
            save_macro(name, instruction)
            new_values = ["Custom"] + list(load_macros().keys())
            self.macro_combo.configure(values=new_values)
            self.log(f"Macro '{name}' saved!")

    def load_macro_choice(self, choice):
        macros = load_macros()
        if choice in macros:
            self.input_instruction.delete(0, END)
            self.input_instruction.insert(0, macros[choice])

    # ========================================================
    # TAB 2: PPT MAKER (NEW)
    # ========================================================
    def setup_ppt_ui(self):
        # 1. Input Section
        self.ppt_topic_label = ctk.CTkLabel(self.tab_ppt, text="Enter Presentation Topic:", font=("Arial", 16))
        self.ppt_topic_label.pack(pady=10)

        self.ppt_topic_entry = ctk.CTkEntry(self.tab_ppt, width=400, placeholder_text="e.g., The Future of AI in Education")
        self.ppt_topic_entry.pack(pady=5)

        self.ppt_generate_btn = ctk.CTkButton(self.tab_ppt, text="Generate PPT", command=self.start_ppt_generation)
        self.ppt_generate_btn.pack(pady=20)

        # 2. Progress Section (Checklist)
        self.ppt_steps_frame = ctk.CTkFrame(self.tab_ppt)
        self.ppt_steps_frame.pack(pady=10, fill="x", padx=50)

        # Labels
        self.ppt_step_labels = {
            "step_1": self.create_step_label(self.ppt_steps_frame, "1. AI Researching Content..."),
            "step_2": self.create_step_label(self.ppt_steps_frame, "2. Structuring Slides..."),
            "step_3": self.create_step_label(self.ppt_steps_frame, "3. Creating PowerPoint File..."),
        }
        
        self.ppt_status_label = ctk.CTkLabel(self.tab_ppt, text="", text_color="green")
        self.ppt_status_label.pack(pady=10)

    def start_ppt_generation(self):
        topic = self.ppt_topic_entry.get()
        if not topic: return
        
        self.ppt_status_label.configure(text="Starting...")
        self.ppt_generate_btn.configure(state="disabled")
        for key, lbl in self.ppt_step_labels.items():
            lbl.configure(text_color="gray", text=lbl.cget("text").replace("🟢", "⚪").replace("🔵", "⚪"))

        if self.ppt_engine:
            self.ppt_engine.generate_ppt(topic, self.handle_ppt_progress)
        else:
            self.ppt_status_label.configure(text="Error: PPT Engine not loaded", text_color="red")

    def handle_ppt_progress(self, step_key, status):
        self.after(0, lambda: self._update_ppt_gui_safe(step_key, status))

    def _update_ppt_gui_safe(self, step_key, status):
        if step_key == "final":
            self.ppt_status_label.configure(text=f"Success! {status}")
            self.ppt_generate_btn.configure(state="normal")
            return
        if step_key == "error":
            self.ppt_status_label.configure(text=f"Error: {status}", text_color="red")
            self.ppt_generate_btn.configure(state="normal")
            return

        if step_key in self.ppt_step_labels:
            lbl = self.ppt_step_labels[step_key]
            current_text = lbl.cget("text").replace("⚪", "").replace("🟢", "").replace("🔵", "").strip()
            if status == "running":
                lbl.configure(text=f"🔵 {current_text}", text_color="#3B8ED0")
            elif status == "done":
                lbl.configure(text=f"🟢 {current_text}", text_color="green")

    # ========================================================
    # TAB 3: SMART PDF WRITER (NEW)
    # ========================================================
    def setup_pdf_ui(self):
        # 1. Input Section
        label = ctk.CTkLabel(self.tab_pdf, text="What should the document be about?", font=("Arial", 16))
        label.pack(pady=10)

        self.pdf_topic_entry = ctk.CTkEntry(self.tab_pdf, width=400, placeholder_text="e.g., Essay on Mars Exploration")
        self.pdf_topic_entry.pack(pady=5)

        self.pdf_btn = ctk.CTkButton(self.tab_pdf, text="Write & Save PDF", command=self.start_pdf_generation, fg_color="#D9534F", hover_color="#C9302C")
        self.pdf_btn.pack(pady=20)

        # 2. Progress Checklist
        self.pdf_steps_frame = ctk.CTkFrame(self.tab_pdf)
        self.pdf_steps_frame.pack(pady=10, fill="x", padx=50)

        self.pdf_step_labels = {
            "step_1": self.create_step_label(self.pdf_steps_frame, "1. AI Writing Content..."),
            "step_2": self.create_step_label(self.pdf_steps_frame, "2. Formatting & Saving PDF..."),
        }
        
        self.pdf_status_label = ctk.CTkLabel(self.tab_pdf, text="", text_color="green")
        self.pdf_status_label.pack(pady=10)

    def start_pdf_generation(self):
        topic = self.pdf_topic_entry.get()
        if not topic: return

        self.pdf_status_label.configure(text="Processing...")
        self.pdf_btn.configure(state="disabled")
        for key, lbl in self.pdf_step_labels.items():
            lbl.configure(text_color="gray", text=lbl.cget("text").replace("🟢", "⚪").replace("🔵", "⚪"))

        if self.pdf_engine:
            self.pdf_engine.generate_smart_pdf(topic, self.handle_pdf_progress)
        else:
             self.pdf_status_label.configure(text="Error: PDF Engine not loaded", text_color="red")

    def handle_pdf_progress(self, step_key, status):
        self.after(0, lambda: self._update_pdf_gui_safe(step_key, status))

    def _update_pdf_gui_safe(self, step_key, status):
        if step_key == "final":
            self.pdf_status_label.configure(text=f"Success! {status}")
            self.pdf_btn.configure(state="normal")
            return
        if step_key == "error":
            self.pdf_status_label.configure(text=f"Error: {status}", text_color="red")
            self.pdf_btn.configure(state="normal")
            return

        if step_key in self.pdf_step_labels:
            lbl = self.pdf_step_labels[step_key]
            txt = lbl.cget("text").replace("⚪", "").replace("🟢", "").replace("🔵", "").strip()
            if status == "running":
                lbl.configure(text=f"🔵 {txt}", text_color="#3B8ED0")
            elif status == "done":
                lbl.configure(text=f"🟢 {txt}", text_color="green")

    # Helper for creating checklist labels
    def create_step_label(self, parent, text):
        lbl = ctk.CTkLabel(parent, text=f"⚪ {text}", text_color="gray")
        lbl.pack(anchor="w", padx=20, pady=5)
        return lbl

    # ========================================================
    # TAB 4: AI ENHANCE (Content Enrichment)
    # ========================================================
    def setup_enhance_tab(self):
        frame = self.tab_enhance
        
        # Title
        title_label = ctk.CTkLabel(frame, text="AI-Powered Content Enrichment", font=("Arial", 20, "bold"))
        title_label.pack(pady=10)
        
        # File Selection
        file_frame = ctk.CTkFrame(frame)
        file_frame.pack(fill="x", padx=20, pady=10)
        
        self.enhance_btn_select = ctk.CTkButton(file_frame, text="Select File to Enhance", command=self.select_enhance_file, height=40)
        self.enhance_btn_select.pack(fill="x", pady=5)
        
        self.enhance_lbl_file = ctk.CTkLabel(file_frame, text="No file selected", text_color="gray")
        self.enhance_lbl_file.pack(pady=5)
        
        # Enhancement Options
        options_frame = ctk.CTkFrame(frame)
        options_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(options_frame, text="Enhancement Options:", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Checkboxes for options
        self.enhance_improve_text = ctk.CTkCheckBox(options_frame, text="Improve Text Quality (Grammar, Clarity, Style)")
        self.enhance_improve_text.pack(anchor="w", padx=20, pady=3)
        self.enhance_improve_text.select()
        
        self.enhance_auto_format = ctk.CTkCheckBox(options_frame, text="Auto-Format (Fonts, Spacing, Alignment)")
        self.enhance_auto_format.pack(anchor="w", padx=20, pady=3)
        
        self.enhance_add_summaries = ctk.CTkCheckBox(options_frame, text="Add Summaries")
        self.enhance_add_summaries.pack(anchor="w", padx=20, pady=3)
        
        self.enhance_fix_consistency = ctk.CTkCheckBox(options_frame, text="Fix Style Consistency")
        self.enhance_fix_consistency.pack(anchor="w", padx=20, pady=3)
        
        # Style Settings
        style_frame = ctk.CTkFrame(frame)
        style_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(style_frame, text="Style:", font=("Arial", 12)).pack(side="left", padx=10)
        self.enhance_style = ctk.CTkComboBox(style_frame, values=["Professional", "Casual", "Academic", "Technical"])
        self.enhance_style.set("Professional")
        self.enhance_style.pack(side="left", padx=10)
        
        # Action Buttons
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        self.enhance_btn_preview = ctk.CTkButton(btn_frame, text="Get Suggestions", command=self.preview_enhancements, fg_color="#5B9BD5")
        self.enhance_btn_preview.pack(side="left", padx=5, expand=True, fill="x")
        
        self.enhance_btn_apply = ctk.CTkButton(btn_frame, text="Apply Enhancements", command=self.apply_enhancements, fg_color="#70AD47", height=40)
        self.enhance_btn_apply.pack(side="left", padx=5, expand=True, fill="x")
        
        # Progress Section
        progress_frame = ctk.CTkFrame(frame)
        progress_frame.pack(fill="x", padx=20, pady=10)
        
        self.enhance_progress = ctk.CTkProgressBar(progress_frame)
        self.enhance_progress.set(0)
        self.enhance_progress.pack(fill="x", pady=5)
        
        self.enhance_status = ctk.CTkLabel(progress_frame, text="Ready", text_color="gray")
        self.enhance_status.pack(pady=5)
        
        # Results Log
        ctk.CTkLabel(frame, text="Results:", font=("Arial", 12, "bold")).pack(anchor="w", padx=20)
        self.enhance_log = ctk.CTkTextbox(frame, height=150)
        self.enhance_log.pack(fill="both", expand=True, padx=20, pady=10)
        self.enhance_log.insert("0.0", "Select a file and choose enhancement options to begin...\n")
    
    def select_enhance_file(self):
        file_types = [
            ("Supported Files", "*.docx;*.xlsx;*.pptx"),
            ("Word", "*.docx"),
            ("Excel", "*.xlsx"),
            ("PowerPoint", "*.pptx")
        ]
        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.enhance_selected_file = path
            self.enhance_lbl_file.configure(text=f"Selected: {os.path.basename(path)}")
            self.enhance_log.insert(END, f"\n📁 Selected: {path}\n")
            self.enhance_log.see(END)
    
    def preview_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'):
            self.enhance_log.insert(END, "❌ Please select a file first.\n")
            self.enhance_log.see(END)
            return
        
        self.enhance_log.insert(END, "\n🔍 Analyzing file...\n")
        self.enhance_log.see(END)
        self.enhance_btn_preview.configure(state="disabled")
        
        threading.Thread(target=self.thread_preview_enhancements, daemon=True).start()
    
    def thread_preview_enhancements(self):
        path = self.enhance_selected_file
        suggestions = []
        
        try:
            if path.endswith(".docx"):
                suggestions = suggest_word_improvements(path)
            elif path.endswith(".xlsx"):
                suggestions = suggest_excel_improvements(path)
            elif path.endswith(".pptx"):
                suggestions = self.ppt_enricher.get_improvement_suggestions(path)
            else:
                suggestions = ["Unsupported file type"]
        except Exception as e:
            suggestions = [f"Error: {e}"]
        
        self.after(0, lambda: self.display_suggestions(suggestions))
    
    def display_suggestions(self, suggestions):
        self.enhance_log.insert(END, "\n" + "="*50 + "\n")
        for suggestion in suggestions:
            self.enhance_log.insert(END, f"{suggestion}\n")
        self.enhance_log.insert(END, "="*50 + "\n")
        self.enhance_log.see(END)
        self.enhance_btn_preview.configure(state="normal")
    
    def apply_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'):
            self.enhance_log.insert(END, "❌ Please select a file first.\n")
            self.enhance_log.see(END)
            return
        
        # Gather options
        options = {
            'improve_text': self.enhance_improve_text.get() == 1,
            'auto_format': self.enhance_auto_format.get() == 1,
            'add_summaries': self.enhance_add_summaries.get() == 1,
            'fix_consistency': self.enhance_fix_consistency.get() == 1,
            'improve_content': self.enhance_improve_text.get() == 1,  # For Excel
            'improve_paragraphs': self.enhance_improve_text.get() == 1  # For Word
        }
        
        style = self.enhance_style.get().lower()
        
        self.enhance_log.insert(END, "\n🚀 Starting enhancement process...\n")
        self.enhance_log.see(END)
        self.enhance_btn_apply.configure(state="disabled")
        self.enhance_progress.start()
        
        threading.Thread(target=self.thread_apply_enhancements, args=(options, style), daemon=True).start()
    
    def thread_apply_enhancements(self, options, style):
        path = self.enhance_selected_file
        result = None
        
        try:
            if path.endswith(".docx"):
                self.after(0, lambda: self.enhance_status.configure(text="Enhancing Word document..."))
                result = enrich_word_document(path, options, style)
            elif path.endswith(".xlsx"):
                self.after(0, lambda: self.enhance_status.configure(text="Enhancing Excel file..."))
                result = enrich_excel_file(path, options, style)
            elif path.endswith(".pptx"):
                self.after(0, lambda: self.enhance_status.configure(text="Enhancing PowerPoint..."))
                # For PPT, we need to use callback
                self.ppt_enricher.enhance_presentation(path, options, style, self.handle_ppt_enhance_progress)
                return  # Exit early, callback will handle completion
            else:
                result = "Error: Unsupported file type"
        except Exception as e:
            result = f"Error: {e}"
        
        self.after(0, lambda: self.finish_enhancement(result))
    
    def handle_ppt_enhance_progress(self, step_key, status):
        self.after(0, lambda: self._update_ppt_enhance_gui(step_key, status))
    
    def _update_ppt_enhance_gui(self, step_key, status):
        if step_key == "final":
            self.finish_enhancement(f"Success! {status}")
        elif step_key == "error":
            self.finish_enhancement(f"Error: {status}")
        elif step_key == "progress":
            self.enhance_status.configure(text=status)
    
    def finish_enhancement(self, result):
        self.enhance_progress.stop()
        self.enhance_progress.set(1)
        self.enhance_btn_apply.configure(state="normal")
        
        if result and "Error" not in result:
            self.enhance_log.insert(END, f"\n✅ {result}\n")
            self.enhance_status.configure(text="Enhancement complete!", text_color="green")
        else:
            self.enhance_log.insert(END, f"\n❌ {result}\n")
            self.enhance_status.configure(text="Enhancement failed", text_color="red")
        
        self.enhance_log.see(END)

    # ========================================================
    # TAB 5: SMART FILL (Data + Template -> PDF)
    # ========================================================
    def setup_fill_tab(self):
        frame = self.tab_fill
        
        ctk.CTkLabel(frame, text="1. Paste Data (JSON, CSV, or messy notes):").pack(anchor="w", padx=10)
        self.txt_data = ctk.CTkTextbox(frame, height=100)
        self.txt_data.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text="2. Paste Template (with placeholders like [NAME]):").pack(anchor="w", padx=10)
        self.txt_template = ctk.CTkTextbox(frame, height=100)
        self.txt_template.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(frame, text="3. Reference Style (Optional):").pack(anchor="w", padx=10)
        self.txt_ref = ctk.CTkEntry(frame, placeholder_text="E.g., generic professional tone")
        self.txt_ref.pack(fill="x", padx=10, pady=5)
        
        self.btn_fill = ctk.CTkButton(frame, text="Generate Filled Document", fg_color="purple", command=self.run_smart_fill)
        self.btn_fill.pack(pady=15)
        
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
        threading.Thread(target=self.thread_smart_fill, args=(data, template, ref)).start()

    def thread_smart_fill(self, data, template, ref):
        ai_text = smart_fill_content(data, template, ref)
        filename = f"Generated_Doc_{int(time.time())}.pdf"
        output_path = os.path.join("user_data", filename)
        os.makedirs("user_data", exist_ok=True)
        final_path = create_filled_pdf(ai_text, output_path)
        self.after(0, lambda: self.finish_smart_fill(ai_text, final_path))

    def finish_smart_fill(self, text_result, pdf_path):
        self.txt_fill_result.delete("0.0", END)
        self.txt_fill_result.insert("0.0", text_result)
        self.btn_fill.configure(state="normal", text="Generate Filled Document")
        if "Error" not in pdf_path:
            ctk.CTkLabel(self.tab_fill, text=f"✅ PDF Saved: {pdf_path}", text_color="green").pack()

    # ========================================================
    # TAB 6: ACTION RECORDER
    # ========================================================
    def setup_recorder_tab(self):
        self.recorder_ui = RecorderTab(self.tab_recorder)
        self.recorder_ui.pack(fill="both", expand=True)

    # ========================================================
    # TAB 7: DIRECTORY MAKER
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
        
        popup = ctk.CTkToplevel(self)
        popup.geometry("400x150")
        popup.title("Result")
        ctk.CTkLabel(popup, text=msg, wraplength=380).pack(pady=20)
        ctk.CTkButton(popup, text="OK", command=popup.destroy).pack()
    
    # ========================================================
    # OLLAMA STATUS MANAGEMENT
    # ========================================================
    def check_ollama_status(self):
        """Check if Ollama is running and update status indicator"""
        def check():
            manager = get_ollama_manager()
            is_running = manager.check_ollama_running()
            
            # Update UI on main thread
            self.after(0, lambda: self.update_ollama_status(is_running))
        
        # Run check in background thread
        threading.Thread(target=check, daemon=True).start()
    
    def update_ollama_status(self, is_running):
        """Update the Ollama status indicator"""
        if is_running:
            self.ollama_status_label.configure(
                text="● Running", 
                text_color="green"
            )
        else:
            self.ollama_status_label.configure(
                text="● Not Running", 
                text_color="red"
            )
