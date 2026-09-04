# ui/widgets/chat_bubble.py
"""Modern chat bubble with light/dark awareness."""

import re
import customtkinter as ctk

from ui.theme import colors

MAX_WRAPLENGTH = 460
_CODE_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)


def _split_content(text: str):
    pos = 0
    for match in _CODE_BLOCK_RE.finditer(text):
        if match.start() > pos:
            chunk = text[pos : match.start()]
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
        c = colors()
        color = c["user_bubble"] if role == "user" else c["avatar_assistant"]
        super().__init__(
            master,
            width=size,
            height=size,
            corner_radius=size // 2,
            fg_color=color,
        )
        self.grid_propagate(False)
        self.pack_propagate(False)

        label_text = "👤" if role == "user" else "✦"
        text_color = "#FFFFFF" if role == "user" else c["text"]
        ctk.CTkLabel(
            self,
            text=label_text,
            font=ctk.CTkFont(size=12),
            text_color=text_color,
        ).place(relx=0.5, rely=0.5, anchor="center")


class _CodeBlock(ctk.CTkFrame):
    def __init__(self, master, language: str, code: str):
        c = colors()
        super().__init__(master, fg_color=c["code_body"], corner_radius=12)

        header = ctk.CTkFrame(
            self, fg_color=c["code_header"], corner_radius=0, height=28
        )
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=language or "code",
            text_color=c["code_lang"],
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=12)

        self.copy_btn = ctk.CTkButton(
            header,
            text="Copy",
            width=52,
            height=20,
            corner_radius=6,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=c["surface_alt"],
            text_color=c["code_lang"],
            command=lambda: self._copy(code),
        )
        self.copy_btn.pack(side="right", padx=8, pady=4)

        body = ctk.CTkTextbox(
            self,
            fg_color=c["code_body"],
            text_color=c["code_text"],
            font=ctk.CTkFont(family="Menlo", size=12),
            wrap="none",
            corner_radius=0,
            height=self._estimate_height(code),
            activate_scrollbars=True,
            border_width=0,
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
        self,
        master,
        role: str = "assistant",
        text: str = "",
        show_avatar: bool = True,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.role = role
        self.text = text
        self._typing_job = None
        self._dot_labels = []
        self._dot_state = 0
        self._stream_label = None

        c = colors()
        is_user = role == "user"
        bubble_color = c["user_bubble"] if is_user else c["assistant_bubble"]
        text_color = c["user_text"] if is_user else c["assistant_text"]

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", anchor="e" if is_user else "w")

        self.bubble = ctk.CTkFrame(
            row,
            fg_color=bubble_color,
            corner_radius=20,
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
        # Re-read theme in case mode changed mid-session
        c = colors()
        is_user = self.role == "user"
        self._text_color = c["user_text"] if is_user else c["assistant_text"]
        bubble_color = c["user_bubble"] if is_user else c["assistant_bubble"]
        self.bubble.configure(fg_color=bubble_color)

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
        c = colors()
        is_user = self.role == "user"
        self._text_color = c["user_text"] if is_user else c["assistant_text"]
        self.bubble.configure(
            fg_color=c["user_bubble"] if is_user else c["assistant_bubble"]
        )

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
        self._stream_label.configure(
            text=text if text else " ",
            text_color=self._text_color,
        )

    def update_text(self, text: str, finalize: bool = False):
        self.text = text
        if finalize:
            self._render(text)
        else:
            self._render_plain(text)

    def start_typing(self):
        self.stop_typing()
        self._clear_content()
        c = colors()
        self.bubble.configure(fg_color=c["assistant_bubble"])

        dots_row = ctk.CTkFrame(self._content_holder, fg_color="transparent")
        dots_row.pack(anchor="w", pady=(1, 0))

        self._dot_labels = []
        for _ in range(3):
            dot = ctk.CTkLabel(
                dots_row,
                text="•",
                text_color=c["text_secondary"],
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
        c = colors()
        for i, dot in enumerate(self._dot_labels):
            active = i == self._dot_state
            dot.configure(
                text_color=c["text"] if active else c["text_secondary"]
            )
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