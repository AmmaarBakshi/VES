"""
Batch Tab UI — Smart Macro Station
====================================
Premium animated tab for processing entire folders of files with AI.

Layout fix — Start button is always visible:
  • Left panel uses grid rows so the button stays anchored at bottom
  • Compact hero section to save vertical space
  • Right panel: scrollable file queue + reasoning terminal
"""

import customtkinter as ctk
from tkinter import filedialog
import os

from app.engine.batch_engine import (
    scan_folder, run_batch, ACTION_LABELS,
)

# ── Design tokens (mirror app_window.py) ────────────────────────────────────
DESIGN = {
    "bg_primary":       "#0A0A0F",
    "bg_secondary":     "#13131A",
    "bg_tertiary":      "#1A1A24",
    "bg_input":         "#1F1F2E",
    "bg_hover":         "#252534",
    "accent_primary":   "#6366F1",
    "accent_secondary": "#8B5CF6",
    "success":          "#10B981",
    "warning":          "#F59E0B",
    "danger":           "#EF4444",
    "info":             "#3B82F6",
    "text_primary":     "#F8FAFC",
    "text_secondary":   "#94A3B8",
    "text_tertiary":    "#64748B",
    "text_disabled":    "#475569",
    "border_subtle":    "#1E293B",
    "border_medium":    "#334155",
    "font_body":        "Segoe UI",
    "font_mono":        "Consolas",
}

EXT_ICONS = {
    ".docx": "📄", ".doc": "📄",
    ".xlsx": "📊", ".xls": "📊", ".csv": "📊",
    ".pptx": "🖼️", ".ppt": "🖼️",
    ".pdf":  "🗒️",
}

STATUS_CFG = {
    "pending":  ("⏳", DESIGN["text_disabled"],  "Pending"),
    "running":  ("⚙️", DESIGN["accent_primary"], "Processing…"),
    "done":     ("✅", DESIGN["success"],         "Done"),
    "error":    ("❌", DESIGN["danger"],           "Error"),
    "skipped":  ("⏭️", DESIGN["warning"],         "Skipped"),
}


# ── File queue row ───────────────────────────────────────────────────────────

class FileRow(ctk.CTkFrame):
    def __init__(self, master, filepath: str, idx: int, **kwargs):
        super().__init__(
            master,
            fg_color=DESIGN["bg_input"] if idx % 2 == 0 else DESIGN["bg_secondary"],
            corner_radius=8,
            height=44,
            **kwargs,
        )
        self.pack_propagate(False)
        ext  = os.path.splitext(filepath)[1].lower()
        icon = EXT_ICONS.get(ext, "📁")
        name = os.path.basename(filepath)

        self._status_lbl = ctk.CTkLabel(
            self, text="⏳", font=("Segoe UI", 15),
            text_color=DESIGN["text_disabled"], width=34,
        )
        self._status_lbl.pack(side="left", padx=(8, 2))

        ctk.CTkLabel(
            self, text=icon, font=("Segoe UI", 13),
            text_color=DESIGN["text_secondary"], width=26,
        ).pack(side="left", padx=(0, 6))

        self._name_lbl = ctk.CTkLabel(
            self, text=name,
            font=(DESIGN["font_body"], 12),
            text_color=DESIGN["text_secondary"],
            anchor="w",
        )
        self._name_lbl.pack(side="left", fill="x", expand=True)

        self._state_lbl = ctk.CTkLabel(
            self, text="Pending",
            font=(DESIGN["font_body"], 11),
            text_color=DESIGN["text_disabled"], width=90,
        )
        self._state_lbl.pack(side="right", padx=(0, 10))

    def set_status(self, status: str):
        icon, color, label = STATUS_CFG.get(status, ("❓", DESIGN["text_disabled"], status))
        self._status_lbl.configure(text=icon, text_color=color)
        self._state_lbl.configure(text=label, text_color=color)
        if status == "running":
            self._name_lbl.configure(text_color=DESIGN["text_primary"])
        elif status == "done":
            self._name_lbl.configure(text_color=DESIGN["success"])


