"""
Premium UI Components

Beautiful, reusable components with smooth animations and modern design.
"""

import customtkinter as ctk
from typing import Optional, Callable


class PremiumButton(ctk.CTkButton):
    """
    Enhanced button with gradient background and smooth hover effects.
    """
    
    def __init__(self, master, text="", command=None, style="primary", icon=None, **kwargs):
        # Style presets
        styles = {
            "primary": {
                "fg_color": ("#3B82F6", "#2563EB"),
                "hover_color": ("#2563EB", "#1E40AF"),
                "text_color": "#F8FAFC",
                "font": ("Segoe UI", 15, "bold"),
                "corner_radius": 10,
                "height": 48
            },
            "success": {
                "fg_color": ("#10B981", "#059669"),
                "hover_color": ("#059669", "#047857"),
                "text_color": "#F8FAFC",
                "font": ("Segoe UI", 15, "bold"),
                "corner_radius": 10,
                "height": 48
            },
            "secondary": {
                "fg_color": "transparent",
                "hover_color": ("#334155", "#475569"),
                "border_width": 2,
                "border_color": ("#3B82F6", "#3B82F6"),
                "text_color": "#3B82F6",
                "font": ("Segoe UI", 14, "bold"),
                "corner_radius": 10,
                "height": 44
            },
            "danger": {
                "fg_color": ("#EF4444", "#DC2626"),
                "hover_color": ("#DC2626", "#B91C1C"),
                "text_color": "#F8FAFC",
                "font": ("Segoe UI", 15, "bold"),
                "corner_radius": 10,
                "height": 48
            }
        }
        
        # Get style config
        style_config = styles.get(style, styles["primary"])
        
        # Merge with kwargs
        final_kwargs = {**style_config, **kwargs}
        
        super().__init__(master, text=text, command=command, **final_kwargs)


class PremiumCard(ctk.CTkFrame):
    """
    Elevated card container with shadow effect.
    """
    
    def __init__(self, master, title=None, **kwargs):
        default_kwargs = {
            "corner_radius": 16,
            "fg_color": ("#1E293B", "#1E293B"),
            "border_width": 1,
            "border_color": ("#334155", "#334155")
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)
        
        # Add title if provided
        if title:
            title_label = ctk.CTkLabel(
                self,
                text=title,
                font=("Segoe UI", 18, "bold"),
                text_color="#F8FAFC"
            )
            title_label.pack(anchor="w", padx=24, pady=(20, 10))


class PremiumInput(ctk.CTkEntry):
    """
    Beautiful input field with focus glow effect.
    """
    
    def __init__(self, master, placeholder="", icon=None, **kwargs):
        default_kwargs = {
            "corner_radius": 10,
            "border_width": 2,
            "height": 48,
            "font": ("Segoe UI", 14),
            "fg_color": ("#1E293B", "#1E293B"),
            "border_color": ("#334155", "#334155"),
            "text_color": "#F8FAFC",
            "placeholder_text_color": "#64748B"
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        if placeholder:
            final_kwargs["placeholder_text"] = placeholder
        
        super().__init__(master, **final_kwargs)


class StatusBadge(ctk.CTkFrame):
    """
    Pill-shaped status indicator with animated dot.
    """
    
    def __init__(self, master, text="Status", status="success", **kwargs):
        default_kwargs = {
            "corner_radius": 999,
            "fg_color": "transparent",
            "border_width": 2
        }
        
        # Status colors
        status_colors = {
            "success": {"border": "#10B981", "text": "#10B981", "dot": "#10B981"},
            "warning": {"border": "#F59E0B", "text": "#F59E0B", "dot": "#F59E0B"},
            "error": {"border": "#EF4444", "text": "#EF4444", "dot": "#EF4444"},
            "info": {"border": "#3B82F6", "text": "#3B82F6", "dot": "#3B82F6"}
        }
        
        colors = status_colors.get(status, status_colors["info"])
        default_kwargs["border_color"] = colors["border"]
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)
        
        # Dot indicator
        dot_label = ctk.CTkLabel(
            self,
            text="●",
            font=("Segoe UI", 16),
            text_color=colors["dot"]
        )
        dot_label.pack(side="left", padx=(12, 4))
        
        # Status text
        text_label = ctk.CTkLabel(
            self,
            text=text,
            font=("Segoe UI", 13, "bold"),
            text_color=colors["text"]
        )
        text_label.pack(side="left", padx=(0, 12))
    
    def update_status(self, text, status="success"):
        """Update badge text and color"""
        status_colors = {
            "success": {"border": "#10B981", "text": "#10B981", "dot": "#10B981"},
            "warning": {"border": "#F59E0B", "text": "#F59E0B", "dot": "#F59E0B"},
            "error": {"border": "#EF4444", "text": "#EF4444", "dot": "#EF4444"},
            "info": {"border": "#3B82F6", "text": "#3B82F6", "dot": "#3B82F6"}
        }
        
        colors = status_colors.get(status, status_colors["info"])
        self.configure(border_color=colors["border"])
        
        # Update children
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkLabel):
                if widget.cget("text") == "●":
                    widget.configure(text_color=colors["dot"])
                else:
                    widget.configure(text=text, text_color=colors["text"])


