"""
Web Scraper Tab UI Component
=============================
CustomTkinter interface for web scraper recorder.

Provides controls for:
- Recording browser interactions via Playwright
- Playing back saved recordings
- Managing saved recordings
"""

import customtkinter as ctk
import os
from tkinter import messagebox
from app.engine.web_recorder import (
    WebRecorder, 
    WebPlayer, 
    get_saved_recordings, 
    delete_recording,
    RECORDINGS_DIR
)


class WebScraperTab(ctk.CTkFrame):
    """
    Web Scraper Recorder UI Component.
    
    Layout:
    - Left sidebar: Control buttons (Record, Stop, Play)
    - Right main area: Status, recordings list, management
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # State
        self.recorder = WebRecorder()
        self.player = WebPlayer()
        
        # Layout: Grid Configuration (2 Columns)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- LEFT SIDEBAR (Controls) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Web Scraper", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        # Big Action Buttons
        self.btn_record = ctk.CTkButton(
            self.sidebar_frame, 
            text="● RECORD", 
            command=self.start_recording,
            fg_color="#e74c3c", 
            hover_color="#c0392b", 
            height=40
        )
        self.btn_record.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_stop = ctk.CTkButton(
            self.sidebar_frame, 
            text="■ STOP", 
            command=self.stop_action,
            state="disabled",
            fg_color="#95a5a6", 
            height=40
        )
        self.btn_stop.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_play = ctk.CTkButton(
            self.sidebar_frame, 
            text="▶ PLAY", 
            command=self.start_playback,
            fg_color="#2ecc71", 
            hover_color="#27ae60", 
            height=40
        )
        self.btn_play.grid(row=3, column=0, padx=20, pady=10)
        
        # --- RIGHT MAIN AREA ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # 1. Status Dashboard
        self.status_frame = ctk.CTkFrame(self.main_frame, height=100)
        self.status_frame.pack(fill="x", pady=(0, 15))
        
        self.lbl_status = ctk.CTkLabel(
            self.status_frame, 
            text="Status: Idle", 
            font=ctk.CTkFont(size=16)
        )
        self.lbl_status.pack(side="left", padx=20, pady=10)
        
        # 2. Instructions Card
        self.info_frame = ctk.CTkFrame(self.main_frame)
        self.info_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            self.info_frame, 
            text="How to Use", 
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        instructions = (
            "1. Click RECORD to start browser recording\n"
            "2. Browser opens automatically - perform your actions\n"
            "3. Click STOP when finished\n"
            "4. Recording auto-saves with timestamp\n"
            "5. Select recording and click PLAY to replay"
        )
        
        ctk.CTkLabel(
            self.info_frame, 
            text=instructions,
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(0, 10))
        
        # 3. File Management Card
        self.files_frame = ctk.CTkFrame(self.main_frame)
        self.files_frame.pack(fill="x", pady=(0, 0))
        
        ctk.CTkLabel(
            self.files_frame, 
            text="Saved Recordings", 
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=15, pady=10)
        
        self.combo_files = ctk.CTkComboBox(
            self.files_frame, 
            values=self.get_recordings()
        )
        self.combo_files.pack(padx=20, pady=(0, 10), fill="x")
        
        # Button row
        button_row = ctk.CTkFrame(self.files_frame, fg_color="transparent")
        button_row.pack(fill="x", padx=20, pady=(0, 15))
        
        self.btn_refresh = ctk.CTkButton(
            button_row, 
            text="🔄 Refresh", 
            command=self.refresh_file_list,
            fg_color="#3498db",
            width=100
        )
        self.btn_refresh.pack(side="left", padx=(0, 10))
        
        self.btn_open_folder = ctk.CTkButton(
            button_row, 
            text="📁 Open Folder", 
            command=self.open_recordings_folder,
            fg_color="#9b59b6",
            width=120
        )
        self.btn_open_folder.pack(side="left", padx=(0, 10))
        
        self.btn_delete = ctk.CTkButton(
            button_row, 
            text="🗑️ Delete", 
            command=self.delete_recording,
            fg_color="#e74c3c",
            width=100
        )
        self.btn_delete.pack(side="right")
        
        # Initial file list load
        self.refresh_file_list()
    
    # --- LOGIC METHODS ---
    
    def get_recordings(self) -> list[str]:
        """Get list of saved recordings."""
        recordings = get_saved_recordings()
        return recordings if recordings else ["No Recordings"]
    
    def refresh_file_list(self):
        """Refresh the recordings dropdown."""
        recordings = self.get_recordings()
        self.combo_files.configure(values=recordings)
        if recordings and recordings[0] != "No Recordings":
            self.combo_files.set(recordings[0])
        else:
            self.combo_files.set("No Recordings")
    
    def set_status(self, text: str, color: str = "white"):
        """Update status label with color."""
        self.lbl_status.configure(text=f"Status: {text}", text_color=color)
    
    def start_recording(self):
        """Start web scraper recording."""
        if self.recorder.recording or self.player.playing:
            return
        
        success = self.recorder.start_recording()
        
        if success:
            self.set_status("RECORDING... (Browser should open)", "#e74c3c")
            self.btn_record.configure(state="disabled")
            self.btn_play.configure(state="disabled")
            self.btn_stop.configure(state="normal", fg_color="#c0392b")
        else:
            self.set_status("Failed to start recording", "#e74c3c")
            messagebox.showerror(
                "Recording Error",
                "Failed to start Playwright codegen.\n\n"
                "Make sure Playwright is installed:\n"
                "1. pip install playwright\n"
                "2. playwright install chromium"
            )
    
    def stop_action(self):
        """Stop recording or playback."""
        if self.recorder.recording:
            self._stop_recording()
        elif self.player.playing:
            self._stop_playback()
    
    def _stop_recording(self):
        """Stop recording and save."""
        success = self.recorder.stop_recording()
        
        if success:
            # Auto-save with timestamp
            saved_path = self.recorder.save_recording()
            
            if saved_path:
                filename = os.path.basename(saved_path).replace(".py", "")
                self.set_status(f"Saved: {filename}", "#2ecc71")
                self.refresh_file_list()
                self.combo_files.set(filename)
            else:
                self.set_status("Recording stopped (save failed)", "#f39c12")
        else:
            self.set_status("Recording stopped (no script captured)", "#f39c12")
        
        # Reset buttons
        self.btn_record.configure(state="normal")
        self.btn_play.configure(state="normal")
        self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
    
    def _stop_playback(self):
        """Stop playback."""
        self.player.stop_playback()
        self.set_status("Playback stopped", "#f39c12")
        
        # Reset buttons
        self.btn_record.configure(state="normal")
        self.btn_play.configure(state="normal")
        self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
    
    def start_playback(self):
        """Start playback of selected recording."""
        filename = self.combo_files.get()
        
        if filename == "No Recordings":
            messagebox.showinfo("No Recordings", "No recordings available to play.")
            return
        
        script_path = os.path.join(RECORDINGS_DIR, f"{filename}.py")
        
        if not os.path.exists(script_path):
            messagebox.showerror("File Not Found", f"Recording not found: {filename}")
            self.refresh_file_list()
            return
        
        # Update UI before starting
        self.set_status("PLAYING...", "#2ecc71")
        self.btn_record.configure(state="disabled")
        self.btn_play.configure(state="disabled")
        self.btn_stop.configure(state="normal", fg_color="#27ae60")
        
        # Start playback with callbacks
        success = self.player.play_recording(
            script_path,
            on_complete=self._on_playback_complete,
            on_error=self._on_playback_error
        )
        
        if not success:
            self.set_status("Failed to start playback", "#e74c3c")
            self.btn_record.configure(state="normal")
            self.btn_play.configure(state="normal")
            self.btn_stop.configure(state="disabled", fg_color="#95a5a6")
    
    def _on_playback_complete(self):
        """Callback when playback completes successfully."""
        self.after(0, lambda: self.set_status("Playback completed", "#2ecc71"))
        self.after(0, lambda: self.btn_record.configure(state="normal"))
        self.after(0, lambda: self.btn_play.configure(state="normal"))
        self.after(0, lambda: self.btn_stop.configure(state="disabled", fg_color="#95a5a6"))
    
    def _on_playback_error(self, error_msg: str):
        """Callback when playback encounters an error."""
        self.after(0, lambda: self.set_status("Playback error", "#e74c3c"))
        self.after(0, lambda: self.btn_record.configure(state="normal"))
        self.after(0, lambda: self.btn_play.configure(state="normal"))
        self.after(0, lambda: self.btn_stop.configure(state="disabled", fg_color="#95a5a6"))
        self.after(0, lambda: messagebox.showerror("Playback Error", error_msg))
    
    def delete_recording(self):
        """Delete selected recording."""
        filename = self.combo_files.get()
        
        if filename == "No Recordings":
            return
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete recording '{filename}'?\n\nThis cannot be undone."
        )
        
        if confirm:
            success = delete_recording(filename)
            
            if success:
                self.set_status(f"Deleted: {filename}", "#e74c3c")
                self.refresh_file_list()
            else:
                messagebox.showerror("Delete Failed", f"Could not delete: {filename}")
    
    def open_recordings_folder(self):
        """Open recordings folder in file explorer."""
        if not os.path.exists(RECORDINGS_DIR):
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
        
        # Open folder in OS file explorer
        if os.name == 'nt':  # Windows
            os.startfile(RECORDINGS_DIR)
        else:  # macOS/Linux
            import subprocess
            subprocess.Popen(['xdg-open', RECORDINGS_DIR])
