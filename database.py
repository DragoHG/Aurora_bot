import os
import aiosqlite
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "aurora.db")
OWNER_ID = os.getenv("OWNER_ID", "")

OWNER_SYSTEM_PROMPT = os.getenv(
    "OWNER_SYSTEM_PROMPT",
    "You are talking to the server owner. Treat them with respect and be direct.",
)

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "You are Aurora, a friendly and helpful AI assistant. Answer clearly and concisely.",
)


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def setup(self) -> None:
        """Creates the required tables if they do not already exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    custom_system_prompt TEXT NOT NULL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            await db.commit()

    async def seed_user(self, user_id: str, name: str) -> None:
        """
        Inserts a user record if it does not already exist.
        The server owner receives the owner system prompt; all others get the default.
        """
        prompt = OWNER_SYSTEM_PROMPT if str(user_id) == str(OWNER_ID) else DEFAULT_SYSTEM_PROMPT
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO users (id, name, custom_system_prompt)
                VALUES (?, ?, ?)
                """,
                (str(user_id), name, prompt),
            )
            await db.commit()

    async def get_system_prompt(self, user_id: str) -> str:
        """Returns the stored system prompt for the given user."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT custom_system_prompt FROM users WHERE id = ?",
                (str(user_id),),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else DEFAULT_SYSTEM_PROMPT

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Returns the last `limit` messages for the user (sliding window context).
        Results are returned in chronological order.
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT role, content FROM chat_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (str(user_id), limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    async def save_message(self, user_id: str, role: str, content: str) -> None:
        """Persists a single chat message to the history table."""
        timestamp = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO chat_history (user_id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (str(user_id), role, content, timestamp),
            )
            await db.commit()
