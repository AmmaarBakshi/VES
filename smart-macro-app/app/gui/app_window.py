import sys
import threading
import os
import time
import shutil

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QStackedWidget, QPushButton, QLabel, QLineEdit, QPlainTextEdit,
    QComboBox, QCheckBox, QProgressBar, QFrame, QFileDialog,
    QInputDialog, QSizePolicy, QSlider, QScrollArea, QApplication,
    QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSignal, pyqtSlot, QObject, QSize
from PyQt6.QtGui import QFont, QTextCursor, QIcon

# --- PROJECT IMPORTS ---
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
from app.gui.ai_chat_panel import AIChatPanel
from app.gui.clarify_dialog import ClarifyDialog
from app.engine.cot_engine import stream_clarifications
from app.engine.batch_engine import run_batch, ACTION_LABELS, scan_folder
from langchain_ollama import OllamaLLM
from app.gui.theme import ThemeManager
from app.gui.components import Card, StatusBadge, ProgressStep, ReasoningTerminal, DownloadButton


class SignalBridge(QObject):
    """Thread-safe signal bridge for UI updates from background threads."""
    update_signal = pyqtSignal(str, object)


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Macro Station")

        # Screen-aware sizing — 80% of available screen
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(1400, int(screen.width() * 0.8))
        h = min(900, int(screen.height() * 0.8))
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)

        self.ppt_engine = PPTGenerator()
        self.ppt_enricher = PPTEnricher()
        self.pdf_engine = PDFAgent()

        # Signal bridge for thread-safe updates
        self._bridge = SignalBridge()
        self._bridge.update_signal.connect(self._handle_signal)

        self._dl_paths = {}
        self._dl_btns = {}

        self._setup_ui()
        self.select_view(0)
        self.check_ollama_status()

    # =========================================================
    # UI SETUP
    # =========================================================
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._setup_sidebar(main_layout)

        # Content area
        content_wrapper = QWidget()
        content_wrapper.setObjectName("contentArea")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_wrapper, 1)

        # Build all 8 views
        self._views = {}
        self._nav_btns = []
        views = [
            ("Process Files", "app/gui/icons/Gemini_Generated_Image_u2worhu2worhu2wo-removebg-preview.png", self._build_process_view),
            ("Presentations", "app/gui/icons/presentations.png", self._build_ppt_view),
            ("PDF Writer", "app/gui/icons/PDF.png", self._build_pdf_view),
            ("Enhance", "app/gui/icons/enhance.png", self._build_enhance_view),
            ("Fill Templates", "app/gui/icons/fill.png", self._build_fill_view),
            ("Recorder", "app/gui/icons/Recorder.png", self._build_recorder_view),
            ("Web Scraper", "app/gui/icons/webrecorder.png", self._build_web_scraper_view),
            ("Directories", "app/gui/icons/directories.png", self._build_dir_view),
            ("Batch", "app/gui/icons/Batch.png", self._build_batch_view),
        ]
        for i, (name, icon, builder) in enumerate(views):
            btn = self._add_nav_button(name, icon, i)
            self._nav_btns.append(btn)
            page = builder()
            self.stack.addWidget(page)

    def _setup_sidebar(self, parent_layout):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # ── Logo area ──
        logo_container = QWidget()
        logo_container.setStyleSheet("background: transparent;")
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(24, 30, 24, 0)
        logo_layout.setSpacing(0)

        icon_frame = QFrame()
        icon_frame.setObjectName("iconFrame")
        icon_frame.setFixedSize(42, 42)
        icon_lbl = QLabel("⚡", icon_frame)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; color: white;")
        icon_lbl.setGeometry(0, 0, 42, 42)
        logo_layout.addWidget(icon_frame)

        title_w = QWidget()
        title_l = QVBoxLayout(title_w)
        title_l.setContentsMargins(14, 0, 0, 0)
        title_l.setSpacing(1)
        title_lbl = QLabel("Macro Station")
        title_lbl.setObjectName("logoTitle")
        title_l.addWidget(title_lbl)
        subtitle_lbl = QLabel("AI Suite")
        subtitle_lbl.setObjectName("logoSubtitle")
        title_l.addWidget(subtitle_lbl)
        logo_layout.addWidget(title_w)
        logo_layout.addStretch()
        sidebar_layout.addWidget(logo_container)
        sidebar_layout.addSpacing(24)

        # ── Navigation section ──
        section_lbl = QLabel("  MENU")
        section_lbl.setObjectName("sectionLabel")
        section_lbl.setContentsMargins(24, 0, 0, 6)
        sidebar_layout.addWidget(section_lbl)

        self._nav_container = QVBoxLayout()
        self._nav_container.setContentsMargins(12, 0, 12, 0)
        self._nav_container.setSpacing(3)
        sidebar_layout.addLayout(self._nav_container)

        sidebar_layout.addStretch(1)

        # ── Bottom section ──
        bottom = QVBoxLayout()
        bottom.setContentsMargins(12, 0, 12, 0)
        bottom.setSpacing(6)

        # Theme toggle
        self._theme_btn = QPushButton("🌙  Dark Mode")
        self._theme_btn.setObjectName("navButton")
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.clicked.connect(self._toggle_theme)
        self._theme_btn.setFixedHeight(40)
        bottom.addWidget(self._theme_btn)

        # Status badge
        self.status_badge = StatusBadge()
        bottom.addWidget(self.status_badge)
        bottom.addSpacing(16)

        sidebar_layout.addLayout(bottom)
        parent_layout.addWidget(sidebar)

    def _add_nav_button(self, name, icon, index):
        if icon.endswith(('.png', '.svg', '.ico')):
            btn = QPushButton(f"  {name}")
            btn.setIcon(QIcon(icon))
            btn.setIconSize(QSize(56, 56))
            btn.setFixedHeight(60)
        else:
            btn = QPushButton(f"  {icon}   {name}")
            btn.setFixedHeight(40)
        btn.setObjectName("navButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, idx=index: self.select_view(idx))
        self._nav_container.addWidget(btn)
        return btn

    def select_view(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_btns):
            if i == index:
                btn.setObjectName("navButtonActive")
            else:
                btn.setObjectName("navButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_theme(self):
        app = QApplication.instance()
        ThemeManager.toggle(app)
        if ThemeManager.is_dark():
            self._theme_btn.setText("☀️  Light Mode")
        else:
            self._theme_btn.setText("🌙  Dark Mode")

    # =========================================================
    # THREAD-SAFE SIGNAL HANDLER
    # =========================================================
    def _emit(self, key, data=None):
        self._bridge.update_signal.emit(key, data)

    @pyqtSlot(str, object)
    def _handle_signal(self, key, data):
        handlers = {
            "process_done": lambda d: self.finish_processing(d),
            "ppt_progress": lambda d: self._update_ppt_gui_safe(d[0], d[1]),
            "pdf_progress": lambda d: self._update_pdf_gui_safe(d[0], d[1]),
            "enhance_done": lambda d: self.finish_enhancement(d),
            "enhance_status": lambda d: self.enhance_status.setText(d),
            "fill_done": lambda d: self.finish_smart_fill(d[0], d[1]),
            "dir_update": lambda d: self._update_dir_ui(d[0], d[1], d[2] if len(d) > 2 else None),
            "ollama_status": lambda d: self.update_ollama_status(d),
            "log": lambda d: self.log(d),
            "stream_process": lambda d: self._stream_to_terminal(self.process_terminal, d),
            "stream_ppt": lambda d: self._stream_to_terminal(self.ppt_terminal, d),
            "stream_pdf": lambda d: self._stream_to_terminal(self.pdf_terminal, d),
            "stream_enhance": lambda d: self._stream_to_terminal(self.enhance_terminal, d),
            "stream_fill": lambda d: self._stream_to_terminal(self.fill_terminal, d),
            "stream_dir": lambda d: self._stream_to_terminal(self.dir_terminal, d),
            "stream_batch": lambda d: self._stream_to_terminal(self.batch_terminal, d),
            "batch_file_status": lambda d: self._batch_update_file(d[0], d[1]),
            "batch_done": lambda d: self.finish_batch(d),
        }
        handler = handlers.get(key)
        if handler:
            handler(data)

    def _stream_to_terminal(self, terminal, text):
        terminal.append_text(text)

    # =========================================================
    # SHARED HELPERS
    # =========================================================
    def _make_reasoning_section(self, parent_layout):
        header = QHBoxLayout()
        header.setContentsMargins(0, 8, 0, 4)
        lbl = QLabel("  Live Reasoning")
        lbl.setStyleSheet("font-family: 'Cascadia Code', 'Consolas'; font-size: 11px; font-weight: bold; color: #2563EB;")
        header.addWidget(lbl)
        header.addStretch()
        terminal = ReasoningTerminal()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("ghost")
        clear_btn.setFixedHeight(28)
        clear_btn.setMinimumWidth(64)
        clear_btn.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        clear_btn.clicked.connect(terminal.clear_text)
        header.addWidget(clear_btn)
        parent_layout.addLayout(header)
        parent_layout.addWidget(terminal)
        return terminal

    def _make_download_btn(self, parent_layout, key):
        btn = DownloadButton()
        btn.clicked.connect(lambda: self._do_download(key))
        self._dl_btns[key] = btn
        parent_layout.addWidget(btn)
        return btn

    def _enable_download(self, key, filepath):
        if not filepath or not os.path.exists(str(filepath)):
            return
        self._dl_paths[key] = filepath
        btn = self._dl_btns.get(key)
        if btn:
            btn.set_ready(filepath)

    def _do_download(self, key):
        filepath = self._dl_paths.get(key)
        if not filepath or not os.path.exists(filepath):
            return
        btn = self._dl_btns.get(key)
        if btn:
            dest = btn.do_download()
            if dest:
                QTimer.singleShot(3000, lambda: self._reset_download_btn(key))

    def _reset_download_btn(self, key):
        btn = self._dl_btns.get(key)
        if btn:
            btn.setText("⬇️  Ready — Save Again")
            btn.setEnabled(True)

    def _run_clarification_phase(self, task_type, task_label, on_proceed):
        if not hasattr(self, '_clarify_llm'):
            self._clarify_llm = OllamaLLM(model="llama3", temperature=0.4)
        dlg = ClarifyDialog(self, task_label=task_label, task_type=task_type, on_proceed=on_proceed)
        def _ask():
            self._emit("_clarify_start", None)
            dlg.start_ai_message_safe()
            time.sleep(0.3)  # Let event loop create the label
            def token_cb(tok):
                dlg.append_ai_token_safe(tok)
            stream_clarifications(self._clarify_llm, task_type, token_cb)
            dlg.end_ai_message_safe()
        threading.Thread(target=_ask, daemon=True).start()

    def _run_clarification_phase_with_cancel(self, task_type, task_label, on_proceed, on_cancel=None):
        if not hasattr(self, '_clarify_llm'):
            self._clarify_llm = OllamaLLM(model="llama3", temperature=0.4)
        dlg = ClarifyDialog(self, task_label=task_label, task_type=task_type, on_proceed=on_proceed, on_cancel=on_cancel)
        def _ask():
            dlg.start_ai_message_safe()
            time.sleep(0.3)  # Let event loop create the label
            def token_cb(tok):
                dlg.append_ai_token_safe(tok)
            stream_clarifications(self._clarify_llm, task_type, token_cb)
            dlg.end_ai_message_safe()
        threading.Thread(target=_ask, daemon=True).start()

    # =========================================================
    # VIEW BUILDERS
    # =========================================================
    def _make_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(20)
        return page, layout

    def _make_header(self, layout, title, subtitle=None):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        h_layout = QVBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 8)
        h_layout.setSpacing(4)
        lbl = QLabel(title)
        lbl.setObjectName("heading")
        h_layout.addWidget(lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("subheading")
            sub.setWordWrap(True)
            h_layout.addWidget(sub)
        layout.addWidget(container)

    # === VIEW 1: PROCESS FILES ===
    def _build_process_view(self):
        page, layout = self._make_page()

        # Hero welcome banner
        hero = QFrame()
        hero.setObjectName("heroBanner")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 24, 28, 24)
        hero_layout.setSpacing(6)
        welcome = QLabel("Welcome back")
        welcome.setObjectName("heroWelcome")
        hero_layout.addWidget(welcome)
        hero_desc = QLabel("Select a file and describe what you need — the AI handles the rest.")
        hero_desc.setObjectName("heroDesc")
        hero_desc.setWordWrap(True)
        hero_layout.addWidget(hero_desc)
        layout.addWidget(hero)

        grid = QGridLayout()
        grid.setSpacing(20)

        # Left card — config
        left_card = Card("Configuration")
        cl = left_card.content_layout()

        lbl = QLabel("Saved Macros")
        lbl.setObjectName("fieldLabel")
        cl.addWidget(lbl)
        self.macro_combo = QComboBox()
        self.macro_combo.addItems(["Custom"] + list(load_macros().keys()))
        self.macro_combo.currentTextChanged.connect(self.load_macro_choice)
        cl.addWidget(self.macro_combo)

        lbl2 = QLabel("AI Instruction")
        lbl2.setObjectName("fieldLabel")
        cl.addWidget(lbl2)
        self.input_instruction = QLineEdit()
        self.input_instruction.setPlaceholderText("e.g., Summarize this document in 3 bullet points")
        cl.addWidget(self.input_instruction)
        save_macro_btn = QPushButton("Save as Macro")
        save_macro_btn.setObjectName("ghost")
        save_macro_btn.clicked.connect(self.save_current_macro)
        cl.addWidget(save_macro_btn, alignment=Qt.AlignmentFlag.AlignRight)

        lbl3 = QLabel("Target File")
        lbl3.setObjectName("fieldLabel")
        cl.addWidget(lbl3)
        file_row = QHBoxLayout()
        self.btn_select = QPushButton("Browse...")
        self.btn_select.clicked.connect(self.select_file)
        file_row.addWidget(self.btn_select)
        self.lbl_file = QLabel("No file selected")
        self.lbl_file.setObjectName("statusText")
        file_row.addWidget(self.lbl_file, 1)
        cl.addLayout(file_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        cl.addWidget(self.progress)

        self.btn_run = QPushButton("Run with AI")
        self.btn_run.setObjectName("primary")
        self.btn_run.setFixedHeight(48)
        self.btn_run.clicked.connect(self.start_processing)
        cl.addWidget(self.btn_run)

        self.process_terminal = self._make_reasoning_section(cl)

        grid.addWidget(left_card, 0, 0)

        # Right card — log
        right_card = Card("Activity Log")
        rl = right_card.content_layout()
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlainText("⚡ System initialized and ready\n")
        rl.addWidget(self.txt_log)
        self._make_download_btn(rl, "process")
        grid.addWidget(right_card, 0, 1)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid, 1)
        return page

    # === VIEW 2: PPT MAKER ===
    def _build_ppt_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Presentation Generator", "AI-powered slide creation with research and structure")

        card = Card()
        cl = card.content_layout()

        lbl = QLabel("Topic")
        lbl.setObjectName("fieldLabel")
        cl.addWidget(lbl)
        self.ppt_topic_entry = QLineEdit()
        self.ppt_topic_entry.setPlaceholderText("e.g., The Future of Renewable Energy")
        cl.addWidget(self.ppt_topic_entry)

        self.ppt_generate_btn = QPushButton("💬  Ask AI & Generate")
        self.ppt_generate_btn.setObjectName("primary")
        self.ppt_generate_btn.setFixedHeight(48)
        self.ppt_generate_btn.clicked.connect(self.start_ppt_generation)
        cl.addWidget(self.ppt_generate_btn)

        self.ppt_terminal = self._make_reasoning_section(cl)

        # Steps
        steps_card = Card()
        sl = steps_card.content_layout()
        self.ppt_step_labels = {}
        for key, text in [("step_1", "Researching Content"), ("step_2", "Structuring Arguments"), ("step_3", "Building .PPTX File")]:
            step = ProgressStep(text)
            sl.addWidget(step)
            self.ppt_step_labels[key] = step
        cl.addWidget(steps_card)

        self.ppt_status_label = QLabel("")
        self.ppt_status_label.setStyleSheet("font-weight: bold; color: #059669;")
        cl.addWidget(self.ppt_status_label)
        self._make_download_btn(cl, "ppt")

        layout.addWidget(card, 1)
        return page

    # === VIEW 3: PDF MAKER ===
    def _build_pdf_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "AI Document Writer", "Generate comprehensive PDFs with AI-powered content")

        card = Card()
        cl = card.content_layout()

        lbl = QLabel("Document Subject")
        lbl.setObjectName("fieldLabel")
        cl.addWidget(lbl)
        self.pdf_topic_entry = QLineEdit()
        self.pdf_topic_entry.setPlaceholderText("e.g., Essay on Quantum Computing")
        cl.addWidget(self.pdf_topic_entry)

        self.pdf_btn = QPushButton("💬  Ask AI & Write")
        self.pdf_btn.setObjectName("primary")
        self.pdf_btn.setFixedHeight(48)
        self.pdf_btn.clicked.connect(self.start_pdf_generation)
        cl.addWidget(self.pdf_btn)

        self.pdf_terminal = self._make_reasoning_section(cl)

        steps_card = Card()
        sl = steps_card.content_layout()
        self.pdf_step_labels = {}
        for key, text in [("step_1", "Generating Content"), ("step_2", "Formatting PDF")]:
            step = ProgressStep(text)
            sl.addWidget(step)
            self.pdf_step_labels[key] = step
        cl.addWidget(steps_card)

        self.pdf_status_label = QLabel("")
        self.pdf_status_label.setStyleSheet("font-weight: bold; color: #059669;")
        cl.addWidget(self.pdf_status_label)
        self._make_download_btn(cl, "pdf")

        layout.addWidget(card, 1)
        return page

    # === VIEW 4: AI ENHANCE ===
    def _build_enhance_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "AI Enhancement Studio", "Improve and polish your documents automatically")

        grid = QGridLayout()
        grid.setSpacing(20)

        # Left — settings
        left_card = Card("Settings")
        cl = left_card.content_layout()

        upload_btn = QPushButton("📂  Upload File")
        upload_btn.clicked.connect(self.select_enhance_file)
        cl.addWidget(upload_btn)
        self.enhance_lbl_file = QLabel("No file selected")
        self.enhance_lbl_file.setObjectName("statusText")
        cl.addWidget(self.enhance_lbl_file)

        lbl = QLabel("Enhancement Options")
        lbl.setObjectName("fieldLabel")
        cl.addWidget(lbl)
        self.enhance_improve_text = QCheckBox("Improve Grammar & Clarity")
        self.enhance_improve_text.setChecked(True)
        cl.addWidget(self.enhance_improve_text)
        self.enhance_auto_format = QCheckBox("Auto-Format Styling")
        cl.addWidget(self.enhance_auto_format)
        self.enhance_add_summaries = QCheckBox("Add Executive Summary")
        cl.addWidget(self.enhance_add_summaries)
        self.enhance_fix_consistency = QCheckBox("Fix Formatting Consistency")
        cl.addWidget(self.enhance_fix_consistency)

        lbl2 = QLabel("Writing Tone")
        lbl2.setObjectName("fieldLabel")
        cl.addWidget(lbl2)
        self.enhance_style = QComboBox()
        self.enhance_style.addItems(["Professional", "Casual", "Academic", "Technical"])
        cl.addWidget(self.enhance_style)

        self.enhance_btn_preview = QPushButton("🔍  Analyze Suggestions")
        self.enhance_btn_preview.setObjectName("ghost")
        self.enhance_btn_preview.clicked.connect(self.preview_enhancements)
        cl.addWidget(self.enhance_btn_preview)
        self.enhance_btn_apply = QPushButton("💬  Ask AI & Enhance")
        self.enhance_btn_apply.setObjectName("primary")
        self.enhance_btn_apply.setFixedHeight(48)
        self.enhance_btn_apply.clicked.connect(self.apply_enhancements)
        cl.addWidget(self.enhance_btn_apply)

        self.enhance_terminal = self._make_reasoning_section(cl)
        grid.addWidget(left_card, 0, 0)

        # Right — output
        right_card = Card("Analysis & Output")
        rl = right_card.content_layout()
        self.enhance_progress = QProgressBar()
        self.enhance_progress.setValue(0)
        self.enhance_progress.setTextVisible(False)
        self.enhance_progress.setFixedHeight(6)
        rl.addWidget(self.enhance_progress)
        self.enhance_status = QLabel("Ready to enhance")
        self.enhance_status.setObjectName("statusText")
        rl.addWidget(self.enhance_status)
        self.enhance_log = QPlainTextEdit()
        rl.addWidget(self.enhance_log)
        self._make_download_btn(rl, "enhance")
        grid.addWidget(right_card, 0, 1)

        layout.addLayout(grid, 1)
        return page

    # === VIEW 5: SMART FILL ===
    def _build_fill_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Smart Fill", "Generate documents from data and templates")

        grid = QGridLayout()
        grid.setSpacing(12)

        card1 = Card("1. Source Data")
        self.txt_data = QPlainTextEdit()
        card1.add_widget(self.txt_data)
        grid.addWidget(card1, 0, 0)

        card2 = Card("2. Template")
        self.txt_template = QPlainTextEdit()
        card2.add_widget(self.txt_template)
        grid.addWidget(card2, 0, 1)

        card3 = Card("3. Generated Output")
        cl3 = card3.content_layout()
        self.txt_ref = QLineEdit()
        self.txt_ref.setPlaceholderText("Style reference (optional)")
        cl3.addWidget(self.txt_ref)
        self.btn_fill = QPushButton("💬  Ask AI & Fill")
        self.btn_fill.setObjectName("primary")
        self.btn_fill.setFixedHeight(48)
        self.btn_fill.clicked.connect(self.run_smart_fill)
        cl3.addWidget(self.btn_fill)
        self.fill_terminal = self._make_reasoning_section(cl3)
        self.txt_fill_result = QPlainTextEdit()
        self.txt_fill_result.setReadOnly(True)
        cl3.addWidget(self.txt_fill_result)
        self._make_download_btn(cl3, "fill")
        grid.addWidget(card3, 0, 2)

        layout.addLayout(grid, 1)
        return page

    # === VIEW 6: RECORDER ===
    def _build_recorder_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Action Replay", "Record and replay desktop macro actions")
        card = Card()
        self.recorder_ui = RecorderTab()
        card.add_widget(self.recorder_ui)
        layout.addWidget(card, 1)
        return page

    # === VIEW 7: WEB SCRAPER ===
    def _build_web_scraper_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Web Scraper Recorder", "Record and replay browser automation")
        card = Card()
        self.web_scraper_ui = WebScraperTab()
        card.add_widget(self.web_scraper_ui)
        layout.addWidget(card, 1)
        return page

    # === VIEW 8: DIRECTORY ===
    def _build_dir_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Directory Generator", "Create project structures from tree descriptions")

        grid = QGridLayout()
        grid.setSpacing(20)

        # Left — input
        left_card = Card("Tree Structure")
        cl = left_card.content_layout()
        cl.addWidget(QLabel("Paste your directory tree structure below:"))
        self.txt_tree = QPlainTextEdit()
        cl.addWidget(self.txt_tree)

        action_row = QHBoxLayout()
        preview_btn = QPushButton("🔍  Preview Tree")
        preview_btn.setObjectName("ghost")
        preview_btn.clicked.connect(self.preview_dir_tree)
        action_row.addWidget(preview_btn)
        copy_btn = QPushButton("📋  Copy Tree")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._copy_dir_preview)
        action_row.addWidget(copy_btn)
        action_row.addStretch()
        self.btn_create_tree = QPushButton("🚀  Build Project")
        self.btn_create_tree.setObjectName("success")
        self.btn_create_tree.clicked.connect(self.generate_tree)
        action_row.addWidget(self.btn_create_tree)
        cl.addLayout(action_row)

        dest_row = QHBoxLayout()
        dest_btn = QPushButton("📁  Select Destination")
        dest_btn.clicked.connect(self.select_target_dir)
        dest_row.addWidget(dest_btn)
        self.lbl_target = QLabel("Current directory")
        self.lbl_target.setObjectName("statusText")
        dest_row.addWidget(self.lbl_target, 1)
        cl.addLayout(dest_row)

        self.dir_progress = QProgressBar()
        self.dir_progress.setValue(0)
        self.dir_progress.setTextVisible(False)
        self.dir_progress.setFixedHeight(6)
        self.dir_progress.hide()
        cl.addWidget(self.dir_progress)
        self.dir_status_lbl = QLabel("Ready to build")
        self.dir_status_lbl.setObjectName("statusText")
        cl.addWidget(self.dir_status_lbl)

        self.dir_terminal = self._make_reasoning_section(cl)
        grid.addWidget(left_card, 0, 0)

        # Right — preview
        right_card = Card("📋 Parsed Preview")
        rl = right_card.content_layout()
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel('Click "Preview Tree" to verify what will be created:'))
        self.dir_count_badge = QLabel("")
        self.dir_count_badge.setStyleSheet("font-weight: bold; color: #2563EB; font-size: 10px;")
        preview_header.addWidget(self.dir_count_badge)
        rl.addLayout(preview_header)

        self.dir_preview_box = QPlainTextEdit()
        self.dir_preview_box.setObjectName("terminal")
        self.dir_preview_box.setReadOnly(True)
        rl.addWidget(self.dir_preview_box)

        self.btn_open_explorer = QPushButton("📂  Open in Explorer")
        self.btn_open_explorer.setEnabled(False)
        self.btn_open_explorer.clicked.connect(self._open_built_dir_in_explorer)
        rl.addWidget(self.btn_open_explorer)

        grid.addWidget(right_card, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid, 1)
        return page

    # === VIEW 9: BATCH OPERATIONS ===
    def _build_batch_view(self):
        page, layout = self._make_page()
        self._make_header(layout, "Batch Operations", "Process an entire folder of documents at once")

        grid = QGridLayout()
        grid.setSpacing(20)

        # Left — config
        left_card = Card("Configuration")
        cl = left_card.content_layout()

        lbl_folder = QLabel("Source Folder")
        lbl_folder.setObjectName("fieldLabel")
        cl.addWidget(lbl_folder)

        folder_row = QHBoxLayout()
        self.batch_folder_btn = QPushButton("Select Folder...")
        self.batch_folder_btn.clicked.connect(self._batch_select_folder)
        folder_row.addWidget(self.batch_folder_btn)
        self.batch_folder_lbl = QLabel("No folder selected")
        self.batch_folder_lbl.setObjectName("statusText")
        folder_row.addWidget(self.batch_folder_lbl, 1)
        cl.addLayout(folder_row)

        lbl_action = QLabel("Action")
        lbl_action.setObjectName("fieldLabel")
        cl.addWidget(lbl_action)
        self.batch_action_combo = QComboBox()
        for key, label in ACTION_LABELS.items():
            self.batch_action_combo.addItem(label, key)
        self.batch_action_combo.currentIndexChanged.connect(self._batch_action_changed)
        cl.addWidget(self.batch_action_combo)

        lbl_instr = QLabel("AI Instruction (for Smart Process)")
        lbl_instr.setObjectName("fieldLabel")
        cl.addWidget(lbl_instr)
        self.batch_instruction = QLineEdit()
        self.batch_instruction.setPlaceholderText("e.g., Fix grammar and make professional")
        self.batch_instruction.setEnabled(False)
        cl.addWidget(self.batch_instruction)

        # File list preview
        lbl_files = QLabel("Files to process")
        lbl_files.setObjectName("fieldLabel")
        cl.addWidget(lbl_files)
        self.batch_file_list = QPlainTextEdit()
        self.batch_file_list.setReadOnly(True)
        self.batch_file_list.setFixedHeight(120)
        self.batch_file_list.setPlaceholderText("Select a folder to see files...")
        cl.addWidget(self.batch_file_list)

        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        self.batch_progress.setTextVisible(False)
        self.batch_progress.setFixedHeight(6)
        cl.addWidget(self.batch_progress)

        self.batch_run_btn = QPushButton("Run Batch")
        self.batch_run_btn.setObjectName("primary")
        self.batch_run_btn.setFixedHeight(48)
        self.batch_run_btn.clicked.connect(self.start_batch)
        cl.addWidget(self.batch_run_btn)

        grid.addWidget(left_card, 0, 0)

        # Right — output
        right_card = Card("Output")
        rl = right_card.content_layout()
        self.batch_status_lbl = QLabel("Ready")
        self.batch_status_lbl.setObjectName("statusText")
        rl.addWidget(self.batch_status_lbl)
        self.batch_terminal = self._make_reasoning_section(rl)
        self.batch_log = QPlainTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setPlaceholderText("Batch results will appear here...")
        rl.addWidget(self.batch_log)
        grid.addWidget(right_card, 0, 1)

        layout.addLayout(grid, 1)
        return page

    # =========================================================
    # LOGIC METHODS (all preserved from original)
    # =========================================================
    def select_file(self):
        file_types = "All Supported (*.docx *.xlsx *.pptx *.pdf)"
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", file_types)
        if path:
            self.selected_file = path
            filename = os.path.basename(path)
            self.lbl_file.setText(filename)
            self.log(f"✓ Selected: {filename}")

    def start_processing(self):
        if not hasattr(self, 'selected_file'):
            self.log("⚠️ Please select a file first")
            return
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Asking AI...")
        self.process_terminal.clear_text()

        def on_answer(user_context):
            instruction = self.input_instruction.text()
            enriched = f"{instruction}\n\nUser preferences: {user_context}" if user_context else instruction
            self._emit("log", "⏳ Processing...")
            self.progress.setRange(0, 0)
            path = self.selected_file

            def _do_process():
                thought_cb = lambda t: self._emit("stream_process", t)
                self._emit("log", f"⚙️ Processing {os.path.basename(path)}...")
                result = None
                try:
                    if path.endswith(".docx"): result = process_word_document(path, enriched, thought_callback=thought_cb)
                    elif path.endswith(".xlsx"): result = process_excel_file(path, enriched, thought_callback=thought_cb)
                    else: result = "Error: Unsupported file type"
                except Exception as e: result = f"Error: {str(e)}"
                self._emit("process_done", result)

            threading.Thread(target=_do_process, daemon=True).start()

        self._run_clarification_phase("word_process", "Smart Process", on_answer)

    def finish_processing(self, result):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.btn_run.setEnabled(True)
        self.btn_run.setText("💬  Ask AI & Run")
        if result and "Error" not in str(result):
            self.log(f"✅ Success! Output: {result}")
            self._enable_download("process", result)
        else:
            self.log(f"❌ {result}")

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.appendPlainText(f"[{timestamp}] {msg}")

    def save_current_macro(self):
        name, ok = QInputDialog.getText(self, "Save Macro", "Macro name:")
        instruction = self.input_instruction.text()
        if ok and name and instruction:
            save_macro(name, instruction)
            self.macro_combo.clear()
            self.macro_combo.addItems(["Custom"] + list(load_macros().keys()))
            self.log(f"💾 Saved macro: {name}")

    def load_macro_choice(self, choice):
        macros = load_macros()
        if choice in macros:
            self.input_instruction.setText(macros[choice])
            self.log(f"📋 Loaded macro: {choice}")

    def start_ppt_generation(self):
        topic = self.ppt_topic_entry.text()
        if not topic: return
        self.ppt_status_label.setText("Asking AI for preferences...")
        self.ppt_generate_btn.setEnabled(False)
        self.ppt_generate_btn.setText("Asking AI...")
        for step in self.ppt_step_labels.values(): step.set_state("pending")
        self.ppt_terminal.clear_text()

        def on_answer(user_context):
            thought_cb = lambda t: self._emit("stream_ppt", t)
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
        self._emit("ppt_progress", (step_key, status))

    def _update_ppt_gui_safe(self, step_key, status):
        if step_key == "final":
            fname = os.path.basename(status) if os.path.isfile(status) else status
            self.ppt_status_label.setText(f"✅ {fname}")
            self.ppt_generate_btn.setEnabled(True)
            self.ppt_generate_btn.setText("💬  Ask AI & Generate")
            self._enable_download("ppt", status)
        elif step_key == "error":
            self.ppt_status_label.setText(f"❌ {status}")
            self.ppt_status_label.setStyleSheet("font-weight: bold; color: #DC2626;")
            self.ppt_generate_btn.setEnabled(True)
            self.ppt_generate_btn.setText("💬  Ask AI & Generate")
        elif step_key in self.ppt_step_labels:
            step = self.ppt_step_labels[step_key]
            if status == "running": step.set_state("active")
            elif status == "done": step.set_state("complete")

    def start_pdf_generation(self):
        topic = self.pdf_topic_entry.text()
        if not topic: return
        self.pdf_status_label.setText("Asking AI for preferences...")
        self.pdf_btn.setEnabled(False)
        self.pdf_btn.setText("Asking AI...")
        for step in self.pdf_step_labels.values(): step.set_state("pending")
        self.pdf_terminal.clear_text()

        def on_answer(user_context):
            thought_cb = lambda t: self._emit("stream_pdf", t)
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
        self._emit("pdf_progress", (step_key, status))

    def _update_pdf_gui_safe(self, step_key, status):
        if step_key == "final":
            fname = os.path.basename(status) if os.path.isfile(status) else status
            self.pdf_status_label.setText(f"✅ {fname}")
            self.pdf_btn.setEnabled(True)
            self.pdf_btn.setText("💬  Ask AI & Write")
            self._enable_download("pdf", status)
        elif step_key == "error":
            self.pdf_status_label.setText(f"❌ {status}")
            self.pdf_status_label.setStyleSheet("font-weight: bold; color: #DC2626;")
            self.pdf_btn.setEnabled(True)
            self.pdf_btn.setText("💬  Ask AI & Write")
        elif step_key in self.pdf_step_labels:
            step = self.pdf_step_labels[step_key]
            if status == "running": step.set_state("active")
            elif status == "done": step.set_state("complete")

    def select_enhance_file(self):
        file_types = "Supported (*.docx *.xlsx *.pptx)"
        path, _ = QFileDialog.getOpenFileName(self, "Select File", "", file_types)
        if path:
            self.enhance_selected_file = path
            filename = os.path.basename(path)
            self.enhance_lbl_file.setText(filename)
            self.enhance_log.appendPlainText(f"✓ Selected: {filename}")

    def preview_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'): return
        self.enhance_log.appendPlainText("\n🔍 Analyzing document...")
        threading.Thread(target=self.thread_preview_enhancements, daemon=True).start()

    def thread_preview_enhancements(self):
        path = self.enhance_selected_file
        try:
            if path.endswith(".docx"): suggestions = suggest_word_improvements(path)
            elif path.endswith(".xlsx"): suggestions = suggest_excel_improvements(path)
            elif path.endswith(".pptx"): suggestions = self.ppt_enricher.get_improvement_suggestions(path)
            else: suggestions = ["Unsupported file type"]
        except Exception as e: suggestions = [f"Error: {str(e)}"]
        self._emit("enhance_suggestions", suggestions)

    @pyqtSlot(str, object)
    def _handle_signal(self, key, data):
        # Extended handler
        if key == "enhance_suggestions":
            self.display_suggestions(data)
            return
        handlers = {
            "process_done": lambda d: self.finish_processing(d),
            "ppt_progress": lambda d: self._update_ppt_gui_safe(d[0], d[1]),
            "pdf_progress": lambda d: self._update_pdf_gui_safe(d[0], d[1]),
            "enhance_done": lambda d: self.finish_enhancement(d),
            "enhance_status": lambda d: self.enhance_status.setText(d),
            "fill_done": lambda d: self.finish_smart_fill(d[0], d[1]),
            "dir_update": lambda d: self._update_dir_ui(d[0], d[1], d[2] if len(d) > 2 else None),
            "ollama_status": lambda d: self.update_ollama_status(d),
            "log": lambda d: self.log(d),
            "stream_process": lambda d: self._stream_to_terminal(self.process_terminal, d),
            "stream_ppt": lambda d: self._stream_to_terminal(self.ppt_terminal, d),
            "stream_pdf": lambda d: self._stream_to_terminal(self.pdf_terminal, d),
            "stream_enhance": lambda d: self._stream_to_terminal(self.enhance_terminal, d),
            "stream_fill": lambda d: self._stream_to_terminal(self.fill_terminal, d),
            "stream_dir": lambda d: self._stream_to_terminal(self.dir_terminal, d),
            "stream_batch": lambda d: self._stream_to_terminal(self.batch_terminal, d),
            "batch_file_status": lambda d: self._batch_update_file(d[0], d[1]),
            "batch_done": lambda d: self.finish_batch(d),
        }
        handler = handlers.get(key)
        if handler:
            handler(data)

    def display_suggestions(self, suggestions):
        self.enhance_log.appendPlainText("\n" + "─" * 40)
        for s in suggestions: self.enhance_log.appendPlainText(f"  • {s}")
        self.enhance_log.appendPlainText("─" * 40)

    def apply_enhancements(self):
        if not hasattr(self, 'enhance_selected_file'): return
        style = self.enhance_style.currentText().lower()
        self.enhance_btn_apply.setEnabled(False)
        self.enhance_btn_apply.setText("Asking AI...")
        self.enhance_progress.setRange(0, 0)
        self.enhance_terminal.clear_text()

        options_snap = {
            'improve_text': self.enhance_improve_text.isChecked(),
            'auto_format': self.enhance_auto_format.isChecked(),
            'add_summaries': self.enhance_add_summaries.isChecked(),
            'fix_consistency': self.enhance_fix_consistency.isChecked(),
            'improve_content': True, 'improve_paragraphs': True
        }

        def on_answer(user_context):
            enriched_style = f"{style} — extra notes: {user_context}" if user_context else style
            threading.Thread(
                target=self.thread_apply_enhancements,
                args=(options_snap, enriched_style),
                daemon=True
            ).start()

        self._run_clarification_phase("enhance", "AI Enhance", on_answer)

    def thread_apply_enhancements(self, options, style):
        path = self.enhance_selected_file
        result = None
        thought_cb = lambda t: self._emit("stream_enhance", t)
        try:
            if path.endswith(".docx"): result = enrich_word_document(path, options, style, thought_callback=thought_cb)
            elif path.endswith(".xlsx"): result = enrich_excel_file(path, options, style, thought_callback=thought_cb)
            elif path.endswith(".pptx"): self.ppt_enricher.enhance_presentation(path, options, style, self.handle_ppt_enhance_progress); return
        except Exception as e: result = f"Error: {str(e)}"
        self._emit("enhance_done", result)

    def handle_ppt_enhance_progress(self, step_key, status):
        if step_key == "final": self._emit("enhance_done", f"✅ {status}")
        elif step_key == "error": self._emit("enhance_done", f"❌ {status}")
        elif step_key == "progress": self._emit("enhance_status", status)

    def finish_enhancement(self, result):
        self.enhance_progress.setRange(0, 100)
        self.enhance_progress.setValue(100)
        self.enhance_btn_apply.setEnabled(True)
        self.enhance_btn_apply.setText("💬  Ask AI & Enhance")
        self.enhance_log.appendPlainText(f"\n{result}")
        self.enhance_status.setText("Complete")
        if result and isinstance(result, str) and os.path.isfile(result):
            self._enable_download("enhance", result)

    def run_smart_fill(self):
        data = self.txt_data.toPlainText().strip()
        template = self.txt_template.toPlainText().strip()
        ref = self.txt_ref.text().strip()
        if not data or not template: return
        self.btn_fill.setEnabled(False)
        self.btn_fill.setText("Asking AI...")
        self.fill_terminal.clear_text()

        def on_answer(user_context):
            threading.Thread(
                target=self.thread_smart_fill,
                args=(data, template, ref, user_context),
                daemon=True
            ).start()

        self._run_clarification_phase("smart_fill", "Smart Fill", on_answer)

    def thread_smart_fill(self, data, template, ref, user_context=""):
        thought_cb = lambda t: self._emit("stream_fill", t)
        enriched_data = f"{data}\n\nUser notes: {user_context}" if user_context else data
        ai_text = smart_fill_content(enriched_data, template, ref, thought_callback=thought_cb)
        filename = f"Generated_Doc_{int(time.time())}.pdf"
        output_path = os.path.join("user_data", filename)
        os.makedirs("user_data", exist_ok=True)
        final_path = create_filled_pdf(ai_text, output_path)
        self._emit("fill_done", (ai_text, final_path))

    def finish_smart_fill(self, text_result, pdf_path):
        self.txt_fill_result.setPlainText(text_result)
        self.btn_fill.setEnabled(True)
        self.btn_fill.setText("💬  Ask AI & Fill")
        if pdf_path and os.path.isfile(str(pdf_path)):
            self._enable_download("fill", pdf_path)

    # ── Directory Logic ──
    def select_target_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Destination")
        if path:
            self.target_dir = path
            self.lbl_target.setText(f".../{os.path.basename(path)}")

    def preview_dir_tree(self):
        text = self.txt_tree.toPlainText().strip()
        if not text: return
        entries = parse_tree_to_list(text)
        if not entries:
            preview = "⚠️  Nothing parsed — check the tree format."
            self.dir_count_badge.setText("")
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
            self.dir_count_badge.setText(f"{total_folders} 📁  {total_files} 📄")

        self.dir_preview_box.setPlainText(preview)

    def _copy_dir_preview(self):
        content = self.dir_preview_box.toPlainText().strip()
        if content:
            QApplication.clipboard().setText(content)

    def generate_tree(self):
        text = self.txt_tree.toPlainText().strip()
        if not text: return
        entries = parse_tree_to_list(text)
        if not entries:
            self.dir_status_lbl.setText("⚠️ Nothing to build — paste a valid directory tree first.")
            self.dir_status_lbl.setStyleSheet("color: #D97706;")
            return

        target = getattr(self, 'target_dir', os.getcwd())
        self.btn_create_tree.setEnabled(False)
        self.btn_create_tree.setText("Asking AI...")
        self.btn_open_explorer.setEnabled(False)
        self.dir_terminal.clear_text()

        def on_answer(user_context):
            self._emit("stream_dir", f"◆ Build started — target: {target}\n◆ Detecting project stack...\n\n")
            self.dir_progress.show()
            self.dir_progress.setRange(0, 0)

            def on_progress(status, msg):
                self._emit("dir_update", (status, msg, target))

            def on_thought(token):
                self._emit("stream_dir", token)

            enriched_tree = f"{text}\n\n# User notes: {user_context}" if user_context else text
            create_directory_from_text(target, enriched_tree, on_progress, thought_callback=on_thought)

        def on_cancel():
            self.btn_create_tree.setEnabled(True)
            self.btn_create_tree.setText("🚀  Build Project")

        self._run_clarification_phase_with_cancel("directory", "Directory Maker", on_answer, on_cancel)

    def _open_built_dir_in_explorer(self):
        path = getattr(self, '_built_dir_path', None)
        if path and os.path.isdir(path):
            import subprocess
            subprocess.Popen(f'explorer "{os.path.normpath(path)}"')

    def _update_dir_ui(self, status, msg, built_path=None):
        self.dir_status_lbl.setText(msg)
        if status == "running":
            self.dir_status_lbl.setStyleSheet("color: #2563EB; font-weight: bold;")
        elif status == "done":
            self.dir_progress.setRange(0, 100)
            self.dir_progress.setValue(100)
            self.dir_progress.hide()
            self.dir_status_lbl.setStyleSheet("color: #059669; font-weight: bold;")
            self.btn_create_tree.setEnabled(True)
            self.btn_create_tree.setText("🚀  Build Project")
            if built_path:
                self._built_dir_path = built_path
            self.btn_open_explorer.setEnabled(True)
            self.btn_open_explorer.setObjectName("success")
            self.btn_open_explorer.style().unpolish(self.btn_open_explorer)
            self.btn_open_explorer.style().polish(self.btn_open_explorer)
        elif status == "error":
            self.dir_progress.setRange(0, 100)
            self.dir_progress.hide()
            self.dir_status_lbl.setStyleSheet("color: #DC2626; font-weight: bold;")
            self.btn_create_tree.setEnabled(True)
            self.btn_create_tree.setText("🚀  Build Project")

    def check_ollama_status(self):
        def check():
            manager = get_ollama_manager()
            is_running = manager.check_ollama_running()
            self._emit("ollama_status", is_running)
        threading.Thread(target=check, daemon=True).start()

    def update_ollama_status(self, is_running):
        if is_running:
            self.status_badge.set_status("success", "Ollama Active")
        else:
            self.status_badge.set_status("error", "Ollama Offline")

    # =========================================================
    # BATCH OPERATIONS LOGIC
    # =========================================================
    def _batch_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._batch_folder = folder
            self.batch_folder_lbl.setText(os.path.basename(folder))
            files = scan_folder(folder)
            if files:
                names = [os.path.basename(f) for f in files]
                self.batch_file_list.setPlainText("\n".join(names))
                self.batch_status_lbl.setText(f"{len(files)} files found")
            else:
                self.batch_file_list.setPlainText("No supported files found.")
                self.batch_status_lbl.setText("No files")

    def _batch_action_changed(self, index):
        action_key = self.batch_action_combo.currentData()
        self.batch_instruction.setEnabled(action_key == "smart_process")

    def start_batch(self):
        if not hasattr(self, '_batch_folder'):
            self.log("Select a folder first")
            return
        action_key = self.batch_action_combo.currentData()
        instruction = self.batch_instruction.text() if action_key == "smart_process" else ""

        self.batch_run_btn.setEnabled(False)
        self.batch_run_btn.setText("Processing...")
        self.batch_terminal.clear_text()
        self.batch_log.clear()
        self.batch_progress.setRange(0, 0)
        self.batch_status_lbl.setText("Running...")

        def status_cb(filepath, status):
            self._emit("batch_file_status", (filepath, status))

        def thought_cb(text):
            self._emit("stream_batch", text)

        def finish_cb(results):
            self._emit("batch_done", results)

        run_batch(
            folder=self._batch_folder,
            action=action_key,
            instruction=instruction,
            status_cb=status_cb,
            thought_cb=thought_cb,
            finish_cb=finish_cb,
        )

    def _batch_update_file(self, filepath, status):
        name = os.path.basename(filepath)
        icon = {"running": "...", "done": "OK", "error": "ERR"}.get(status, "")
        self.batch_log.appendPlainText(f"[{icon}] {name}")

    def finish_batch(self, results):
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(100)
        self.batch_run_btn.setEnabled(True)
        self.batch_run_btn.setText("Run Batch")
        processed = results.get('processed', 0)
        errors = results.get('errors', 0)
        self.batch_status_lbl.setText(f"Done: {processed} processed, {errors} errors")