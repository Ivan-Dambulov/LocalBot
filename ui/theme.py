"""Simple light/dark color tokens for LocalBot UI."""

from __future__ import annotations

import customtkinter as ctk


def is_dark() -> bool:
    return ctk.get_appearance_mode() == "Dark"


def colors() -> dict:
    if is_dark():
        return {
            "bg": "#1C1C1E",
            "sidebar": "#2C2C2E",
            "header": "#2C2C2E",
            "surface": "#3A3A3C",
            "surface_alt": "#48484A",
            "border": "#3A3A3C",
            "text": "#F5F5F7",
            "text_secondary": "#AEAEB2",
            "accent": "#0A84FF",
            "accent_hover": "#409CFF",
            "danger": "#FF453A",
            "danger_hover": "#FF6961",
            "input_bg": "#2C2C2E",
            "chip": "#3A3A3C",
            "user_bubble": "#0A84FF",
            "assistant_bubble": "#3A3A3C",
            "user_text": "#FFFFFF",
            "assistant_text": "#F5F5F7",
            "code_header": "#2C2C2E",
            "code_body": "#1C1C1E",
            "code_text": "#F5F5F7",
            "code_lang": "#8E8E93",
            "avatar_assistant": "#48484A",
            "success": "#30D158",
            "warning": "#FF9F0A",
        }
    return {
        "bg": "#F5F5F7",
        "sidebar": "#FFFFFF",
        "header": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_alt": "#EBEBF0",
        "border": "#D1D1D6",
        "text": "#1C1C1E",
        "text_secondary": "#8E8E93",
        "accent": "#0A84FF",
        "accent_hover": "#0071E3",
        "danger": "#FF3B30",
        "danger_hover": "#D70015",
        "input_bg": "#FFFFFF",
        "chip": "#EBEBF0",
        "user_bubble": "#0A84FF",
        "assistant_bubble": "#E8E8ED",
        "user_text": "#FFFFFF",
        "assistant_text": "#1C1C1E",
        "code_header": "#E5E5EA",
        "code_body": "#F2F2F7",
        "code_text": "#1C1C1E",
        "code_lang": "#8E8E93",
        "avatar_assistant": "#D1D1D6",
        "success": "#34C759",
        "warning": "#FF9500",
    }


def paint_scrollable(frame: ctk.CTkScrollableFrame, bg: str) -> None:
    """Force CTkScrollableFrame + its internal canvas to one solid color."""
    frame.configure(fg_color=bg)
    try:
        frame._parent_frame.configure(fg_color=bg)
    except Exception:
        pass
    try:
        # Tk canvas uses the same hex on modern platforms
        frame._parent_canvas.configure(bg=bg, highlightthickness=0)
    except Exception:
        pass
    try:
        frame._scrollbar.configure(
            fg_color=bg,
            button_color=bg,
            button_hover_color=bg,
        )
    except Exception:
        pass