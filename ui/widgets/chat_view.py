# ui/widgets/chat_view.py
"""
Scrollable conversation view made of ChatBubble widgets, replacing the old
single CTkTextbox chat log.
"""

import customtkinter as ctk

from ui.widgets.chat_bubble import ChatBubble, BACKGROUND_COLOR


class ChatView(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", BACKGROUND_COLOR)
        kwargs.setdefault("corner_radius", 12)
        super().__init__(master, **kwargs)

        self._bubbles = []
        self._typing_bubble = None
        self._streaming_bubble = None

        # Give bubbles some breathing room from the scrollable frame edges.
        self._pad = dict(padx=6, pady=4)

    # ------------------------------------------------------------------
    # Adding messages
    # ------------------------------------------------------------------
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
        # Rendered like an assistant bubble; kept as a separate method so
        # callers can style/filter system notices differently later.
        return self.add_assistant_message(text)

    # ------------------------------------------------------------------
    # Typing indicator
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def start_streaming_message(self) -> ChatBubble:
        """Call once, right before the first token arrives. Reuses the
        typing-indicator bubble if one is showing, so the dots morph
        directly into text instead of a new bubble popping in."""
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
        """Update the in-progress assistant bubble with the latest
        accumulated text (call with the full text so far, not just the
        newest token)."""
        if self._streaming_bubble is None:
            self.start_streaming_message()
        self._streaming_bubble.update_text(full_text, finalize=False)
        self._scroll_to_bottom()

    def append_stream_token(self, token: str):
        """Convenience wrapper if the caller only has the newest token."""
        if self._streaming_bubble is None:
            self.start_streaming_message()
        current = self._streaming_bubble.text + token
        self.update_streaming_message(current)

    def finalize_streaming_message(self):
        """Call once generation has finished so code blocks etc. render."""
        if self._streaming_bubble is not None:
            self._streaming_bubble.update_text(self._streaming_bubble.text, finalize=True)
            if self._streaming_bubble not in self._bubbles:
                self._bubbles.append(self._streaming_bubble)
            self._streaming_bubble = None
        self._scroll_to_bottom()

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------
    def clear(self):
        self.hide_typing_indicator()
        self._streaming_bubble = None
        for bubble in self._bubbles:
            bubble.destroy()
        self._bubbles = []

    def _scroll_to_bottom(self):
        # CTkScrollableFrame exposes the underlying canvas as _parent_canvas.
        def _do_scroll():
            try:
                self._parent_canvas.yview_moveto(1.0)
            except Exception:
                pass
        self.after(20, _do_scroll)