class SectionHeader(ctk.CTkFrame):
    """
    Section header with icon and title.
    """
    
    def __init__(self, master, title="", icon="", subtitle="", **kwargs):
        default_kwargs = {
            "fg_color": "transparent"
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)
        
        # Icon + Title container
        header_container = ctk.CTkFrame(self, fg_color="transparent")
        header_container.pack(fill="x", pady=(0, 8))
        
        if icon:
            icon_label = ctk.CTkLabel(
                header_container,
                text=icon,
                font=("Segoe UI", 24)
            )
            icon_label.pack(side="left", padx=(0, 12))
        
        # Title
        title_label = ctk.CTkLabel(
            header_container,
            text=title,
            font=("Segoe UI", 22, "bold"),
            text_color="#F8FAFC"
        )
        title_label.pack(side="left")
        
        # Subtitle
        if subtitle:
            subtitle_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=("Segoe UI", 13),
                text_color="#94A3B8"
            )
            subtitle_label.pack(anchor="w")


class PremiumCheckbox(ctk.CTkCheckBox):
    """
    Enhanced checkbox with better styling.
    """
    
    def __init__(self, master, text="", **kwargs):
        default_kwargs = {
            "corner_radius": 6,
            "border_width": 2,
            "checkbox_width": 24,
            "checkbox_height": 24,
            "font": ("Segoe UI", 14),
            "text_color": "#F8FAFC",
            "fg_color": "#3B82F6",
            "hover_color": "#2563EB",
            "border_color": "#334155"
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, text=text, **final_kwargs)


class PremiumProgress(ctk.CTkProgressBar):
    """
    Animated progress bar with gradient.
    """
    
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 999,
            "height": 8,
            "border_width": 0,
            "fg_color": ("#334155", "#334155"),
            "progress_color": ("#3B82F6", "#2563EB")
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)


class GradientFrame(ctk.CTkFrame):
    """
    Frame with gradient background effect (simulated with colors).
    """
    
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 16,
            "fg_color": ("#1E40AF", "#1E3A8A"),
            "border_width": 0
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)


class IconButton(ctk.CTkButton):
    """
    Circular or square icon button.
    """
    
    def __init__(self, master, icon="", command=None, **kwargs):
        default_kwargs = {
            "text": icon,
            "width": 44,
            "height": 44,
            "corner_radius": 10,
            "fg_color": "transparent",
            "hover_color": ("#334155", "#475569"),
            "font": ("Segoe UI", 18),
            "border_width": 2,
            "border_color": ("#334155", "#334155")
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, command=command, **final_kwargs)


class PremiumTextbox(ctk.CTkTextbox):
    """
    Enhanced textbox with better styling.
    """
    
    def __init__(self, master, **kwargs):
        default_kwargs = {
            "corner_radius": 12,
            "border_width": 2,
            "border_color": ("#334155", "#334155"),
            "fg_color": ("#1E293B", "#1E293B"),
            "text_color": "#F8FAFC",
            "font": ("Consolas", 13)
        }
        
        final_kwargs = {**default_kwargs, **kwargs}
        super().__init__(master, **final_kwargs)
