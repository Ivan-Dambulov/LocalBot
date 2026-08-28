# ui/widgets/chat_view.py
import customtkinter as ctk

from ui.theme import colors, paint_scrollable
from ui.widgets.chat_bubble import ChatBubble


class ChatView(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        c = colors()
        kwargs.setdefault("fg_color", c["bg"])
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)

        self._bubbles = []
        self._typing_bubble = None
        self._streaming_bubble = None
        self._pad = dict(padx=6, pady=4)
        paint_scrollable(self, c["bg"])

    def apply_theme(self):
        c = colors()
        paint_scrollable(self, c["bg"])

    def add_user_message(self, text: str) -> ChatBubble:
        bubble = ChatBubble(self, role="user", text=text)
        bubble.pack(fill="x", **self._pad)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def add_assistant_message(self, text: str = "") -> ChatBubble:
        bubble = ChatBubble(self, role="assistant", text=text)
        bubble.pack(fill="x", **self._pad)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()
        return bubble

    def add_system_message(self, text: str) -> ChatBubble:
        return self.add_assistant_message(text)

    def show_typing_indicator(self) -> ChatBubble:
        self.hide_typing_indicator()
        bubble = ChatBubble(self, role="assistant", text="")
        bubble.pack(fill="x", **self._pad)
        bubble.start_typing()
        self._typing_bubble = bubble
        self._scroll_to_bottom()
        return bubble

    def hide_typing_indicator(self):
        if self._typing_bubble is not None:
            self._typing_bubble.stop_typing()
            self._typing_bubble.destroy()
            self._typing_bubble = None

    def start_streaming_message(self) -> ChatBubble:
        if self._typing_bubble is not None:
            bubble = self._typing_bubble
            bubble.stop_typing()
            self._typing_bubble = None
        else:
            bubble = ChatBubble(self, role="assistant", text="")
            bubble.pack(fill="x", **self._pad)
            self._bubbles.append(bubble)

        self._streaming_bubble = bubble
        return bubble

    def update_streaming_message(self, full_text: str):
        if self._streaming_bubble is None:
            self.start_streaming_message()
        self._streaming_bubble.update_text(full_text, finalize=False)
        self._scroll_to_bottom()

    def append_stream_token(self, token: str):
        if self._streaming_bubble is None:
            self.start_streaming_message()
        current = self._streaming_bubble.text + token
        self.update_streaming_message(current)

    def finalize_streaming_message(self):
        if self._streaming_bubble is not None:
            self._streaming_bubble.update_text(
                self._streaming_bubble.text, finalize=True
            )
            if self._streaming_bubble not in self._bubbles:
                self._bubbles.append(self._streaming_bubble)
            self._streaming_bubble = None
        self._scroll_to_bottom()

    def clear(self):
        self.hide_typing_indicator()
        self._streaming_bubble = None
        for bubble in self._bubbles:
            try:
                bubble.destroy()
            except Exception:
                pass
        self._bubbles = []

    def rebuild_messages(self, messages: list):
        """
        Wipe all bubbles and recreate from stored messages.
        Call this after every theme change so colors match Light/Dark.
        """
        self.clear()
        self.apply_theme()
        for m in messages:
            role = m.get("role") or "assistant"
            text = m.get("content") or ""
            if not text.strip():
                continue
            if role == "user":
                self.add_user_message(text)
            else:
                self.add_assistant_message(text)

    def _scroll_to_bottom(self):
        def _do_scroll():
            try:
                self._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass

        self.after(20, _do_scroll)