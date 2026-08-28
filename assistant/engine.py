from __future__ import annotations

import threading
from typing import Generator, List, Optional

from assistant.context_provider import ContextProvider
from files.attachments import AttachmentManager
from web.search import WebSearchError, WebSearcher


# Soft limits; char budget is the real sliding window.
MAX_HISTORY_MESSAGES = 60
# Rough chars reserved for system context + new reply.
REPLY_RESERVE_CHARS = 4000


def _trim_messages_for_context(
    messages: list,
    max_chars: int,
) -> list:
    """Keep newest messages until the character budget is reached."""
    if not messages or max_chars <= 0:
        return list(messages) if messages else []

    selected = []
    total = 0
    for msg in reversed(messages):
        content = msg.get("content") or ""
        size = len(content)
        if selected and total + size > max_chars:
            break
        selected.append(msg)
        total += size
    selected.reverse()
    return selected


class AssistantEngine:
    def __init__(self, llm, store):
        self.llm = llm
        self.store = store
        self.conversation_id: Optional[int] = None

        self.web_search_enabled = False
        self.web_searcher = WebSearcher(max_results=5)

        self.context_provider = ContextProvider()
        self.attachments = AttachmentManager()

        self._cancel_event = threading.Event()

    def set_llm(self, llm) -> None:
        self.llm = llm

    def set_web_search_enabled(self, enabled: bool) -> None:
        self.web_search_enabled = bool(enabled)

    def request_stop(self) -> None:
        """Signal the active generation loop to stop."""
        self._cancel_event.set()

    def is_stop_requested(self) -> bool:
        return self._cancel_event.is_set()

    def add_attachments(self, paths):
        self.attachments.add_files(paths)

    def clear_attachments(self):
        self.attachments.clear()

    def get_attachments(self):
        return self.attachments.get_files()

    def get_attachment_names(self):
        return self.attachments.get_display_names()

    def new_conversation(self) -> None:
        self.conversation_id = None

    def ensure_conversation(self) -> int:
        if self.conversation_id is None:
            self.conversation_id = self.store.create_conversation()
        return self.conversation_id

    def load_conversation(self, conversation_id: int):
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError("Conversation does not exist.")
        self.conversation_id = conversation_id
        return self.store.load_messages(conversation_id)

    def get_conversations(self):
        return self.store.get_conversations()

    def clear_conversations(self, scope: str) -> int:
        deleted = self.store.clear_conversations(scope)
        self.conversation_id = None
        return deleted

    def delete_conversation(self, conversation_id: int) -> None:
        self.store.delete_conversation(conversation_id)
        if self.conversation_id == conversation_id:
            self.conversation_id = None

    def _context_char_budget(self) -> int:
        ctx = 8192
        if self.llm is not None:
            ctx = int(getattr(self.llm, "context_size", 8192) or 8192)
        # ~3 chars per token (conservative); leave room for reply + system.
        budget = max(1500, (ctx * 3) - REPLY_RESERVE_CHARS)
        return budget

    def send(
        self,
        text: str,
        web_search: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        text = text.strip()
        if not text:
            return

        self._cancel_event.clear()

        if self.llm is None:
            yield (
                "[No model loaded. Open Model Manager, "
                "select or download a GGUF, then click Apply.]"
            )
            return

        if web_search is None:
            web_search = self.web_search_enabled

        conversation_id = self.ensure_conversation()
        self.store.save_message(conversation_id, "user", text)

        message_count = self.store.get_message_count(conversation_id)
        if message_count == 1:
            self.store.update_title(
                conversation_id,
                self._make_title(text),
            )

        messages = self.store.load_messages(conversation_id)

        if len(messages) > MAX_HISTORY_MESSAGES:
            messages = messages[-MAX_HISTORY_MESSAGES:]

        messages = _trim_messages_for_context(
            messages,
            max_chars=self._context_char_budget(),
        )

        llm_messages: List[dict] = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

        search_results = []
        if web_search and not self._cancel_event.is_set():
            try:
                search_results = self.web_searcher.search(text)
            except WebSearchError:
                search_results = []

        if self._cancel_event.is_set():
            yield "\n\n[Stopped]"
            self.attachments.clear()
            return

        context = self.context_provider.build_context(
            query=text,
            search_results=search_results,
            attachments=self.attachments.get_files(),
        )

        if context:
            llm_messages.insert(
                0,
                {
                    "role": "system",
                    "content": (
                        "External context for the user's request.\n\n"
                        + context
                    ),
                },
            )

        response_parts: List[str] = []
        stopped = False

        for token in self.llm.stream(llm_messages):
            if self._cancel_event.is_set():
                stopped = True
                break
            response_parts.append(token)
            yield token

        response = "".join(response_parts)

        sources_text = ""
        if search_results and not stopped:
            sources_lines = ["", "", "Sources:"]
            for idx, source in enumerate(search_results, start=1):
                sources_lines.append(f"{idx}. {source.title}")
                sources_lines.append(source.url)
            sources_text = "\n".join(sources_lines)
            yield sources_text

        if stopped:
            yield "\n\n[Stopped]"

        saved = (response + sources_text).strip()
        if stopped and response.strip():
            saved = (response.rstrip() + "\n\n[Stopped]").strip()
        elif stopped and not response.strip():
            saved = "[Stopped]"

        if saved:
            self.store.save_message(conversation_id, "assistant", saved)

        self.attachments.clear()

    @staticmethod
    def _make_title(text: str) -> str:
        text = " ".join(text.strip().split())
        max_length = 50
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rstrip() + "..."