# ── Main Batch Tab ───────────────────────────────────────────────────────────

class BatchTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._folder    = ""
        self._file_rows: dict[str, FileRow] = {}
        self._running   = False
        self._done_count = 0

        self._build_ui()

    # ────────────────────────────────────────────────────────────────────────
    # UI BUILD
    # ────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Compact header ────────────────────────────────────────────────
        hero = ctk.CTkFrame(self, fg_color="transparent")
        hero.pack(fill="x", pady=(0, 12))

        title_row = ctk.CTkFrame(hero, fg_color="transparent")
        title_row.pack()

        icon_bg = ctk.CTkFrame(
            title_row, width=48, height=48, corner_radius=24,
            fg_color=DESIGN["bg_tertiary"],
            border_width=2, border_color=DESIGN["accent_primary"],
        )
        icon_bg.pack(side="left", padx=(0, 14))
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="⚡", font=("Segoe UI", 22)).place(relx=0.5, rely=0.5, anchor="center")

        title_text = ctk.CTkFrame(title_row, fg_color="transparent")
        title_text.pack(side="left")
        ctk.CTkLabel(
            title_text, text="Batch Processor",
            font=(DESIGN["font_body"], 24, "bold"),
            text_color=DESIGN["text_primary"], anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_text,
            text="Select a folder · pick an action · AI processes every file automatically",
            font=(DESIGN["font_body"], 12),
            text_color=DESIGN["text_tertiary"], anchor="w",
        ).pack(anchor="w")

        # ── Two-column body ───────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    # ── LEFT PANEL ────────────────────────────────────────────────────────

    def _build_left(self, parent):
        """
        Uses grid rows inside the card so the Start button is
        ALWAYS visible at the bottom regardless of window height.
        """
        card = ctk.CTkFrame(
            parent,
            fg_color=DESIGN["bg_tertiary"],
            corner_radius=12,
            border_width=1,
            border_color=DESIGN["border_subtle"],
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        # Card uses grid internally: rows 0-4 are content, row 5 is the button
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(3, weight=1)   # action list gets the stretch

        pad = {"padx": 20}

        # ── Row 0: Folder picker ─────────────────────────────────────────
        folder_section = ctk.CTkFrame(card, fg_color="transparent")
        folder_section.grid(row=0, column=0, sticky="ew", pady=(18, 0), **pad)

        ctk.CTkLabel(
            folder_section, text="📂  Target Folder",
            font=(DESIGN["font_body"], 12, "bold"),
            text_color=DESIGN["text_secondary"], anchor="w",
        ).pack(fill="x", pady=(0, 6))

        folder_row = ctk.CTkFrame(
            folder_section, fg_color=DESIGN["bg_input"],
            corner_radius=8, height=50,
        )
        folder_row.pack(fill="x")
        folder_row.pack_propagate(False)

        ctk.CTkButton(
            folder_row, text="Browse",
            fg_color=DESIGN["accent_primary"],
            hover_color=DESIGN["accent_secondary"],
            text_color="white",
            font=(DESIGN["font_body"], 12, "bold"),
            corner_radius=6, height=34, width=90,
            command=self._pick_folder,
        ).pack(side="left", padx=8, pady=8)

        self._folder_lbl = ctk.CTkLabel(
            folder_row, text="No folder selected",
            font=(DESIGN["font_body"], 11),
            text_color=DESIGN["text_disabled"], anchor="w",
        )
        self._folder_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # File count
        self._count_lbl = ctk.CTkLabel(
            folder_section, text="",
            font=(DESIGN["font_body"], 11),
            text_color=DESIGN["text_tertiary"], anchor="w",
        )
        self._count_lbl.pack(fill="x", pady=(4, 0))

        # ── Divider ──────────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color=DESIGN["border_subtle"]).grid(
            row=1, column=0, sticky="ew", pady=14, **pad
        )

        # ── Row 2: Action label ──────────────────────────────────────────
        ctk.CTkLabel(
            card, text="Action",
            font=(DESIGN["font_body"], 12, "bold"),
            text_color=DESIGN["text_secondary"], anchor="w",
        ).grid(row=2, column=0, sticky="ew", **pad)

        # ── Row 3: Action radio buttons (scrollable if needed) ───────────
        action_frame = ctk.CTkFrame(card, fg_color="transparent")
        action_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0), **pad)

        self._action_var = ctk.StringVar(value="enhance_docs")

        action_info = {
            "enhance_docs":     ("✨", "AI Enhance",      "Improve grammar, clarity & formatting"),
            "format_excel":     ("📊", "Format Excel/CSV", "Headers, borders, auto column widths"),
            "smart_process":    ("⚙️", "Smart Process",    "Custom AI instruction on each file"),
            "generate_summary": ("📝", "Generate Summary", "Write an AI summary .txt per file"),
        }

        for key, (icon, title, subtitle) in action_info.items():
            row_f = ctk.CTkFrame(action_frame, fg_color=DESIGN["bg_input"], corner_radius=8, height=52)
            row_f.pack(fill="x", pady=3)
            row_f.pack_propagate(False)

            rb = ctk.CTkRadioButton(
                row_f, text="",
                variable=self._action_var, value=key,
                fg_color=DESIGN["accent_primary"],
                hover_color=DESIGN["accent_secondary"],
                border_color=DESIGN["border_medium"],
                width=24,
                command=self._on_action_change,
            )
            rb.pack(side="left", padx=(10, 4), pady=8)

            text_col = ctk.CTkFrame(row_f, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True, pady=6)
            ctk.CTkLabel(
                text_col,
                text=f"{icon}  {title}",
                font=(DESIGN["font_body"], 12, "bold"),
                text_color=DESIGN["text_primary"], anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                text_col,
                text=subtitle,
                font=(DESIGN["font_body"], 10),
                text_color=DESIGN["text_tertiary"], anchor="w",
            ).pack(anchor="w")

        # ── Custom instruction (smart_process only) ──────────────────────
        self._instr_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        ctk.CTkLabel(
            self._instr_frame,
            text="AI Instruction",
            font=(DESIGN["font_body"], 11, "bold"),
            text_color=DESIGN["text_secondary"], anchor="w",
        ).pack(fill="x", pady=(8, 4))
        self._instr_entry = ctk.CTkEntry(
            self._instr_frame,
            placeholder_text="e.g., Summarize in 3 bullet points",
            fg_color=DESIGN["bg_input"],
            border_color=DESIGN["border_subtle"],
            border_width=1, corner_radius=8, height=38,
            font=(DESIGN["font_body"], 12),
            text_color=DESIGN["text_primary"],
        )
        self._instr_entry.pack(fill="x")
        # hidden by default
        self._instr_frame.pack_forget()

        # ── Divider ──────────────────────────────────────────────────────
        ctk.CTkFrame(card, height=1, fg_color=DESIGN["border_subtle"]).grid(
            row=4, column=0, sticky="ew", pady=12, **pad
        )

        # ── Row 5: START BUTTON — always pinned to bottom ────────────────
        btn_section = ctk.CTkFrame(card, fg_color="transparent")
        btn_section.grid(row=5, column=0, sticky="ew", pady=(0, 18), **pad)

        self._run_btn = ctk.CTkButton(
            btn_section,
            text="⚡  Start Batch Processing",
            fg_color=DESIGN["accent_primary"],
            hover_color=DESIGN["accent_secondary"],
            text_color="white",
            font=(DESIGN["font_body"], 14, "bold"),
            corner_radius=10,
            height=50,
            command=self._start_batch,
        )
        self._run_btn.pack(fill="x")

        # Summary + open-folder (appear after run)
        self._summary_lbl = ctk.CTkLabel(
            btn_section, text="",
            font=(DESIGN["font_body"], 12),
            text_color=DESIGN["success"],
        )
        self._summary_lbl.pack(pady=(8, 0))

        self._open_btn = ctk.CTkButton(
            btn_section,
            text="📂  Open Output Folder",
            fg_color=DESIGN["bg_input"],
            hover_color=DESIGN["bg_hover"],
            border_width=1,
            border_color=DESIGN["border_subtle"],
            text_color=DESIGN["text_secondary"],
            font=(DESIGN["font_body"], 12),
            height=36, corner_radius=8,
            command=self._open_folder,
        )
        # shown only after batch completes

    # ── RIGHT PANEL ───────────────────────────────────────────────────────

    def _build_right(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=DESIGN["bg_tertiary"],
            corner_radius=12,
            border_width=1,
            border_color=DESIGN["border_subtle"],
        )
        card.grid(row=0, column=1, sticky="nsew")
        card.grid_rowconfigure(1, weight=1)   # terminal gets expand
        card.grid_columnconfigure(0, weight=1)

        pad = {"padx": 20}

        # ── Progress bar ──────────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(card, fg_color="transparent")
        prog_frame.grid(row=0, column=0, sticky="ew", pady=(16, 0), **pad)

        queue_hdr = ctk.CTkFrame(prog_frame, fg_color="transparent")
        queue_hdr.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            queue_hdr, text="📋  File Queue",
            font=(DESIGN["font_body"], 13, "bold"),
            text_color=DESIGN["text_primary"],
        ).pack(side="left")
        self._count_badge = ctk.CTkLabel(
            queue_hdr, text="",
            font=(DESIGN["font_body"], 11),
            text_color=DESIGN["text_tertiary"],
        )
        self._count_badge.pack(side="right")

        self._progress = ctk.CTkProgressBar(
            prog_frame,
            progress_color=DESIGN["accent_primary"],
            fg_color=DESIGN["bg_input"],
            corner_radius=4, height=6,
        )
        self._progress.set(0)
        self._progress.pack(fill="x", pady=(0, 8))

        # Scrollable file list
        self._queue_scroll = ctk.CTkScrollableFrame(
            prog_frame,
            fg_color=DESIGN["bg_input"],
            corner_radius=8,
            border_width=1,
            border_color=DESIGN["border_subtle"],
            height=200,
        )
        self._queue_scroll.pack(fill="x")

        self._queue_empty_lbl = ctk.CTkLabel(
            self._queue_scroll,
            text="Select a folder to see files here",
            font=(DESIGN["font_body"], 12),
            text_color=DESIGN["text_disabled"],
        )
        self._queue_empty_lbl.pack(pady=24)

        # ── Reasoning Terminal ─────────────────────────────────────────
        term_frame = ctk.CTkFrame(card, fg_color="transparent")
        term_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 16), **pad)
        term_frame.grid_rowconfigure(1, weight=1)
        term_frame.grid_columnconfigure(0, weight=1)

        terminal_hdr = ctk.CTkFrame(term_frame, fg_color="transparent")
        terminal_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkLabel(
            terminal_hdr, text="🤖  Live Reasoning",
            font=(DESIGN["font_mono"], 11, "bold"),
            text_color=DESIGN["accent_primary"],
        ).pack(side="left")
        ctk.CTkButton(
            terminal_hdr, text="🗑 Clear",
            fg_color="transparent",
            hover_color=DESIGN["bg_hover"],
            text_color=DESIGN["text_disabled"],
            font=(DESIGN["font_body"], 11),
            height=24, width=60,
            command=self._clear_terminal,
        ).pack(side="right")

        self._terminal = ctk.CTkTextbox(
            term_frame,
            font=(DESIGN["font_mono"], 11),
            fg_color="#050508",
            text_color="#00FF88",
            border_width=1,
            border_color=DESIGN["border_subtle"],
            corner_radius=8,
            state="disabled",
            wrap="word",
        )
        self._terminal.grid(row=1, column=0, sticky="nsew")

    # ────────────────────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ────────────────────────────────────────────────────────────────────────

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select folder to batch process")
        if not folder:
            return
        self._folder = folder
        short = folder if len(folder) <= 42 else "…" + folder[-39:]
        self._folder_lbl.configure(text=short, text_color=DESIGN["text_primary"])
        files = scan_folder(folder)
        self._populate_queue(files)

    def _populate_queue(self, files: list):
        for w in self._queue_scroll.winfo_children():
            w.destroy()
        self._file_rows.clear()
        self._summary_lbl.configure(text="")
        self._open_btn.pack_forget()
        self._progress.set(0)

        if not files:
            self._count_lbl.configure(
                text="  No supported files found",
                text_color=DESIGN["warning"],
            )
            self._count_badge.configure(text="0 files")
            lbl = ctk.CTkLabel(
                self._queue_scroll,
                text="No supported files (.docx .xlsx .csv .pptx .pdf)",
                font=(DESIGN["font_body"], 12),
                text_color=DESIGN["text_disabled"],
            )
            lbl.pack(pady=24)
            return

        n = len(files)
        self._count_lbl.configure(
            text=f"  {n} file{'s' if n != 1 else ''} ready",
            text_color=DESIGN["text_tertiary"],
        )
        self._count_badge.configure(text=f"{n} files")

        for idx, fp in enumerate(files):
            row = FileRow(self._queue_scroll, fp, idx)
            row.pack(fill="x", pady=(0, 3))
            self._file_rows[fp] = row

    def _on_action_change(self):
        if self._action_var.get() == "smart_process":
            self._instr_frame.pack(fill="x", pady=(8, 0))
        else:
            self._instr_frame.pack_forget()

    def _start_batch(self):
        if self._running:
            return
        if not self._folder or not self._file_rows:
            self._log("⚠️  Please select a folder with supported files first.\n")
            return

        action = self._action_var.get()
        instruction = (
            self._instr_entry.get().strip() if action == "smart_process" else ""
        )
        if action == "smart_process" and not instruction:
            self._log("⚠️  Please enter an AI instruction for Smart Process mode.\n")
            return

        self._running = True
        self._done_count = 0
        self._run_btn.configure(state="disabled", text="⚙️  Processing…")
        self._open_btn.pack_forget()
        self._summary_lbl.configure(text="")
        self._progress.set(0)

        for row in self._file_rows.values():
            row.set_status("pending")

        total = len(self._file_rows)

        def status_cb(filepath, status):
            self.after(0, lambda fp=filepath, s=status: self._update_row(fp, s, total))

        def thought_cb(text):
            self.after(0, lambda t=text: self._log(t))

        def finish_cb(results):
            self.after(0, lambda r=results: self._on_done(r))

        run_batch(
            folder=self._folder,
            action=action,
            instruction=instruction,
            status_cb=status_cb,
            thought_cb=thought_cb,
            finish_cb=finish_cb,
        )

    def _update_row(self, filepath, status, total):
        row = self._file_rows.get(filepath)
        if row:
            row.set_status(status)
        if status in ("done", "error", "skipped"):
            self._done_count += 1
            self._progress.set(self._done_count / total if total else 0)

    def _on_done(self, results):
        self._running = False
        self._run_btn.configure(state="normal", text="⚡  Start Batch Processing")
        self._progress.set(1.0)

        processed = results.get("processed", 0)
        errors    = results.get("errors", 0)
        color = DESIGN["success"] if errors == 0 else DESIGN["warning"]
        self._summary_lbl.configure(
            text=f"✅ {processed} processed   ❌ {errors} errors",
            text_color=color,
        )
        if self._folder:
            self._open_btn.pack(fill="x", pady=(6, 0))

    def _open_folder(self):
        if self._folder and os.path.exists(self._folder):
            os.startfile(self._folder)

    # ── Terminal helpers ─────────────────────────────────────────────────

    def _log(self, text: str):
        self._terminal.configure(state="normal")
        self._terminal.insert("end", text)
        self._terminal.see("end")
        self._terminal.configure(state="disabled")

    def _clear_terminal(self):
        self._terminal.configure(state="normal")
        self._terminal.delete("0.0", "end")
        self._terminal.configure(state="disabled")
