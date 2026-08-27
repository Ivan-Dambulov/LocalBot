# ui/widgets/chat_bubble.py
"""
Modern chat bubble – soft, clean, ChatGPT / Claude inspired.
"""

import re
import customtkinter as ctk

# ---------------------------------------------------------------------------
# Refined light theme
# ---------------------------------------------------------------------------
USER_BUBBLE_COLOR = "#0A84FF"          # slightly richer blue
ASSISTANT_BUBBLE_COLOR = "#F2F2F7"
BACKGROUND_COLOR = "#FFFFFF"

USER_TEXT_COLOR = "#FFFFFF"
ASSISTANT_TEXT_COLOR = "#1C1C1E"

CODE_HEADER_COLOR = "#EBEBF0"
CODE_BODY_COLOR = "#F7F7F9"
CODE_TEXT_COLOR = "#1C1C1E"
CODE_LANG_COLOR = "#8E8E93"

AVATAR_USER_COLOR = "#0A84FF"
AVATAR_ASSISTANT_COLOR = "#E5E5EA"

MAX_WRAPLENGTH = 460

_CODE_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)


def _split_content(text: str):
    pos = 0
    for match in _CODE_BLOCK_RE.finditer(text):
        if match.start() > pos:
            chunk = text[pos:match.start()]
            if chunk.strip():
                yield ("text", chunk.strip())
        lang = (match.group(1) or "plaintext").strip()
        code = match.group(2).rstrip("\n")
        yield ("code", lang, code)
        pos = match.end()
    if pos < len(text):
        chunk = text[pos:]
        if chunk.strip():
            yield ("text", chunk.strip())


class _Avatar(ctk.CTkFrame):
    def __init__(self, master, role: str, size: int = 28):
        color = AVATAR_USER_COLOR if role == "user" else AVATAR_ASSISTANT_COLOR
        super().__init__(
            master, width=size, height=size,
            corner_radius=size // 2, fg_color=color,
        )
        self.grid_propagate(False)
        self.pack_propagate(False)

        label_text = "👤" if role == "user" else "✦"
        text_color = "#FFFFFF" if role == "user" else "#3A3A3C"
        ctk.CTkLabel(
            self, text=label_text,
            font=ctk.CTkFont(size=12),
            text_color=text_color,
        ).place(relx=0.5, rely=0.5, anchor="center")


class _CodeBlock(ctk.CTkFrame):
    def __init__(self, master, language: str, code: str):
        super().__init__(master, fg_color=CODE_BODY_COLOR, corner_radius=12)

        header = ctk.CTkFrame(
            self, fg_color=CODE_HEADER_COLOR, corner_radius=0, height=28
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text=language or "code",
            text_color=CODE_LANG_COLOR,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=12)

        self.copy_btn = ctk.CTkButton(
            header, text="Copy", width=52, height=20, corner_radius=6,
            font=ctk.CTkFont(size=11), fg_color="transparent",
            hover_color="#D1D1D6", text_color=CODE_LANG_COLOR,
            command=lambda: self._copy(code),
        )
        self.copy_btn.pack(side="right", padx=8, pady=4)

        body = ctk.CTkTextbox(
            self, fg_color=CODE_BODY_COLOR, text_color=CODE_TEXT_COLOR,
            font=ctk.CTkFont(family="Menlo", size=12),
            wrap="none", corner_radius=0,
            height=self._estimate_height(code),
            activate_scrollbars=True, border_width=0,
        )
        body.pack(fill="x", padx=2, pady=(0, 2))
        body.insert("1.0", code)
        body.configure(state="disabled")

    @staticmethod
    def _estimate_height(code: str) -> int:
        lines = code.count("\n") + 1
        return min(max(lines, 1) * 18 + 14, 280)

    def _copy(self, code: str):
        self.clipboard_clear()
        self.clipboard_append(code)
        original = self.copy_btn.cget("text")
        self.copy_btn.configure(text="Copied")
        self.after(1100, lambda: self.copy_btn.configure(text=original))


