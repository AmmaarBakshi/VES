"""
Theme Manager — Smart Macro Station
Centralized theming with Light/Dark mode support via QSS.
"""

import os

LIGHT = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F8FAFC",
    "bg_card": "#FFFFFF",
    "bg_input": "#F1F5F9",
    "bg_hover": "#E2E8F0",
    "accent": "#2563EB",
    "accent_hover": "#1D4ED8",
    "accent_light": "#DBEAFE",
    "success": "#059669",
    "success_light": "#D1FAE5",
    "danger": "#DC2626",
    "danger_light": "#FEE2E2",
    "warning": "#D97706",
    "warning_light": "#FEF3C7",
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "text_tertiary": "#64748B",
    "text_disabled": "#94A3B8",
    "text_on_accent": "#FFFFFF",
    "border": "#E2E8F0",
    "border_focus": "#2563EB",
    "shadow": "rgba(0,0,0,0.06)",
    "terminal_bg": "#1E293B",
    "terminal_text": "#10B981",
}

DARK = {
    "bg_primary": "#0F172A",
    "bg_secondary": "#1E293B",
    "bg_card": "#1E293B",
    "bg_input": "#0F172A",
    "bg_hover": "#334155",
    "accent": "#3B82F6",
    "accent_hover": "#2563EB",
    "accent_light": "#1E3A5F",
    "success": "#10B981",
    "success_light": "#064E3B",
    "danger": "#EF4444",
    "danger_light": "#7F1D1D",
    "warning": "#F59E0B",
    "warning_light": "#78350F",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "text_tertiary": "#64748B",
    "text_disabled": "#475569",
    "text_on_accent": "#FFFFFF",
    "border": "#334155",
    "border_focus": "#3B82F6",
    "shadow": "rgba(0,0,0,0.3)",
    "terminal_bg": "#020617",
    "terminal_text": "#10B981",
}


class ThemeManager:
    """Manages Light/Dark theming via QSS stylesheets."""

    _current = "light"
    _colors = LIGHT

    @classmethod
    def colors(cls):
        return cls._colors

    @classmethod
    def is_dark(cls):
        return cls._current == "dark"

    @classmethod
    def toggle(cls, app=None):
        cls._current = "dark" if cls._current == "light" else "light"
        cls._colors = DARK if cls._current == "dark" else LIGHT
        if app:
            cls.apply(app)

    @classmethod
    def set_theme(cls, theme: str, app=None):
        cls._current = theme
        cls._colors = DARK if theme == "dark" else LIGHT
        if app:
            cls.apply(app)

    @classmethod
    def apply(cls, app):
        """Load and apply the appropriate QSS file."""
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        qss_file = "styles_dark.qss" if cls._current == "dark" else "styles_light.qss"
        qss_path = os.path.join(gui_dir, qss_file)
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"[Theme] QSS file not found: {qss_path}")
