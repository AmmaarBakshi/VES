import customtkinter as ctk
from tkinter import filedialog, END
import threading
import os
import time
import shutil

# ---IMPORTS FROM YOUR PROJECT MODULES ---
from app.utils.config_loader import save_macro, load_macros
from app.utils.ollama_manager import get_ollama_manager
from app.engine.directory_maker import create_directory_from_text, parse_tree_to_list
from app.engine.word_agent import process_word_document
from app.engine.excel_agent import process_excel_file
from app.engine.smart_fill import smart_fill_content
from app.engine.pdf_maker import create_filled_pdf
from app.engine.ppt_agent import PPTGenerator, PPTEnricher
from app.engine.pdf_agent import PDFAgent
from app.engine.excel_agent import enrich_excel_file, suggest_excel_improvements
from app.engine.word_agent import enrich_word_document, suggest_word_improvements
from app.gui.recorder_tab import RecorderTab
from app.gui.web_scraper_tab import WebScraperTab
from app.gui.batch_tab import BatchTab
from app.gui.ai_chat_panel import AIChatPanel
from app.gui.clarify_dialog import ClarifyDialog
from app.engine.cot_engine import stream_clarifications
from langchain_ollama import OllamaLLM

# --- PREMIUM DESIGN SYSTEM ---
DESIGN = {
    # Colors - Modern gradient-ready palette
    "bg_primary": "#0A0A0F",        # Deep space black
    "bg_secondary": "#13131A",      # Elevated surface
    "bg_tertiary": "#1A1A24",       # Card background
    "bg_input": "#1F1F2E",          # Input fields
    "bg_hover": "#252534",          # Hover states
    
    # Accent colors - Vibrant gradient system
    "accent_primary": "#6366F1",    # Indigo
    "accent_secondary": "#8B5CF6",  # Purple
    
    # Status colors
    "success": "#10B981",           # Emerald
    "warning": "#F59E0B",           # Amber
    "danger": "#EF4444",            # Red
    "info": "#3B82F6",              # Blue
    
    # Text hierarchy
    "text_primary": "#F8FAFC",      # Almost white
    "text_secondary": "#94A3B8",    # Slate
    "text_tertiary": "#64748B",     # Muted slate
    "text_disabled": "#475569",     # Dark slate
    
    # Borders
    "border_subtle": "#1E293B",     
    "border_medium": "#334155",     
    
    # Typography
    "font_display": ("SF Pro Display", "Segoe UI", "Roboto"),
    "font_body": ("SF Pro Text", "Segoe UI", "Roboto"),
    "font_mono": ("JetBrains Mono", "Consolas", "Monaco"),
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class ModernButton(ctk.CTkButton):
    """Premium button with smooth hover effects"""
    def __init__(self, master, style="primary", **kwargs):
        styles = {
            "primary": {
                "fg_color": DESIGN["accent_primary"],
                "hover_color": DESIGN["accent_secondary"],
                "text_color": DESIGN["text_primary"],
                "border_width": 0,
            },
            "secondary": {
                "fg_color": DESIGN["bg_tertiary"],
                "hover_color": DESIGN["bg_hover"],
                "text_color": DESIGN["text_primary"],
                "border_width": 1,
                "border_color": DESIGN["border_medium"],
            },
            "ghost": {
                "fg_color": "transparent",
                "hover_color": DESIGN["bg_hover"],
                "text_color": DESIGN["text_secondary"],
                "border_width": 0,
            },
            "success": {
                "fg_color": DESIGN["success"],
                "hover_color": "#059669",
                "text_color": "white",
                "border_width": 0,
            },
            "danger": {
                "fg_color": DESIGN["danger"],
                "hover_color": "#DC2626",
                "text_color": "white",
                "border_width": 0,
            }
        }
        
        style_config = styles.get(style, styles["primary"])
        defaults = {
            "corner_radius": 8,
            "font": (DESIGN["font_body"][0], 13, "normal"),
            "height": 40,
            **style_config
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class ModernCard(ctk.CTkFrame):
    """Elegant card component with subtle borders"""
    def __init__(self, master, title=None, subtitle=None, **kwargs):
        defaults = {
            "fg_color": DESIGN["bg_tertiary"],
            "corner_radius": 12,
            "border_width": 1,
            "border_color": DESIGN["border_subtle"],
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)
        
        if title:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=24, pady=(20, 0))
            
            title_label = ctk.CTkLabel(
                header,
                text=title,
                font=(DESIGN["font_display"][0], 18, "bold"),
                text_color=DESIGN["text_primary"],
                anchor="w"
            )
            title_label.pack(side="left", fill="x", expand=True)
            
            if subtitle:
                subtitle_label = ctk.CTkLabel(
                    header,
                    text=subtitle,
                    font=(DESIGN["font_body"][0], 13),
                    text_color=DESIGN["text_tertiary"],
                    anchor="w"
                )
                subtitle_label.pack(anchor="w", padx=24, pady=(4, 0))
            
            divider = ctk.CTkFrame(self, height=1, fg_color=DESIGN["border_subtle"])
            divider.pack(fill="x", padx=24, pady=(16, 0))


class ModernInput(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        defaults = {
            "fg_color": DESIGN["bg_input"],
            "border_color": DESIGN["border_subtle"],
            "border_width": 1,
            "corner_radius": 8,
            "height": 44,
            "font": (DESIGN["font_body"][0], 13),
            "text_color": DESIGN["text_primary"],
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class StatusBadge(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=DESIGN["bg_secondary"],
            corner_radius=20,
            height=40,
            **kwargs
        )
        self.dot = ctk.CTkLabel(self, text="●", font=("Arial", 14), text_color=DESIGN["warning"])
        self.dot.pack(side="left", padx=(12, 8))
        self.label = ctk.CTkLabel(self, text="Initializing...", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"])
        self.label.pack(side="left", padx=(0, 16))
    
    def set_status(self, status, text):
        colors = {"success": DESIGN["success"], "error": DESIGN["danger"], "warning": DESIGN["warning"], "loading": DESIGN["info"]}
        self.dot.configure(text_color=colors.get(status, DESIGN["text_disabled"]))
        self.label.configure(text=text)


class ProgressStep(ctk.CTkFrame):
    def __init__(self, master, text, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.icon_container = ctk.CTkFrame(self, width=32, height=32, corner_radius=16, fg_color=DESIGN["bg_input"], border_width=2, border_color=DESIGN["border_subtle"])
        self.icon_container.pack(side="left", padx=(0, 12))
        self.icon_container.pack_propagate(False)
        self.icon = ctk.CTkLabel(self.icon_container, text="○", font=("Arial", 14), text_color=DESIGN["text_disabled"])
        self.icon.place(relx=0.5, rely=0.5, anchor="center")
        self.label = ctk.CTkLabel(self, text=text, font=(DESIGN["font_body"][0], 13), text_color=DESIGN["text_tertiary"], anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
    
    def set_state(self, state):
        if state == "pending":
            self.icon.configure(text="○", text_color=DESIGN["text_disabled"])
            self.label.configure(text_color=DESIGN["text_tertiary"])
            self.icon_container.configure(fg_color=DESIGN["bg_input"], border_color=DESIGN["border_subtle"])
        elif state == "active":
            self.icon.configure(text="◔", text_color=DESIGN["accent_primary"])
            self.label.configure(text_color=DESIGN["text_primary"])
            self.icon_container.configure(fg_color=DESIGN["bg_tertiary"], border_color=DESIGN["accent_primary"])
        elif state == "complete":
            self.icon.configure(text="✓", text_color=DESIGN["success"])
            self.label.configure(text_color=DESIGN["text_secondary"])
            self.icon_container.configure(fg_color=DESIGN["success"], border_color=DESIGN["success"])


class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Macro Station")
        self.geometry("1400x900")
        self.configure(fg_color=DESIGN["bg_primary"])
        
        self.ppt_engine = PPTGenerator()
        self.ppt_enricher = PPTEnricher()
        self.pdf_engine = PDFAgent()
        
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_content_area()
        
        self.frames = {}
        self.nav_buttons = {}
        self.init_all_views()
        self.select_view("Smart Process")
        self.check_ollama_status()
    
    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=DESIGN["bg_secondary"], corner_radius=0, width=280, border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        logo_section = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_section.pack(pady=(40, 30), padx=24)
        
        icon_frame = ctk.CTkFrame(logo_section, width=48, height=48, corner_radius=12, fg_color=DESIGN["accent_primary"], border_width=0)
        icon_frame.pack(pady=(0, 12))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="⚡", font=("Arial", 24)).place(relx=0.5, rely=0.5, anchor="center")
        
        ctk.CTkLabel(logo_section, text="Macro Station", font=(DESIGN["font_display"][0], 22, "bold"), text_color=DESIGN["text_primary"]).pack()
        ctk.CTkLabel(logo_section, text="AI Automation Suite", font=(DESIGN["font_body"][0], 12), text_color=DESIGN["text_tertiary"]).pack(pady=(2, 0))
        
        ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=(DESIGN["font_body"][0], 10, "bold"), text_color=DESIGN["text_disabled"], anchor="w").pack(fill="x", padx=24, pady=(20, 12))
        
        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.pack(fill="x", padx=16)
        
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(expand=True)
        self.status_badge = StatusBadge(self.sidebar)
        self.status_badge.pack(side="bottom", fill="x", padx=20, pady=30)
    
    def create_nav_button(self, name, icon="○"):
        btn_frame = ctk.CTkFrame(self.nav_container, fg_color="transparent", height=44)
        btn_frame.pack(fill="x", pady=1)
        btn = ctk.CTkButton(btn_frame, text=f"  {icon}  {name}", anchor="w", fg_color="transparent", hover_color=DESIGN["bg_hover"], text_color=DESIGN["text_secondary"], font=(DESIGN["font_body"][0], 13, "bold"), height=44, corner_radius=8, border_width=0, command=lambda: self.select_view(name))
        btn.pack(fill="both", expand=True, padx=8)
        self.nav_buttons[name] = btn
    
    def select_view(self, name):
        for frame in self.frames.values(): frame.grid_forget()
        if name in self.frames: self.frames[name].grid(row=0, column=0, sticky="nsew")
        for btn_name, btn in self.nav_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=DESIGN["accent_primary"], text_color=DESIGN["text_primary"], hover_color=DESIGN["accent_secondary"])
            else:
                btn.configure(fg_color="transparent", text_color=DESIGN["text_secondary"], hover_color=DESIGN["bg_hover"])
    
    def setup_content_area(self):
        self.content_area = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)
    
    def init_all_views(self):
        views = [("Smart Process", "⚙️", self.setup_process_view), ("PPT Maker", "📊", self.setup_ppt_view), ("Smart PDF", "📄", self.setup_pdf_view), ("AI Enhance", "✨", self.setup_enhance_view), ("Smart Fill", "📝", self.setup_fill_view), ("Batch", "⚡", self.setup_batch_view), ("Recorder", "🎙️", self.setup_recorder_view), ("Web Recorder", "🌐", self.setup_web_scraper_view), ("Directory", "📁", self.setup_dir_view)]
        for name, icon, setup_func in views:
            self.create_nav_button(name, icon)
            frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
            self.frames[name] = frame
            setup_func(frame)
    
    # =========================================================
    # SHARED REASONING TERMINAL HELPERS
    # =========================================================
    def _make_reasoning_terminal(self, parent):
        """Build and return the dark hacker-style Live Reasoning Terminal widget."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(
            header, text="\U0001f916  Live Reasoning",
            font=(DESIGN["font_mono"][0], 11, "bold"),
            text_color=DESIGN["accent_primary"], anchor="w"
        ).pack(side="left")
        ctk.CTkButton(
            header, text="\U0001f5d1 Clear", fg_color="transparent",
            hover_color=DESIGN["bg_hover"], text_color=DESIGN["text_disabled"],
            font=(DESIGN["font_body"][0], 11), height=24, width=60,
            command=lambda w=None: None  # patched below
        ).pack(side="right")
        terminal = ctk.CTkTextbox(
            parent,
            font=(DESIGN["font_mono"][0], 11),
            fg_color="#050508",
            text_color="#00FF88",
            border_width=1,
            border_color=DESIGN["border_subtle"],
            corner_radius=8,
            height=150,
            state="disabled",
            wrap="word",
        )
        terminal.pack(fill="x", pady=(0, 8))
        # Patch clear button to reference the actual terminal
        header.winfo_children()[-1].configure(command=lambda: self._clear_terminal(terminal))
        return terminal

    def _stream_thought(self, widget, text):
        """Thread-safe: insert a CoT token into the terminal widget."""
        def _insert():
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.see("end")
            widget.configure(state="disabled")
        self.after(0, _insert)

    def _clear_terminal(self, widget):
        """Clear the reasoning terminal."""
        widget.configure(state="normal")
        widget.delete("0.0", "end")
        widget.configure(state="disabled")

    # =========================================================
    # UNIVERSAL DOWNLOAD BUTTON INFRASTRUCTURE
    # =========================================================
    def _init_download_store(self):
        """Call once in __init__ to set up storage dicts."""
        if not hasattr(self, '_dl_paths'):
            self._dl_paths = {}
            self._dl_btns  = {}

    def _make_download_btn(self, parent, key: str) -> ctk.CTkButton:
        """
        Create a disabled '⬇️ Save to Downloads' button.
        Stores the reference in self._dl_btns[key].
        """
        self._init_download_store()
        btn = ctk.CTkButton(
            parent,
            text="\u2b07\ufe0f  Save to Downloads",
            fg_color=DESIGN["bg_input"],
            hover_color=DESIGN["bg_hover"],
            border_width=1,
            border_color=DESIGN["border_subtle"],
            text_color=DESIGN["text_disabled"],
            font=(DESIGN["font_body"][0], 12, "bold"),
            height=40, corner_radius=8,
            state="disabled",
            command=lambda k=key: self._do_download(k)
        )
        self._dl_btns[key] = btn
        return btn

    def _enable_download(self, key: str, filepath: str):
        """Called when a file is ready — enables the download button."""
        self._init_download_store()
        if not filepath or not os.path.exists(str(filepath)):
            return
        self._dl_paths[key] = filepath
        btn = self._dl_btns.get(key)
        if btn:
            btn.configure(
                state="normal",
                fg_color=DESIGN["success"],
                hover_color="#2ECC71",
                text_color="white",
                border_color=DESIGN["success"],
                text="\u2b07\ufe0f  Ready \u2014 Save to Downloads"
            )

    def _do_download(self, key: str):
        """Copy the generated file to the system Downloads folder."""
        filepath = self._dl_paths.get(key)
        if not filepath or not os.path.exists(filepath):
            return
        try:
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(downloads, exist_ok=True)
            dest = os.path.join(downloads, os.path.basename(filepath))
            shutil.copy2(filepath, dest)
            btn = self._dl_btns.get(key)
            if btn:
                btn.configure(text="\u2705  Saved to Downloads!", state="disabled")
                self.after(3000, lambda: btn.configure(
                    text="\u2b07\ufe0f  Ready \u2014 Save Again",
                    state="normal"
                ))
        except Exception as e:
            print(f"[Download] Error: {e}")

    # =========================================================
    # SHARED CLARIFICATION DIALOG HELPER
    # =========================================================
    def _run_clarification_phase(self, task_type: str, task_label: str, on_proceed):
        """
        Opens a centered floating ClarifyDialog, streams AI questions
        into it, then calls on_proceed(user_answer) when user submits.
        """
        if not hasattr(self, '_clarify_llm'):
            self._clarify_llm = OllamaLLM(model="llama3", temperature=0.4)

        dlg = ClarifyDialog(self, task_label=task_label, on_proceed=on_proceed)

        def _ask():
            self.after(0, dlg.start_ai_message)
            def token_cb(tok):
                self.after(0, lambda t=tok: dlg.append_ai_token(t))
            stream_clarifications(self._clarify_llm, task_type, token_cb)
            self.after(0, dlg.end_ai_message)

        threading.Thread(target=_ask, daemon=True).start()

    # =========================================================

    # === VIEW 1: SMART PROCESS ===
    # =========================================================
    def setup_process_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 32))
        ctk.CTkLabel(header, text="Smart Process", font=(DESIGN["font_display"][0], 28, "bold"), text_color=DESIGN["text_primary"], anchor="w").pack(side="left")
        
        content_grid = ctk.CTkFrame(container, fg_color="transparent")
        content_grid.pack(fill="both", expand=True)
        content_grid.grid_columnconfigure(0, weight=2)
        content_grid.grid_columnconfigure(1, weight=1)
        content_grid.grid_rowconfigure(0, weight=1)
        
        left_card = ModernCard(content_grid, title="Configuration")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        form = ctk.CTkFrame(left_card, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=24, pady=20)
        
        ctk.CTkLabel(form, text="Saved Macros", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(0, 8))
        self.macro_combo = ctk.CTkComboBox(form, values=["Custom"] + list(load_macros().keys()), command=self.load_macro_choice, fg_color=DESIGN["bg_input"], border_color=DESIGN["border_subtle"], button_color=DESIGN["accent_primary"], dropdown_fg_color=DESIGN["bg_secondary"], height=44, corner_radius=8, font=(DESIGN["font_body"][0], 13))
        self.macro_combo.pack(fill="x", pady=(0, 24))
        
        ctk.CTkLabel(form, text="AI Instruction", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(0, 8))
        self.input_instruction = ModernInput(form, placeholder_text="e.g., Summarize this document in 3 bullet points", height=48)
        self.input_instruction.pack(fill="x", pady=(0, 12))
        ModernButton(form, text="💾  Save as Macro", style="ghost", height=36, command=self.save_current_macro).pack(anchor="e")
        
        ctk.CTkLabel(form, text="Target File", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(24, 8))
        file_selector = ctk.CTkFrame(form, fg_color=DESIGN["bg_input"], corner_radius=8, height=60)
        file_selector.pack(fill="x", pady=(0, 24))
        file_selector.pack_propagate(False)
        self.btn_select = ModernButton(file_selector, text="📂  Browse", style="secondary", command=self.select_file, width=120)
        self.btn_select.pack(side="left", padx=12, pady=12)
        self.lbl_file = ctk.CTkLabel(file_selector, text="No file selected", font=(DESIGN["font_body"][0], 13), text_color=DESIGN["text_disabled"], anchor="w")
        self.lbl_file.pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        self.progress = ctk.CTkProgressBar(form, progress_color=DESIGN["accent_primary"], fg_color=DESIGN["bg_input"], corner_radius=4, height=6)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(0, 16))
        
        self.btn_run = ModernButton(form, text="\U0001f4ac  Ask AI & Run", style="primary", height=48, font=(DESIGN["font_body"][0], 14, "bold"), command=self.start_processing)
        self.btn_run.pack(fill="x")

        # --- Reasoning Terminal ---
        self.process_terminal = self._make_reasoning_terminal(form)
        
        right_card = ModernCard(content_grid, title="Activity Log")
        right_card.grid(row=0, column=1, sticky="nsew")
        log_container = ctk.CTkFrame(right_card, fg_color="transparent")
        log_container.pack(fill="both", expand=True, padx=24, pady=20)
        self.txt_log = ctk.CTkTextbox(log_container, font=(DESIGN["font_mono"][0], 11), fg_color=DESIGN["bg_input"], border_width=1, border_color=DESIGN["border_subtle"], corner_radius=8, text_color=DESIGN["text_secondary"])
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.insert("0.0", "\u26a1 System initialized and ready\n")
        # --- Download Button ---
        dl_btn = self._make_download_btn(log_container, "process")
        dl_btn.pack(fill="x", pady=(8, 0))

    # === VIEW 2: PPT MAKER ===
    def setup_ppt_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        center = ctk.CTkFrame(container, fg_color="transparent")
        center.pack(expand=True, fill="both")
        
        hero = ctk.CTkFrame(center, fg_color="transparent")
        hero.pack(pady=(0, 20))
        icon_bg = ctk.CTkFrame(hero, width=80, height=80, corner_radius=40, fg_color=DESIGN["bg_tertiary"], border_width=3, border_color=DESIGN["accent_primary"])
        icon_bg.pack(); icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="📊", font=("Arial", 40)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(hero, text="Presentation Generator", font=(DESIGN["font_display"][0], 32, "bold"), text_color=DESIGN["text_primary"]).pack(pady=(20, 8))
        ctk.CTkLabel(hero, text="AI-powered slide creation with research and structure", font=(DESIGN["font_body"][0], 14), text_color=DESIGN["text_tertiary"]).pack()
        
        card = ModernCard(center, fg_color=DESIGN["bg_tertiary"])
        card.pack(fill="x", pady=12)
        card_inner = ctk.CTkFrame(card, fg_color="transparent")
        card_inner.pack(fill="x", padx=40, pady=24)
        
        ctk.CTkLabel(card_inner, text="Topic", font=(DESIGN["font_body"][0], 13, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(0, 10))
        self.ppt_topic_entry = ModernInput(card_inner, placeholder_text="e.g., The Future of Renewable Energy", height=52)
        self.ppt_topic_entry.pack(fill="x", pady=(0, 24))
        
        self.ppt_generate_btn = ModernButton(card_inner, text="\U0001f4ac  Ask AI & Generate", style="primary", height=52, font=(DESIGN["font_body"][0], 15, "bold"), command=self.start_ppt_generation)
        self.ppt_generate_btn.pack(fill="x", pady=(0, 12))

        # --- Reasoning Terminal ---
        self.ppt_terminal = self._make_reasoning_terminal(card_inner)
        
        steps_container = ctk.CTkFrame(card_inner, fg_color=DESIGN["bg_input"], corner_radius=12, border_width=1, border_color=DESIGN["border_subtle"])
        steps_container.pack(fill="x", pady=(4, 0))
        steps_inner = ctk.CTkFrame(steps_container, fg_color="transparent")
        steps_inner.pack(fill="x", padx=20, pady=20)
        
        self.ppt_step_labels = {}
        for i, (key, text) in enumerate([("step_1", "Researching Content"), ("step_2", "Structuring Arguments"), ("step_3", "Building .PPTX File")]):
            step = ProgressStep(steps_inner, text)
            step.pack(fill="x", pady=6 if i > 0 else 0)
            self.ppt_step_labels[key] = step
        
        self.ppt_status_label = ctk.CTkLabel(card_inner, text="", font=(DESIGN["font_body"][0], 13, "bold"), text_color=DESIGN["success"])
        self.ppt_status_label.pack(pady=(20, 8))
        # --- Download Button ---
        dl_btn = self._make_download_btn(card_inner, "ppt")
        dl_btn.pack(fill="x")

    # === VIEW 3: PDF MAKER ===
    def setup_pdf_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        center = ctk.CTkFrame(container, fg_color="transparent")
        center.pack(expand=True, fill="both")
        
        hero = ctk.CTkFrame(center, fg_color="transparent")
        hero.pack(pady=(0, 20))
        icon_bg = ctk.CTkFrame(hero, width=80, height=80, corner_radius=40, fg_color=DESIGN["bg_tertiary"], border_width=3, border_color=DESIGN["danger"])
        icon_bg.pack(); icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="📄", font=("Arial", 40)).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(hero, text="AI Document Writer", font=(DESIGN["font_display"][0], 32, "bold"), text_color=DESIGN["text_primary"]).pack(pady=(20, 8))
        ctk.CTkLabel(hero, text="Generate comprehensive PDFs with AI-powered content", font=(DESIGN["font_body"][0], 14), text_color=DESIGN["text_tertiary"]).pack()
        
        card = ModernCard(center, fg_color=DESIGN["bg_tertiary"])
        card.pack(fill="x", pady=12)
        card_inner = ctk.CTkFrame(card, fg_color="transparent")
        card_inner.pack(fill="x", padx=40, pady=24)
        
        ctk.CTkLabel(card_inner, text="Document Subject", font=(DESIGN["font_body"][0], 13, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(0, 10))
        self.pdf_topic_entry = ModernInput(card_inner, placeholder_text="e.g., Essay on Quantum Computing", height=52)
        self.pdf_topic_entry.pack(fill="x", pady=(0, 24))
        
        self.pdf_btn = ModernButton(card_inner, text="\U0001f4ac  Ask AI & Write", style="danger", height=52, font=(DESIGN["font_body"][0], 15, "bold"), command=self.start_pdf_generation)
        self.pdf_btn.pack(fill="x", pady=(0, 12))

        # --- Reasoning Terminal ---
        self.pdf_terminal = self._make_reasoning_terminal(card_inner)
        
        steps_container = ctk.CTkFrame(card_inner, fg_color=DESIGN["bg_input"], corner_radius=12, border_width=1, border_color=DESIGN["border_subtle"])
        steps_container.pack(fill="x", pady=(4, 0))
        steps_inner = ctk.CTkFrame(steps_container, fg_color="transparent")
        steps_inner.pack(fill="x", padx=20, pady=20)
        
        self.pdf_step_labels = {}
        for i, (key, text) in enumerate([("step_1", "Generating Content"), ("step_2", "Formatting PDF")]):
            step = ProgressStep(steps_inner, text)
            step.pack(fill="x", pady=6 if i > 0 else 0)
            self.pdf_step_labels[key] = step
        
        self.pdf_status_label = ctk.CTkLabel(card_inner, text="", font=(DESIGN["font_body"][0], 13, "bold"), text_color=DESIGN["success"])
        self.pdf_status_label.pack(pady=(20, 8))
        # --- Download Button ---
        dl_btn = self._make_download_btn(card_inner, "pdf")
        dl_btn.pack(fill="x")

    # === VIEW 4: AI ENHANCE ===
    def setup_enhance_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 32))
        ctk.CTkLabel(header, text="AI Enhancement Studio", font=(DESIGN["font_display"][0], 28, "bold"), text_color=DESIGN["text_primary"]).pack(side="left")
        
        grid = ctk.CTkFrame(container, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1); grid.grid_columnconfigure(1, weight=1); grid.grid_rowconfigure(0, weight=1)
        
        left_card = ModernCard(grid, title="Settings")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        settings = ctk.CTkFrame(left_card, fg_color="transparent")
        settings.pack(fill="both", expand=True, padx=24, pady=20)
        
        ModernButton(settings, text="📂  Upload File", style="secondary", height=48, command=self.select_enhance_file).pack(fill="x", pady=(0, 8))
        self.enhance_lbl_file = ctk.CTkLabel(settings, text="No file selected", font=(DESIGN["font_body"][0], 12), text_color=DESIGN["text_disabled"])
        self.enhance_lbl_file.pack(pady=(0, 24))
        
        ctk.CTkLabel(settings, text="Enhancement Options", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(0, 16))
        self.enhance_improve_text = ctk.CTkCheckBox(settings, text="Improve Grammar & Clarity", font=(DESIGN["font_body"][0], 13), fg_color=DESIGN["accent_primary"], hover_color=DESIGN["accent_secondary"], border_color=DESIGN["border_medium"], text_color=DESIGN["text_primary"])
        self.enhance_improve_text.pack(anchor="w", pady=6); self.enhance_improve_text.select()
        self.enhance_auto_format = ctk.CTkCheckBox(settings, text="Auto-Format Styling", font=(DESIGN["font_body"][0], 13), fg_color=DESIGN["accent_primary"], hover_color=DESIGN["accent_secondary"], border_color=DESIGN["border_medium"], text_color=DESIGN["text_primary"])
        self.enhance_auto_format.pack(anchor="w", pady=6)
        self.enhance_add_summaries = ctk.CTkCheckBox(settings, text="Add Executive Summary", font=(DESIGN["font_body"][0], 13), fg_color=DESIGN["accent_primary"], hover_color=DESIGN["accent_secondary"], border_color=DESIGN["border_medium"], text_color=DESIGN["text_primary"])
        self.enhance_add_summaries.pack(anchor="w", pady=6)
        self.enhance_fix_consistency = ctk.CTkCheckBox(settings, text="Fix Formatting Consistency", font=(DESIGN["font_body"][0], 13), fg_color=DESIGN["accent_primary"], hover_color=DESIGN["accent_secondary"], border_color=DESIGN["border_medium"], text_color=DESIGN["text_primary"])
        self.enhance_fix_consistency.pack(anchor="w", pady=6)
        
        ctk.CTkLabel(settings, text="Writing Tone", font=(DESIGN["font_body"][0], 12, "bold"), text_color=DESIGN["text_secondary"], anchor="w").pack(fill="x", pady=(24, 8))
        self.enhance_style = ctk.CTkComboBox(settings, values=["Professional", "Casual", "Academic", "Technical"], fg_color=DESIGN["bg_input"], border_color=DESIGN["border_subtle"], button_color=DESIGN["accent_primary"], dropdown_fg_color=DESIGN["bg_secondary"], height=44, corner_radius=8)
        self.enhance_style.pack(fill="x", pady=(0, 24))
        
        self.enhance_btn_preview = ModernButton(settings, text="\U0001f50d  Analyze Suggestions", style="ghost", command=self.preview_enhancements)
        self.enhance_btn_preview.pack(fill="x", pady=(0, 12))
        self.enhance_btn_apply = ModernButton(settings, text="\U0001f4ac  Ask AI & Enhance", style="success", height=48, font=(DESIGN["font_body"][0], 14, "bold"), command=self.apply_enhancements)
        self.enhance_btn_apply.pack(fill="x")

        # --- Reasoning Terminal (left panel) ---
        self.enhance_terminal = self._make_reasoning_terminal(settings)
        
        right_card = ModernCard(grid, title="Analysis & Output")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(0, 0))
        output = ctk.CTkFrame(right_card, fg_color="transparent")
        output.pack(fill="both", expand=True, padx=24, pady=20)
        self.enhance_progress = ctk.CTkProgressBar(output, progress_color=DESIGN["success"], fg_color=DESIGN["bg_input"], height=6, corner_radius=3)
        self.enhance_progress.set(0); self.enhance_progress.pack(fill="x", pady=(0, 12))
        self.enhance_status = ctk.CTkLabel(output, text="Ready to enhance", font=(DESIGN["font_body"][0], 12), text_color=DESIGN["text_tertiary"])
        self.enhance_status.pack(pady=(0, 16))
        self.enhance_log = ctk.CTkTextbox(output, font=(DESIGN["font_mono"][0], 11), fg_color=DESIGN["bg_input"], border_width=1, border_color=DESIGN["border_subtle"], corner_radius=8, text_color=DESIGN["text_secondary"])
        self.enhance_log.pack(fill="both", expand=True)
        # --- Download Button ---
        dl_btn = self._make_download_btn(output, "enhance")
        dl_btn.pack(fill="x", pady=(8, 0))

    # === VIEW 5: SMART FILL ===
    def setup_fill_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 32))
        ctk.CTkLabel(header, text="Smart Fill", font=(DESIGN["font_display"][0], 28, "bold"), text_color=DESIGN["text_primary"]).pack(side="left")
        ctk.CTkLabel(header, text="Generate documents from data and templates", font=(DESIGN["font_body"][0], 14), text_color=DESIGN["text_tertiary"]).pack(side="left", padx=(20, 0))
        
        grid = ctk.CTkFrame(container, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0, 1, 2), weight=1); grid.grid_rowconfigure(0, weight=1)
        
        card1 = ModernCard(grid, title="1. Source Data"); card1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.txt_data = ctk.CTkTextbox(card1, font=(DESIGN["font_mono"][0], 12), fg_color=DESIGN["bg_input"], border_width=1, border_color=DESIGN["border_subtle"], corner_radius=8)
        self.txt_data.pack(fill="both", expand=True, padx=24, pady=20)
        
        card2 = ModernCard(grid, title="2. Template"); card2.grid(row=0, column=1, sticky="nsew", padx=10)
        self.txt_template = ctk.CTkTextbox(card2, font=(DESIGN["font_mono"][0], 12), fg_color=DESIGN["bg_input"], border_width=1, border_color=DESIGN["border_subtle"], corner_radius=8)
        self.txt_template.pack(fill="both", expand=True, padx=24, pady=20)
        
        card3 = ModernCard(grid, title="3. Generated Output"); card3.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        output_controls = ctk.CTkFrame(card3, fg_color="transparent")
        output_controls.pack(fill="x", padx=24, pady=(20, 0))
        self.txt_ref = ModernInput(output_controls, placeholder_text="Style reference (optional)", height=44)
        self.txt_ref.pack(fill="x", pady=(0, 16))
        self.btn_fill = ModernButton(output_controls, text="\U0001f4ac  Ask AI & Fill", style="primary", height=48, command=self.run_smart_fill)
        self.btn_fill.pack(fill="x", pady=(0, 12))
        # --- Reasoning Terminal ---
        self.fill_terminal = self._make_reasoning_terminal(output_controls)
        self.txt_fill_result = ctk.CTkTextbox(card3, font=(DESIGN["font_mono"][0], 11), fg_color=DESIGN["bg_input"], border_width=1, border_color=DESIGN["border_subtle"], corner_radius=8)
        self.txt_fill_result.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        # --- Download Button ---
        dl_btn = self._make_download_btn(card3, "fill")
        dl_btn.pack(fill="x", padx=24, pady=(0, 16))

    # === VIEW 6: RECORDER ===
    def setup_recorder_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        card = ModernCard(container, title="Action Replay")
        card.pack(fill="both", expand=True)
        self.recorder_ui = RecorderTab(card)
        self.recorder_ui.pack(fill="both", expand=True, padx=24, pady=20)

    # === VIEW 7: WEB SCRAPER ===
    def setup_web_scraper_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)
        card = ModernCard(container, title="Web Recorder")
        card.pack(fill="both", expand=True)
        self.web_scraper_ui = WebScraperTab(card)
        self.web_scraper_ui.pack(fill="both", expand=True, padx=24, pady=20)

    # === VIEW 8: BATCH PROCESSOR ===
    def setup_batch_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=30)
        self.batch_ui = BatchTab(container)
        self.batch_ui.pack(fill="both", expand=True)

    # === VIEW 9: DIRECTORY ===
    def setup_dir_view(self, frame):
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(
            header,
            text="Directory Generator",
            font=(DESIGN["font_display"][0], 28, "bold"),
            text_color=DESIGN["text_primary"]
        ).pack(side="left")

        # ── Two-column layout: Input left, Preview right ──
        cols = ctk.CTkFrame(container, fg_color="transparent")
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure(0, weight=3)
        cols.grid_columnconfigure(1, weight=2)
        cols.grid_rowconfigure(0, weight=1)

        # ── LEFT: Input card ──
        left_card = ModernCard(cols, title="Tree Structure")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_inner = ctk.CTkFrame(left_card, fg_color="transparent")
        left_inner.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            left_inner,
            text="Paste your directory tree structure below:",
            font=(DESIGN["font_body"][0], 13),
            text_color=DESIGN["text_secondary"],
            anchor="w"
        ).pack(fill="x", pady=(0, 8))

        self.txt_tree = ctk.CTkTextbox(
            left_inner,
            font=(DESIGN["font_mono"][0], 12),
            fg_color=DESIGN["bg_input"],
            border_width=1,
            border_color=DESIGN["border_subtle"],
            corner_radius=8
        )
        self.txt_tree.pack(fill="both", expand=True, pady=(0, 10))

        # Preview + Build buttons row
        action_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 10))

        ModernButton(
            action_row,
            text="🔍  Preview Tree",
            style="ghost",
            command=self.preview_dir_tree
        ).pack(side="left", padx=(0, 8))

        # Enhancement 3: Copy Tree button
        ModernButton(
            action_row,
            text="📋  Copy Tree",
            style="ghost",
            command=self._copy_dir_preview
        ).pack(side="left", padx=(0, 8))

        self.btn_create_tree = ModernButton(
            action_row,
            text="🚀  Build Project",
            style="success",
            command=self.generate_tree
        )
        self.btn_create_tree.pack(side="right")

        # Destination selector
        dest_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        dest_row.pack(fill="x", pady=(0, 4))

        ModernButton(
            dest_row,
            text="📁  Select Destination",
            style="secondary",
            command=self.select_target_dir
        ).pack(side="left", padx=(0, 10))

        self.lbl_target = ctk.CTkLabel(
            dest_row,
            text="Current directory",
            font=(DESIGN["font_body"][0], 12),
            text_color=DESIGN["text_disabled"]
        )
        self.lbl_target.pack(side="left", fill="x", expand=True)

        # Progress line  (Bug 2 fix: progress bar starts hidden)
        self.dir_status_frame = ctk.CTkFrame(left_inner, fg_color="transparent")
        self.dir_status_frame.pack(fill="x", pady=(4, 0))
        self.dir_progress = ctk.CTkProgressBar(
            self.dir_status_frame,
            progress_color=DESIGN["success"],
            fg_color=DESIGN["bg_input"],
            height=6
        )
        self.dir_progress.set(0)
        # Do NOT pack here — it will be packed when a build starts
        self.dir_status_lbl = ctk.CTkLabel(
            self.dir_status_frame,
            text="Ready to build",
            text_color=DESIGN["text_tertiary"],
            font=(DESIGN["font_body"][0], 12),
            anchor="w"
        )
        self.dir_status_lbl.pack(fill="x")

        # Reasoning terminal
        self.dir_terminal = self._make_reasoning_terminal(left_inner)

        # ── RIGHT: Preview card ──
        right_card = ModernCard(cols, title="📋 Parsed Preview")
        right_card.grid(row=0, column=1, sticky="nsew")
        right_inner = ctk.CTkFrame(right_card, fg_color="transparent")
        right_inner.pack(fill="both", expand=True, padx=16, pady=16)

        # Enhancement 2: count badge row
        preview_header_row = ctk.CTkFrame(right_inner, fg_color="transparent")
        preview_header_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            preview_header_row,
            text='Click "Preview Tree" to verify what will be created:',
            font=(DESIGN["font_body"][0], 12),
            text_color=DESIGN["text_tertiary"],
            anchor="w"
        ).pack(side="left", fill="x", expand=True)
        self.dir_count_badge = ctk.CTkLabel(
            preview_header_row,
            text="",
            font=(DESIGN["font_mono"][0], 10, "bold"),
            text_color=DESIGN["accent_primary"],
            anchor="e"
        )
        self.dir_count_badge.pack(side="right")

        self.dir_preview_box = ctk.CTkTextbox(
            right_inner,
            font=(DESIGN["font_mono"][0], 11),
            fg_color=DESIGN["bg_input"],
            border_width=1,
            border_color=DESIGN["border_subtle"],
            corner_radius=8,
            text_color="#00FF88",
            state="disabled"
        )
        self.dir_preview_box.pack(fill="both", expand=True, pady=(0, 10))

        # Open in Explorer button (hidden until build succeeds)
        self.btn_open_explorer = ctk.CTkButton(
            right_inner,
            text="📂  Open in Explorer",
            fg_color=DESIGN["bg_input"],
            hover_color=DESIGN["bg_hover"],
            border_width=1,
            border_color=DESIGN["border_subtle"],
            text_color=DESIGN["text_disabled"],
            font=(DESIGN["font_body"][0], 12, "bold"),
            height=40,
            corner_radius=8,
            state="disabled",
            command=self._open_built_dir_in_explorer
        )
        self.btn_open_explorer.pack(fill="x")
        self._built_dir_path = None

    # =====================================================
    # LOGIC METHODS
    # =====================================================
    def select_file(self):
        file_types = [("All Supported", "*.docx;*.xlsx;*.pptx;*.pdf")]
        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.selected_file = path
            filename = os.path.basename(path)
            self.lbl_file.configure(text=filename, text_color=DESIGN["text_primary"])
            self.log(f"✓ Selected: {filename}")
    
    def start_processing(self):
        if not hasattr(self, 'selected_file'):
            self.log("\u26a0\ufe0f Please select a file first")
            return
        self.btn_run.configure(state="disabled", text="Asking AI...")
        self._clear_terminal(self.process_terminal)

        def on_answer(user_context):
            instruction = self.input_instruction.get()
            enriched = f"{instruction}\n\nUser preferences: {user_context}" if user_context else instruction
            self.after(0, lambda: self.progress.start())
            thought_cb = lambda t: self._stream_thought(self.process_terminal, t)
            path = self.selected_file
            self.log(f"\u2699\ufe0f Processing {os.path.basename(path)}...")
            result = None
            try:
                if path.endswith(".docx"): result = process_word_document(path, enriched, thought_callback=thought_cb)
                elif path.endswith(".xlsx"): result = process_excel_file(path, enriched, thought_callback=thought_cb)
                else: result = "Error: Unsupported file type"
            except Exception as e: result = f"Error: {str(e)}"
            self.after(0, lambda: self.finish_processing(result))

        self._run_clarification_phase("word_process", "Smart Process", on_answer)
    
    def finish_processing(self, result):
        self.progress.stop()
        self.progress.set(1)
        self.btn_run.configure(state="normal", text="\U0001f4ac  Ask AI & Run")
        if result and "Error" not in str(result):
            self.log(f"\u2705 Success! Output: {result}")
            self._enable_download("process", result)
        else:
            self.log(f"\u274c {result}")
    
    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert(END, f"[{timestamp}] {msg}\n")
        self.txt_log.see(END)
    
    def save_current_macro(self):
        dialog = ctk.CTkInputDialog(text="Macro name:", title="Save Macro")
        name = dialog.get_input()
        instruction = self.input_instruction.get()
        if name and instruction:
            save_macro(name, instruction)
            new_values = ["Custom"] + list(load_macros().keys())
            self.macro_combo.configure(values=new_values)
            self.log(f"💾 Saved macro: {name}")
    
    def load_macro_choice(self, choice):
        macros = load_macros()
        if choice in macros:
            self.input_instruction.delete(0, END)
            self.input_instruction.insert(0, macros[choice])
            self.log(f"📋 Loaded macro: {choice}")
    
    def start_ppt_generation(self):
        topic = self.ppt_topic_entry.get()
        if not topic: return
        self.ppt_status_label.configure(text="Asking AI for preferences...")
        self.ppt_generate_btn.configure(state="disabled", text="Asking AI...")
        for step in self.ppt_step_labels.values(): step.set_state("pending")
        self._clear_terminal(self.ppt_terminal)

        def on_answer(user_context):
            thought_cb = lambda t: self._stream_thought(self.ppt_terminal, t)
            if self.ppt_engine:
                threading.Thread(
                    target=lambda: self.ppt_engine.generate_ppt(
                        f"{topic}\n\nUser preferences: {user_context}" if user_context else topic,
                        self.handle_ppt_progress,
                        thought_callback=thought_cb
                    ), daemon=True
                ).start()

        self._run_clarification_phase("ppt", f"PPT: {topic[:30]}", on_answer)
    
    def handle_ppt_progress(self, step_key, status):
        self.after(0, lambda: self._update_ppt_gui_safe(step_key, status))
    
    def _update_ppt_gui_safe(self, step_key, status):
        if step_key == "final":
            fname = os.path.basename(status) if os.path.isfile(status) else status
            self.ppt_status_label.configure(text=f"\u2705 {fname}")
            self.ppt_generate_btn.configure(state="normal", text="\U0001f4ac  Ask AI & Generate")
            self._enable_download("ppt", status)  # status = full file path
        elif step_key == "error":
            self.ppt_status_label.configure(text=f"\u274c {status}", text_color=DESIGN["danger"])
            self.ppt_generate_btn.configure(state="normal", text="\U0001f4ac  Ask AI & Generate")
        elif step_key in self.ppt_step_labels:
            step = self.ppt_step_labels[step_key]
            if status == "running": step.set_state("active")
            elif status == "done": step.set_state("complete")
    
    def start_pdf_generation(self):
        topic = self.pdf_topic_entry.get()
        if not topic: return
        self.pdf_status_label.configure(text="Asking AI for preferences...")
        self.pdf_btn.configure(state="disabled", text="Asking AI...")
        for step in self.pdf_step_labels.values(): step.set_state("pending")
        self._clear_terminal(self.pdf_terminal)

        def on_answer(user_context):
            thought_cb = lambda t: self._stream_thought(self.pdf_terminal, t)
            if self.pdf_engine:
                threading.Thread(
                    target=lambda: self.pdf_engine.generate_smart_pdf(
                        f"{topic}\n\nUser preferences: {user_context}" if user_context else topic,
                        self.handle_pdf_progress,
                        thought_callback=thought_cb
                    ), daemon=True
                ).start()

        self._run_clarification_phase("pdf", f"PDF: {topic[:30]}", on_answer)
    
    def handle_pdf_progress(self, step_key, status):
        self.after(0, lambda: self._update_pdf_gui_safe(step_key, status))
    
    def _update_pdf_gui_safe(self, step_key, status):
        if step_key == "final":
            fname = os.path.basename(status) if os.path.isfile(status) else status
            self.pdf_status_label.configure(text=f"\u2705 {fname}")
            self.pdf_btn.configure(state="normal", text="\U0001f4ac  Ask AI & Write")
            self._enable_download("pdf", status)  # status = full file path
        elif step_key == "error":
            self.pdf_status_label.configure(text=f"\u274c {status}", text_color=DESIGN["danger"])
            self.pdf_btn.configure(state="normal", text="\U0001f4ac  Ask AI & Write")
        elif step_key in self.pdf_step_labels:
            step = self.pdf_step_labels[step_key]
            if status == "running": step.set_state("active")
            elif status == "done": step.set_state("complete")
    
    def select_enhance_file(self):
        file_types = [("Supported", "*.docx;*.xlsx;*.pptx")]
        path = filedialog.askopenfilename(filetypes=file_types)
        if path:
            self.enhance_selected_file = path
            filename = os.path.basename(path)
            self.enhance_lbl_file.configure(text=filename, text_color=DESIGN["text_primary"])
            self.enhance_log.insert(END, f"✓ Selected: {filename}\n")
    
    def preview_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'): return
        self.enhance_log.insert(END, "\n🔍 Analyzing document...\n")
        threading.Thread(target=self.thread_preview_enhancements, daemon=True).start()
    
    def thread_preview_enhancements(self):
        path = self.enhance_selected_file
        try:
            if path.endswith(".docx"): suggestions = suggest_word_improvements(path)
            elif path.endswith(".xlsx"): suggestions = suggest_excel_improvements(path)
            elif path.endswith(".pptx"): suggestions = self.ppt_enricher.get_improvement_suggestions(path)
            else: suggestions = ["Unsupported file type"]
        except Exception as e: suggestions = [f"Error: {str(e)}"]
        self.after(0, lambda: self.display_suggestions(suggestions))
    
    def display_suggestions(self, suggestions):
        self.enhance_log.insert(END, "\n" + "─" * 40 + "\n")
        for s in suggestions: self.enhance_log.insert(END, f"  • {s}\n")
        self.enhance_log.insert(END, "─" * 40 + "\n")
    
    def apply_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'): return
        options = {
            'improve_text': self.enhance_improve_text.get() == 1,
            'auto_format': self.enhance_auto_format.get() == 1,
            'add_summaries': self.enhance_add_summaries.get() == 1,
            'fix_consistency': self.enhance_fix_consistency.get() == 1,
            'improve_content': True, 'improve_paragraphs': True
        }
        style = self.enhance_style.get().lower()
        self.enhance_btn_apply.configure(state="disabled", text="Asking AI...")
        self.enhance_progress.start()
        self._clear_terminal(self.enhance_terminal)

        options_snap = {
            'improve_text': self.enhance_improve_text.get() == 1,
            'auto_format': self.enhance_auto_format.get() == 1,
            'add_summaries': self.enhance_add_summaries.get() == 1,
            'fix_consistency': self.enhance_fix_consistency.get() == 1,
            'improve_content': True, 'improve_paragraphs': True
        }

        def on_answer(user_context):
            enriched_style = f"{style} \u2014 extra notes: {user_context}" if user_context else style
            threading.Thread(
                target=self.thread_apply_enhancements,
                args=(options_snap, enriched_style),
                daemon=True
            ).start()

        self._run_clarification_phase("enhance", "AI Enhance", on_answer)
    
    def thread_apply_enhancements(self, options, style):
        path = self.enhance_selected_file
        result = None
        thought_cb = lambda t: self._stream_thought(self.enhance_terminal, t)
        try:
            if path.endswith(".docx"): result = enrich_word_document(path, options, style, thought_callback=thought_cb)
            elif path.endswith(".xlsx"): result = enrich_excel_file(path, options, style, thought_callback=thought_cb)
            elif path.endswith(".pptx"): self.ppt_enricher.enhance_presentation(path, options, style, self.handle_ppt_enhance_progress); return
        except Exception as e: result = f"Error: {str(e)}"
        self.after(0, lambda: self.finish_enhancement(result))
    
    def handle_ppt_enhance_progress(self, step_key, status):
        self.after(0, lambda: self._update_ppt_enhance_gui(step_key, status))
    
    def _update_ppt_enhance_gui(self, step_key, status):
        if step_key == "final": self.finish_enhancement(f"✅ {status}")
        elif step_key == "error": self.finish_enhancement(f"❌ {status}")
        elif step_key == "progress": self.enhance_status.configure(text=status)
    
    def finish_enhancement(self, result):
        self.enhance_progress.stop()
        self.enhance_progress.set(1)
        self.enhance_btn_apply.configure(state="normal", text="\U0001f4ac  Ask AI & Enhance")
        self.enhance_log.insert(END, f"\n{result}\n")
        self.enhance_status.configure(text="Complete")
        if result and isinstance(result, str) and os.path.isfile(result):
            self._enable_download("enhance", result)
    
    def run_smart_fill(self):
        data = self.txt_data.get("0.0", END).strip()
        template = self.txt_template.get("0.0", END).strip()
        ref = self.txt_ref.get().strip()
        if not data or not template: return
        self.btn_fill.configure(state="disabled", text="Asking AI...")
        self._clear_terminal(self.fill_terminal)

        def on_answer(user_context):
            threading.Thread(
                target=self.thread_smart_fill,
                args=(data, template, ref, user_context),
                daemon=True
            ).start()

        self._run_clarification_phase("smart_fill", "Smart Fill", on_answer)

    def thread_smart_fill(self, data, template, ref, user_context=""):
        thought_cb = lambda t: self._stream_thought(self.fill_terminal, t)
        enriched_data = f"{data}\n\nUser notes: {user_context}" if user_context else data
        ai_text = smart_fill_content(enriched_data, template, ref, thought_callback=thought_cb)
        filename = f"Generated_Doc_{int(time.time())}.pdf"
        output_path = os.path.join("user_data", filename)
        os.makedirs("user_data", exist_ok=True)
        final_path = create_filled_pdf(ai_text, output_path)
        self.after(0, lambda: self.finish_smart_fill(ai_text, final_path))
    
    def finish_smart_fill(self, text_result, pdf_path):
        self.txt_fill_result.delete("0.0", END)
        self.txt_fill_result.insert("0.0", text_result)
        self.btn_fill.configure(state="normal", text="\U0001f4ac  Ask AI & Fill")
        if pdf_path and os.path.isfile(str(pdf_path)):
            self._enable_download("fill", pdf_path)
    
    # ── Directory Logic ──
    def select_target_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.target_dir = path
            self.lbl_target.configure(
                text=f".../{os.path.basename(path)}",
                text_color=DESIGN["text_primary"]
            )

    def preview_dir_tree(self):
        """Parse the tree text and show a human-readable preview in the right panel."""
        text = self.txt_tree.get("0.0", END).strip()
        if not text:
            return

        entries = parse_tree_to_list(text)
        if not entries:
            preview = "⚠️  Nothing parsed — check the tree format."
            # Enhancement 2: clear badge
            self.dir_count_badge.configure(text="")
        else:
            lines = []
            for e in entries:
                indent = "  " * (e['depth'] // 2)
                icon = "📄" if e['type'] == 'file' else "📁"
                lines.append(f"{indent}{icon} {e['name']}")
            total_files = sum(1 for e in entries if e['type'] == 'file')
            total_folders = sum(1 for e in entries if e['type'] == 'folder')
            summary = f"\n── {total_folders} folder(s), {total_files} file(s) ──"
            preview = "\n".join(lines) + summary
            # Enhancement 2: update count badge
            self.dir_count_badge.configure(
                text=f"{total_folders} 📁  {total_files} 📄"
            )

        self.dir_preview_box.configure(state="normal")
        self.dir_preview_box.delete("0.0", END)
        self.dir_preview_box.insert("0.0", preview)
        self.dir_preview_box.configure(state="disabled")

    def _copy_dir_preview(self):
        """Enhancement 3: Copy the parsed preview text to the clipboard."""
        self.dir_preview_box.configure(state="normal")
        content = self.dir_preview_box.get("0.0", END).strip()
        self.dir_preview_box.configure(state="disabled")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)

    def generate_tree(self):
        text = self.txt_tree.get("0.0", END).strip()
        if not text:
            return

        # Enhancement 1: validate the tree produces at least one parseable entry
        entries = parse_tree_to_list(text)
        if not entries:
            self.dir_status_lbl.configure(
                text="⚠️ Nothing to build — paste a valid directory tree first.",
                text_color=DESIGN["warning"]
            )
            return

        target = getattr(self, 'target_dir', os.getcwd())

        self.btn_create_tree.configure(state="disabled", text="Asking AI...")
        # Hide explorer button while rebuilding
        self.btn_open_explorer.configure(
            state="disabled",
            fg_color=DESIGN["bg_input"],
            text_color=DESIGN["text_disabled"],
            text="📂  Open in Explorer"
        )
        self._clear_terminal(self.dir_terminal)

        def on_answer(user_context):
            # ── Instant feedback so the terminal is never blank ──
            self.after(0, lambda: self._stream_thought(
                self.dir_terminal,
                f"◆ Build started — target: {target}\n"
                f"◆ Detecting project stack...\n\n"
            ))
            # Show and start the progress bar only now (Bug 2 fix)
            self.after(0, lambda: self.dir_progress.pack(fill="x", pady=(0, 5)))
            self.after(0, self.dir_progress.start)

            def on_progress(status, msg):
                self.after(0, lambda s=status, m=msg: self._update_dir_ui(s, m, target))

            def on_thought(token):
                self._stream_thought(self.dir_terminal, token)

            enriched_tree = (
                f"{text}\n\n# User notes: {user_context}" if user_context else text
            )
            create_directory_from_text(target, enriched_tree, on_progress, thought_callback=on_thought)


        def on_cancel():
            # Re-enable button if the dialog is dismissed without answering
            self.after(0, lambda: self.btn_create_tree.configure(
                state="normal", text="🚀  Build Project"
            ))

        # Wrap _run_clarification_phase to catch cancellation
        self._run_clarification_phase_with_cancel("directory", "Directory Maker", on_answer, on_cancel)

    def _run_clarification_phase_with_cancel(self, task_type, task_label, on_proceed, on_cancel=None):
        """
        Like _run_clarification_phase but calls on_cancel() if the dialog is
        closed without the user submitting an answer.
        """
        from app.gui.clarify_dialog import ClarifyDialog
        from app.engine.cot_engine import stream_clarifications

        if not hasattr(self, '_clarify_llm'):
            self._clarify_llm = OllamaLLM(model="llama3", temperature=0.4)

        def _wrapped_proceed(answer):
            on_proceed(answer)

        def _wrapped_cancel():
            if on_cancel:
                on_cancel()

        dlg = ClarifyDialog(
            self,
            task_label=task_label,
            on_proceed=_wrapped_proceed,
            on_cancel=_wrapped_cancel
        )

        def _ask():
            self.after(0, dlg.start_ai_message)
            def token_cb(tok):
                self.after(0, lambda t=tok: dlg.append_ai_token(t))
            stream_clarifications(self._clarify_llm, task_type, token_cb)
            self.after(0, dlg.end_ai_message)

        threading.Thread(target=_ask, daemon=True).start()

    def _open_built_dir_in_explorer(self):
        """Open the last successfully built directory in Windows Explorer."""
        path = getattr(self, '_built_dir_path', None)
        if path and os.path.isdir(path):
            import subprocess
            subprocess.Popen(f'explorer "{os.path.normpath(path)}"')

    def _update_dir_ui(self, status, msg, built_path=None):
        self.dir_status_lbl.configure(text=msg)

        if status == "running":
            self.dir_status_lbl.configure(text_color=DESIGN["accent_primary"])
        elif status == "done":
            self.dir_progress.stop()
            self.dir_progress.pack_forget()
            self.dir_status_lbl.configure(text_color=DESIGN["success"])
            self.btn_create_tree.configure(state="normal", text="🚀  Build Project")
            # Enable Open in Explorer
            if built_path:
                self._built_dir_path = built_path
            self.btn_open_explorer.configure(
                state="normal",
                fg_color=DESIGN["success"],
                hover_color="#2ECC71",
                text_color="white",
                border_color=DESIGN["success"],
                text="📂  Open in Explorer"
            )
        elif status == "error":
            self.dir_progress.stop()
            self.dir_progress.pack_forget()  # Bug 1 fix: hide bar after error
            self.dir_status_lbl.configure(text_color=DESIGN["danger"])
            self.btn_create_tree.configure(state="normal", text="🚀  Build Project")
    
    def check_ollama_status(self):
        def check():
            manager = get_ollama_manager()
            is_running = manager.check_ollama_running()
            self.after(0, lambda: self.update_ollama_status(is_running))
        threading.Thread(target=check, daemon=True).start()
    
    def update_ollama_status(self, is_running):
        if is_running: self.status_badge.set_status("success", "Ollama Active")
        else: self.status_badge.set_status("error", "Ollama Offline")

if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()