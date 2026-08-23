from typing import Generator, Optional


class AssistantEngine:

    def __init__(self, llm, store):
        self.llm = llm
        self.store = store
        # None until the user actually sends a message
        self.conversation_id: Optional[int] = None

    # -----------------------------------------------------
    # Conversations
    # -----------------------------------------------------

    def new_conversation(self) -> None:
        """Start a blank draft — no DB row until the first message."""
        self.conversation_id = None

    def ensure_conversation(self) -> int:
        """Create a DB conversation on demand (first user message)."""
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
        """
        scope: 'today' | 'last_week' | 'all'
        Does not create a replacement empty conversation.
        """
        deleted = self.store.clear_conversations(scope)
        self.conversation_id = None
        return deleted

    def delete_conversation(self, conversation_id: int) -> None:
        self.store.delete_conversation(conversation_id)
        if self.conversation_id == conversation_id:
            self.conversation_id = None

    # -----------------------------------------------------
    # Chat
    # -----------------------------------------------------

    def send(self, text: str) -> Generator[str, None, None]:
        text = text.strip()
        if not text:
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
