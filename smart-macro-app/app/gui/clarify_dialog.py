"""
clarify_dialog.py  —  Floating "Ask AI Before You Run" popup dialog.

A CTkToplevel window that appears centered over the main app, streams
clarifying questions from the AI, and calls on_proceed(user_answer)
when the user submits their reply.
"""

import customtkinter as ctk
import threading

_BG      = "#080810"
_AI_CLR  = "#00FF88"
_USR_CLR = "#E2E8F0"
_ACCENT  = "#6366F1"


class ClarifyDialog(ctk.CTkToplevel):
    """
    Floating dialog that:
      1. Streams AI clarifying questions token-by-token (typing effect)
      2. Lets the user type an answer
      3. Calls on_proceed(answer) when user clicks "Proceed ▶"
    """

    def __init__(self, master, task_label: str, on_proceed, **kwargs):
        super().__init__(master, **kwargs)

        self._on_proceed = on_proceed
        self._answer = ""

        # --- Window setup ---
        self.title("💬 AI Clarification")
        self.geometry("560x420")
        self.configure(fg_color=_BG)
        self.resizable(False, False)
        self.grab_set()          # modal — blocks the main window
        self.lift()
        self.after(100, self._center)
        self.protocol("WM_DELETE_WINDOW", self._skip)   # X = skip Q&A

        # --- Build UI ---
        self._build(task_label)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build(self, task_label: str):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(18, 4))

        ctk.CTkLabel(
            hdr, text="🤖  Quick Questions Before I Start",
            font=("Consolas", 13, "bold"), text_color=_AI_CLR, anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            hdr, text=task_label,
            font=("Segoe UI", 11), text_color="#555577", anchor="e"
        ).pack(side="right")

        ctk.CTkFrame(self, height=1, fg_color="#1A1A2E").pack(fill="x", padx=20)

        # Chat scroll area
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", height=220,
            scrollbar_button_color="#1A1A2E",
            scrollbar_button_hover_color="#2A2A4E",
        )
        self._scroll.pack(fill="x", padx=16, pady=(10, 6))
        self._scroll.grid_columnconfigure(0, weight=1)
        self._row = 0

        # Current AI bubble text accumulator
        self._ai_lbl = None
        self._ai_text = ""

        ctk.CTkFrame(self, height=1, fg_color="#1A1A2E").pack(fill="x", padx=20)

        # Input row
        inp = ctk.CTkFrame(self, fg_color="transparent")
        inp.pack(fill="x", padx=16, pady=10)
        inp.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            inp,
            placeholder_text="Type your answer here and press Enter…",
            fg_color="#0D0D1A", border_color="#2A2A4E", border_width=1,
            text_color=_USR_CLR, font=("Segoe UI", 12),
            height=40, corner_radius=8, state="disabled"
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry.bind("<Return>", lambda e: self._on_send())

        self._send_btn = ctk.CTkButton(
            inp, text="Proceed ▶",
            fg_color=_ACCENT, hover_color="#4F52D0",
            text_color="white", font=("Segoe UI", 12, "bold"),
            height=40, width=100, corner_radius=8,
            state="disabled", command=self._on_send
        )
        self._send_btn.grid(row=0, column=1)

        # Skip link
        ctk.CTkButton(
            self, text="Skip Q&A — run with defaults",
            fg_color="transparent", hover_color="#111122",
            text_color="#444466", font=("Segoe UI", 10),
            height=22, command=self._skip
        ).pack(pady=(0, 12))

    # ── Public Streaming API ───────────────────────────────────────────────

    def start_ai_message(self):
        """Begin a new AI bubble (call before first token)."""
        self._ai_text = ""
        self._ai_lbl = ctk.CTkLabel(
            self._scroll,
            text="🤖  ",
            font=("Consolas", 11), text_color=_AI_CLR,
            anchor="w", justify="left", wraplength=460,
        )
        self._ai_lbl.grid(row=self._row, column=0, sticky="ew",
                          padx=(8, 48), pady=(8, 2))
        self._row += 1
        self._scroll._parent_canvas.yview_moveto(1.0)

    def append_ai_token(self, token: str):
        """Append a streaming token to the current AI bubble."""
        self._ai_text += token
        if self._ai_lbl:
            self._ai_lbl.configure(text="🤖  " + self._ai_text)
            self._scroll._parent_canvas.yview_moveto(1.0)

    def end_ai_message(self):
        """Finalise the AI bubble and unlock the input field."""
        self._ai_lbl = None
        self._entry.configure(state="normal")
        self._send_btn.configure(state="normal")
        self._entry.focus()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _center(self):
        """Centre the dialog over the master window."""
        try:
            self.update_idletasks()
            mw = self.master.winfo_width()
            mh = self.master.winfo_height()
            mx = self.master.winfo_rootx()
            my = self.master.winfo_rooty()
            dw, dh = 560, 420
            x = mx + (mw - dw) // 2
            y = my + (mh - dh) // 2
            self.geometry(f"{dw}x{dh}+{x}+{y}")
        except Exception:
            pass

    def _on_send(self):
        answer = self._entry.get().strip()
        self._entry.configure(state="disabled")
        self._send_btn.configure(state="disabled", text="Running…")
        self._answer = answer
        self.after(400, self._finish)

    def _skip(self):
        """User closed or skipped — proceed with empty answer."""
        self._answer = ""
        self._finish()

    def _finish(self):
        answer = self._answer
        cb = self._on_proceed
        self.grab_release()
        self.destroy()
        # Fire the callback AFTER the dialog is gone
        threading.Thread(target=lambda: cb(answer), daemon=True).start()
