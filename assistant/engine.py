from typing import Generator, Optional


class AssistantEngine:

    def __init__(self, llm, store):
        self.llm = llm
        self.store = store
        self.conversation_id: Optional[int] = None

    def set_llm(self, llm) -> None:
        """Replace the runtime model (e.g. after Model Manager Apply)."""
        self.llm = llm

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

    def send(self, text: str) -> Generator[str, None, None]:
        text = text.strip()
        if not text:
            return

        if self.llm is None:
            yield (
                "[No model loaded. Open Model Manager, select or download a GGUF, "
                "then click Apply.]"
            )
            return

        conversation_id = self.ensure_conversation()
        self.store.save_message(conversation_id, "user", text)

        message_count = self.store.get_message_count(conversation_id)
        if message_count == 1:
            title = self._make_title(text)
            self.store.update_title(conversation_id, title)

        messages = self.store.load_messages(conversation_id)
        llm_messages = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
        ]

        response_parts = []
        for token in self.llm.stream(llm_messages):
            response_parts.append(token)
            yield token

        response = "".join(response_parts)
        if response.strip():
            self.store.save_message(conversation_id, "assistant", response)

    @staticmethod
    def _make_title(text: str) -> str:
        text = " ".join(text.strip().split())
        max_length = 50
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].rstrip() + "..."