"""
ai_chat_panel.py  —  Conversational AI Chat Widget for Smart Macro Station.

Provides a ChatGPT-style Q&A panel embedded in each tab.
  - AI messages appear in matrix-green on the left.
  - User replies appear in white on the right.
  - Input bar stays disabled until the AI has asked a question.
  - on_user_send(text) callback is fired when user hits Send.
"""

import customtkinter as ctk
from tkinter import END
import threading

# ── Design tokens (mirrors the main DESIGN dict) ──────────────────────────
_BG_CHAT    = "#080810"   # slightly lighter than terminal
_AI_COLOR   = "#00FF88"   # matrix-green — AI bubbles
_USER_COLOR = "#E2E8F0"   # near-white — user bubbles
_ACCENT     = "#6366F1"   # indigo — send button


class AIChatPanel(ctk.CTkFrame):
    """
    A compact conversational chat panel.

    Usage
    -----
    panel = AIChatPanel(parent, on_user_send=my_callback)
    panel.pack(fill="x")

    panel.start_ai_message()          # begin a streamed AI message
    panel.append_ai_token("Hello ")   # call repeatedly as tokens arrive
    panel.end_ai_message()            # finalise and enable the input bar

    panel.add_user_message("7 slides, professional tone")  # echo user reply
    panel.set_input_enabled(False)    # lock while AI thinks
    panel.clear()                     # reset for next run
    """

    def __init__(self, master, on_user_send=None, **kwargs):
        defaults = {
            "fg_color": _BG_CHAT,
            "corner_radius": 10,
            "border_width": 1,
        }
        defaults.update(kwargs)
        super().__init__(master, **defaults)

        self._on_user_send = on_user_send
        self._ai_bubble = None   # current streaming bubble widget
        self._ai_text   = ""     # accumulated text for current AI turn

        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # Header row
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(
            hdr, text="💬  Chat with AI",
            font=("Consolas", 11, "bold"), text_color=_AI_COLOR, anchor="w"
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="🗑 Clear", fg_color="transparent",
            hover_color="#1A1A2E", text_color="#555577",
            font=("Segoe UI", 10), height=20, width=55,
            command=self.clear
        ).pack(side="right")

        # Scrollable message area
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", height=180,
            scrollbar_button_color="#1A1A2E",
            scrollbar_button_hover_color="#2A2A4E",
        )
        self._scroll.pack(fill="x", padx=8, pady=(0, 6))
        self._scroll.grid_columnconfigure(0, weight=1)
        self._msg_row = 0

        # Divider
        ctk.CTkFrame(self, height=1, fg_color="#1A1A2E").pack(fill="x", padx=8)

        # Input row
        input_row = ctk.CTkFrame(self, fg_color="transparent")
        input_row.pack(fill="x", padx=8, pady=6)
        input_row.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Type your answer here...",
            fg_color="#0D0D1A", border_color="#2A2A4E", border_width=1,
            text_color=_USER_COLOR, font=("Segoe UI", 12),
            height=36, corner_radius=8, state="disabled"
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry.bind("<Return>", self._on_enter)

        self._send_btn = ctk.CTkButton(
            input_row, text="Send ▶",
            fg_color=_ACCENT, hover_color="#4F52D0",
            text_color="white", font=("Segoe UI", 12, "bold"),
            height=36, width=80, corner_radius=8,
            state="disabled", command=self._on_send
        )
        self._send_btn.grid(row=0, column=1)

    # ── Public API ─────────────────────────────────────────────────────────

    def start_ai_message(self):
        """Call once to begin a new streamed AI message bubble."""
        self._ai_text = ""
        self._ai_bubble = self._make_bubble(
            text="", side="left", color=_AI_COLOR, prefix="🤖  "
        )

    def append_ai_token(self, token: str):
        """Append a streaming token to the current AI bubble."""
        if self._ai_bubble is None:
            self.start_ai_message()
        self._ai_text += token
        self._ai_bubble.configure(text="🤖  " + self._ai_text)
        self._scroll._parent_canvas.yview_moveto(1.0)

    def end_ai_message(self):
        """Finalise current AI bubble and unlock the input bar."""
        self._ai_bubble = None
        self.set_input_enabled(True)

    def add_user_message(self, text: str):
        """Render a user reply bubble (right-aligned, white)."""
        self._make_bubble(text=text, side="right", color=_USER_COLOR, prefix="You:  ")
        self.set_input_enabled(False)

    def add_system_message(self, text: str):
        """Render a small grey system/status note."""
        lbl = ctk.CTkLabel(
            self._scroll, text=text,
            font=("Consolas", 10), text_color="#4A4A6A",
            anchor="center", wraplength=400
        )
        lbl.grid(row=self._msg_row, column=0, sticky="ew", pady=(4, 2), padx=12)
        self._msg_row += 1
        self._scroll._parent_canvas.yview_moveto(1.0)

    def set_input_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._entry.configure(state=state)
        self._send_btn.configure(state=state)
        if enabled:
            self._entry.focus()

    def clear(self):
        """Remove all chat messages and reset state."""
        for widget in self._scroll.winfo_children():
            widget.destroy()
        self._msg_row = 0
        self._ai_bubble = None
        self._ai_text = ""
        self.set_input_enabled(False)

    def get_and_clear_input(self) -> str:
        """Return current entry text and clear it."""
        text = self._entry.get().strip()
        self._entry.delete(0, END)
        return text

    # ── Private Helpers ────────────────────────────────────────────────────

    def _make_bubble(self, text: str, side: str, color: str, prefix: str = "") -> ctk.CTkLabel:
        """Create a styled message bubble in the scroll area."""
        anchor = "w" if side == "left" else "e"
        padx   = (8, 48) if side == "left" else (48, 8)

        lbl = ctk.CTkLabel(
            self._scroll,
            text=prefix + text,
            font=("Consolas", 11),
            text_color=color,
            anchor=anchor,
            justify="left" if side == "left" else "right",
            wraplength=420,
        )
        lbl.grid(row=self._msg_row, column=0, sticky="ew",
                 padx=padx, pady=(6, 2))
        self._msg_row += 1
        self._scroll._parent_canvas.yview_moveto(1.0)
        return lbl

    def _on_enter(self, event=None):
        self._on_send()

    def _on_send(self):
        text = self.get_and_clear_input()
        if not text:
            return
        self.add_user_message(text)
        if self._on_user_send:
            threading.Thread(
                target=self._on_user_send, args=(text,), daemon=True
            ).start()
