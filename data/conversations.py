import sqlite3


class ConversationStore:

    def __init__(self, path="data/conversations.db"):
        self.conn = sqlite3.connect(path)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def create_conversation(self):
        cursor = self.conn.cursor()

        cursor.execute(
            "INSERT INTO conversations(title) VALUES (?)",
            ("New Conversation",)
        )

        self.conn.commit()

        return cursor.lastrowid

    def save_message(
        self,
        conversation_id,
        role,
        content
    ):
        self.conn.execute(
            """
            INSERT INTO messages(
                conversation_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                conversation_id,
                role,
                content
            )
        )

        self.conn.commit()

    def load_messages(
        self,
        conversation_id
    ):
        rows = self.conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conversation_id,)
        )

        return [
            {
                "role": role,
                "content": content
            }
            for role, content in rows
        ]