class ChatBubble(ctk.CTkFrame):
    def __init__(
        self, master, role: str = "assistant", text: str = "",
        show_avatar: bool = True, **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.role = role
        self.text = text
        self._typing_job = None
        self._dot_labels = []
        self._dot_state = 0
        self._stream_label = None

        is_user = role == "user"
        bubble_color = USER_BUBBLE_COLOR if is_user else ASSISTANT_BUBBLE_COLOR
        text_color = USER_TEXT_COLOR if is_user else ASSISTANT_TEXT_COLOR

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", anchor="e" if is_user else "w")

        self.bubble = ctk.CTkFrame(
            row, fg_color=bubble_color, corner_radius=20,
        )

        if is_user:
            self.bubble.pack(side="right", padx=(72, 6), pady=3)
            if show_avatar:
                _Avatar(row, "user").pack(side="right", padx=(2, 2), pady=4)
        else:
            if show_avatar:
                _Avatar(row, "assistant").pack(side="left", padx=(2, 2), pady=4)
            self.bubble.pack(side="left", padx=(6, 72), pady=3)

        self._text_color = text_color
        self._content_holder = ctk.CTkFrame(self.bubble, fg_color="transparent")
        self._content_holder.pack(padx=16, pady=11, fill="x")

        if text:
            self._render(text)

    def _clear_content(self):
        for child in self._content_holder.winfo_children():
            child.destroy()
        self._stream_label = None

    def _render(self, text: str):
        self._clear_content()
        chunks = list(_split_content(text)) or [("text", text)]
        for chunk in chunks:
            if chunk[0] == "text":
                lbl = ctk.CTkLabel(
                    self._content_holder,
                    text=chunk[1],
                    text_color=self._text_color,
                    font=ctk.CTkFont(size=14),
                    justify="left",
                    anchor="w",
                    wraplength=MAX_WRAPLENGTH,
                )
                lbl.pack(fill="x", anchor="w", pady=(0, 1))
            else:
                _, lang, code = chunk
                block = _CodeBlock(self._content_holder, lang, code)
                block.pack(fill="x", pady=(6, 2))

    def _render_plain(self, text: str):
        if self._stream_label is None:
            self._stream_label = ctk.CTkLabel(
                self._content_holder,
                text=" ",
                text_color=self._text_color,
                font=ctk.CTkFont(size=14),
                justify="left",
                anchor="w",
                wraplength=MAX_WRAPLENGTH,
            )
            self._stream_label.pack(fill="x", anchor="w")
        self._stream_label.configure(text=text if text else " ")

    def update_text(self, text: str, finalize: bool = False):
        self.text = text
        if finalize:
            self._render(text)
        else:
            self._render_plain(text)

    def start_typing(self):
        """Small modern three-dot indicator."""
        self.stop_typing()
        self._clear_content()

        dots_row = ctk.CTkFrame(self._content_holder, fg_color="transparent")
        dots_row.pack(anchor="w", pady=(1, 0))

        self._dot_labels = []
        for _ in range(3):
            dot = ctk.CTkLabel(
                dots_row,
                text="•",
                text_color="#AEAEB2",
                font=ctk.CTkFont(size=10),
                width=9,
                height=11,
            )
            dot.pack(side="left", padx=1)
            self._dot_labels.append(dot)

        self._animate_typing()

    def _animate_typing(self):
        if not self._dot_labels:
            return
        for i, dot in enumerate(self._dot_labels):
            active = i == self._dot_state
            dot.configure(text_color="#1C1C1E" if active else "#C7C7CC")
        self._dot_state = (self._dot_state + 1) % 3
        self._typing_job = self.after(300, self._animate_typing)

    def stop_typing(self):
        if self._typing_job is not None:
            try:
                self.after_cancel(self._typing_job)
            except Exception:
                pass
            self._typing_job = None
        self._dot_labels = []