import os
import sqlite3
from typing import Optional


class ConversationStore:

    def __init__(self, database_path: str):
        self.database_path = database_path

        directory = os.path.dirname(
            os.path.abspath(database_path)
        )

        os.makedirs(
            directory,
            exist_ok=True
        )

        self._initialize_database()


    def _connect(self):
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(self):
        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL DEFAULT 'New Conversation',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (
                        conversation_id
                    )
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_messages_conversation
                ON messages(conversation_id)
            """)


    def create_conversation(
        self,
        title: str = "New Conversation"
    ) -> int:

        with self._connect() as connection:

            cursor = connection.execute(
                """
                INSERT INTO conversations(title)
                VALUES (?)
                """,
                (title,)
            )

            return cursor.lastrowid

    def get_conversations(self):
        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()

            return [
                dict(row)
                for row in rows
            ]

    def get_conversation(
        self,
        conversation_id: int
    ) -> Optional[dict]:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT
                    id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,)
            ).fetchone()

            if row is None:
                return None

            return dict(row)

    def update_title(
        self,
        conversation_id: int,
        title: str
    ):

        title = title.strip()

        if not title:
            title = "New Conversation"

        with self._connect() as connection:

            connection.execute(
                """
                UPDATE conversations
                SET
                    title = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    title,
                    conversation_id
                )
            )

    def touch_conversation(
        self,
        conversation_id: int
    ):

        with self._connect() as connection:

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,)
            )


    def save_message(
        self,
        conversation_id: int,
        role: str,
        content: str
    ):

        with self._connect() as connection:

            connection.execute(
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

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,)
            )

    def load_messages(
        self,
        conversation_id: int
    ):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    role,
                    content,
                    created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,)
            ).fetchall()

            return [
                {
                    "role": row["role"],
                    "content": row["content"],
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    def get_message_count(
        self,
        conversation_id: int
    ) -> int:

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM messages
                WHERE conversation_id = ?
                """,
                (conversation_id,)
            ).fetchone()

            return row["count"]



    def delete_conversation(
        self,
        conversation_id: int
    ):

        with self._connect() as connection:

            connection.execute(
                """
                DELETE FROM messages
                WHERE conversation_id = ?
                """,
                (conversation_id,)
            )

            connection.execute(
                """
                DELETE FROM conversations
                WHERE id = ?
                """,
                (conversation_id,)
            )


    def delete_conversations_since(self, since_iso: str) -> int:
        """
        Delete conversations whose updated_at is on or after since_iso
        (SQLite datetime string, e.g. '2026-08-23 00:00:00').
        Returns number of conversations deleted.
        """
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                SELECT id FROM conversations
                WHERE updated_at >= ?
                """,
                (since_iso,),
            )
            ids = [row["id"] for row in cursor.fetchall()]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            connection.execute(
                f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                ids,
            )
            connection.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                ids,
            )
            return len(ids)

    def delete_conversations_older_than(self, before_iso: str) -> int:
        """
        Delete conversations whose updated_at is strictly before before_iso.
        Returns number of conversations deleted.
        """
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                SELECT id FROM conversations
                WHERE updated_at < ?
                """,
                (before_iso,),
            )
            ids = [row["id"] for row in cursor.fetchall()]
            if not ids:
                return 0
            placeholders = ",".join("?" * len(ids))
            connection.execute(
                f"DELETE FROM messages WHERE conversation_id IN ({placeholders})",
                ids,
            )
            connection.execute(
                f"DELETE FROM conversations WHERE id IN ({placeholders})",
                ids,
            )
            return len(ids)

    def delete_all_conversations(self) -> int:
        """Delete every conversation and message. Returns count removed."""
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM conversations"
            ).fetchone()
            count = row["count"]
            connection.execute("DELETE FROM messages")
            connection.execute("DELETE FROM conversations")
            return count

    def clear_conversations(self, scope: str) -> int:
        """
        scope: 'today' | 'last_week' | 'all'
        - today: updated today (local calendar day)
        - last_week: updated in the last 7 days
        - all: everything
        """
        from datetime import datetime, timedelta, timezone

        # SQLite CURRENT_TIMESTAMP is UTC
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if scope == "all":
            return self.delete_all_conversations()
        if scope == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return self.delete_conversations_since(start.strftime("%Y-%m-%d %H:%M:%S"))
        if scope == "last_week":
            start = now - timedelta(days=7)
            return self.delete_conversations_since(start.strftime("%Y-%m-%d %H:%M:%S"))
        raise ValueError(f"Unknown clear scope: {scope}")
