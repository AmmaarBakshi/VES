import customtkinter as ctk
from tkinter import filedialog
import threading
from app.utils.logger import log_event
from app.gui.components import StatusLabel

# Import Agents
from app.engine.word_agent import process_word_document
from app.engine.excel_agent import process_excel_file
from app.engine.ppt_agent import process_ppt_file
from app.engine.pdf_agent import process_pdf_file

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Macro Desktop App (Cloud AI)")
        self.geometry("700x500")

        # UI Layout
        self.label = ctk.CTkLabel(self, text="Smart Document Automator", font=("Roboto", 24, "bold"))
        self.label.pack(pady=20)

        self.input_instruction = ctk.CTkEntry(self, placeholder_text="What should I do? (e.g., 'Fix Grammar', 'Summarize')", width=500)
        self.input_instruction.pack(pady=10)

        self.btn_select = ctk.CTkButton(self, text="Select File (Docx, Xlsx, PPT, PDF)", command=self.select_file, height=40)
        self.btn_select.pack(pady=20)

        self.status = StatusLabel(self, text="Ready", font=("Arial", 12))
        self.status.pack(pady=20)

        self.selected_file = None

    def select_file(self):
        file_types = [
            ("All Supported", "*.docx;*.xlsx;*.pptx;*.pdf"),
            ("Word", "*.docx"), ("Excel", "*.xlsx"), 
            ("PowerPoint", "*.pptx"), ("PDF", "*.pdf")
        ]
        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.selected_file = path
            # Show filename only (not full path) to keep UI clean
            filename = path.split("/")[-1]
            self.status.configure(text=f"Selected: {filename}")
            
            # FIX: Only create the button if it doesn't exist yet
            if not hasattr(self, 'btn_run'):
                self.btn_run = ctk.CTkButton(self, text="▶ Run Automation", fg_color="green", command=self.start_thread)
                self.btn_run.pack(pady=10)
            else:
                self.btn_run.configure(state="normal")
                
    def start_thread(self):
        instruction = self.input_instruction.get() or "Enhance this"
        self.status.set_loading()
        self.btn_run.configure(state="disabled")
        
        # Threading to prevent GUI freeze
        t = threading.Thread(target=self.run_logic, args=(self.selected_file, instruction))
        t.start()

    def run_logic(self, file_path, instruction):
        log_event(f"Processing {file_path}")
        result = None
        
        if file_path.endswith(".docx"):
            result = process_word_document(file_path, instruction)
        elif file_path.endswith(".xlsx"):
            result = process_excel_file(file_path, instruction)
        elif file_path.endswith(".pptx"):
            result = process_ppt_file(file_path, instruction)
        elif file_path.endswith(".pdf"):
            result = process_pdf_file(file_path, instruction)

        # Update GUI safely
        self.after(0, lambda: self.finish(result))

    def finish(self, result):
        self.btn_run.configure(state="normal")
        if result and "Error" not in result:
            self.status.set_success(result)
        else:
            self.status.set_error("Failed to process file. Check logs.")