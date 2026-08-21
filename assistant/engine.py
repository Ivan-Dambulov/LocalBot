from typing import Generator


class AssistantEngine:

    def __init__(
        self,
        llm,
        store
    ):
        self.llm = llm
        self.store = store

        self.conversation_id = (
            self.store.create_conversation()
        )

    # -----------------------------------------------------
    # Conversations
    # -----------------------------------------------------

    def new_conversation(self) -> int:

        self.conversation_id = (
            self.store.create_conversation()
        )

        return self.conversation_id

    def load_conversation(
        self,
        conversation_id: int
    ):

        conversation = (
            self.store.get_conversation(
                conversation_id
            )
        )

        if conversation is None:
            raise ValueError(
                "Conversation does not exist."
            )

        self.conversation_id = conversation_id

        return self.store.load_messages(
            conversation_id
        )

    def get_conversations(self):
        return self.store.get_conversations()

    # -----------------------------------------------------
    # Chat
    # -----------------------------------------------------

    def send(
        self,
        text: str
    ) -> Generator[str, None, None]:

        text = text.strip()

        if not text:
            return

        conversation_id = (
            self.conversation_id
        )

        # Save user message
        self.store.save_message(
            conversation_id,
            "user",
            text
        )

        # Automatically create a title from
        # the first user message.
        message_count = (
            self.store.get_message_count(
                conversation_id
            )
        )

        if message_count == 1:

            title = self._make_title(text)

            self.store.update_title(
                conversation_id,
                title
            )

        # Load complete conversation
        messages = (
            self.store.load_messages(
                conversation_id
            )
        )

        # Remove database-only fields before
        # sending to the LLM.
        llm_messages = [
            {
                "role": message["role"],
                "content": message["content"]
            }
            for message in messages
        ]

        # Generate response
        response_parts = []

        for token in self.llm.stream(
            llm_messages
        ):

            response_parts.append(token)

            yield token

        response = "".join(
            response_parts
        )

        # Save assistant response
        if response.strip():

            self.store.save_message(
                conversation_id,
                "assistant",
                response
            )


    @staticmethod
    def _make_title(text: str) -> str:

        text = " ".join(
            text.strip().split()
        )

        max_length = 50

        if len(text) <= max_length:
            return text

        return (
            text[:max_length - 3].rstrip()
            + "..."
        )