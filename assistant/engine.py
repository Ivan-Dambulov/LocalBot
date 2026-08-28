from typing import Generator, Optional

from assistant.context_provider import ContextProvider
from files.attachments import AttachmentManager

from web.search import (
    WebSearchError,
    WebSearcher,
)


class AssistantEngine:
    def __init__(self, llm, store):
        self.llm = llm
        self.store = store
        self.conversation_id: Optional[int] = None

        self.web_search_enabled = False
        self.web_searcher = WebSearcher(max_results=5)

        self.context_provider = ContextProvider()
        self.attachments = AttachmentManager()

    def set_llm(self, llm) -> None:
        """Replace the runtime model."""
        self.llm = llm

    def set_web_search_enabled(self, enabled: bool) -> None:
        self.web_search_enabled = bool(enabled)

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

    def send(
            self,
            text: str,
            web_search: Optional[bool] = None,
    ) -> Generator[str, None, None]:

        text = text.strip()

        if not text:
            return

        if self.llm is None:
            yield (
                "[No model loaded. Open Model Manager, "
                "select or download a GGUF, then click Apply.]"
            )
            return

        if web_search is None:
            web_search = self.web_search_enabled

        conversation_id = self.ensure_conversation()

        self.store.save_message(
            conversation_id,
            "user",
            text,
        )

        message_count = self.store.get_message_count(
            conversation_id
        )

        if message_count == 1:
            self.store.update_title(
                conversation_id,
                self._make_title(text),
            )

        messages = self.store.load_messages(
            conversation_id
        )

        llm_messages = [
            {
                "role": message["role"],
                "content": message["content"],
            }
            for message in messages
        ]

        search_results = []

        if web_search:
            try:
                search_results = self.web_searcher.search(text)

            except WebSearchError:
                search_results = []

        context = self.context_provider.build_context(
            query=text,
            search_results=search_results,
            attachments=self.attachments.get_files(),
        )

        if context:
            llm_messages.append(
                {
                    "role": "system",
                    "content": (
                            "External context for the user's request.\n\n"
                            + context
                    ),
                }
            )

        response_parts = []

        for token in self.llm.stream(llm_messages):
            response_parts.append(token)
            yield token

        response = "".join(response_parts)

        if response.strip():
            self.store.save_message(
                conversation_id,
                "assistant",
                response,
            )

        if search_results:
            yield "\n\nSources:\n"

            for idx, source in enumerate(
                    search_results,
                    start=1,
            ):
                yield (
                    f"\n{idx}. "
                    f"{source.title}\n"
                    f"{source.url}\n"
                )

        self.attachments.clear()

    def _search_and_prepare(
        self,
        query: str,
        llm_messages: list,
    ) -> Generator[str, None, None]:
        """Search the web and append results to the LLM context."""

        yield "[Searching the Internet…]\n"

        try:
            results = self.web_searcher.search(query)

            context = format_search_context(
                query,
                results,
            )

            if results:
                yield (
                    f"[Found {len(results)} web "
                    f"result(s).]\n\n"
                )
            else:
                yield "[No web results found.]\n\n"

        except WebSearchError as exc:
            context = (
                "Internet search failed. Answer using your "
                "existing knowledge only.\n"
                f"Search error: {exc}"
            )

            yield (
                "[Internet search failed; continuing "
                "without web results.]\n\n"
            )

        # Important: don't save this search context as a
        # conversation message. It is temporary context only.
        llm_messages.append(
            {
                "role": "system",
                "content": context,
            }
        )

    @staticmethod
    def _make_title(text: str) -> str:
        text = " ".join(text.strip().split())

        max_length = 50

        if len(text) <= max_length:
            return text

        return text[: max_length - 3].rstrip() + "..."