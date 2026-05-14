import os
import logging
import aiohttp
from database import DatabaseManager

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5")

OLLAMA_OFFLINE_MSG = (
    "⚠️ O motor de texto está offline no momento. "
    "Verifique se o Ollama está em execução e tente novamente."
)


class OllamaEngine:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        """Creates the reusable aiohttp ClientSession."""
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Closes the ClientSession when the bot shuts down."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def chat(self, user_id: str, user_name: str, message: str) -> str:
        """
        Processes a text message through the following steps:
        1. Ensures the user exists in the database.
        2. Fetches the user's system prompt and last 10 messages (sliding window).
        3. Sends the conversation payload to Ollama via aiohttp.
        4. Persists the new exchange and returns the response string.
        """
        await self.db.seed_user(user_id, user_name)

        system_prompt = await self.db.get_system_prompt(user_id)
        history = await self.db.get_history(user_id, limit=10)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
        }

        try:
            async with self.session.post(
                OLLAMA_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                response.raise_for_status()
                data = await response.json()

            reply: str = data["message"]["content"].strip()

        except aiohttp.ClientConnectorError:
            logger.error("Ollama unreachable at %s", OLLAMA_URL)
            return OLLAMA_OFFLINE_MSG

        except aiohttp.ClientResponseError as exc:
            logger.error("Ollama returned HTTP error %s: %s", exc.status, exc.message)
            return f"⚠️ O Ollama retornou um erro inesperado (HTTP {exc.status}). Tente novamente."

        except Exception as exc:
            logger.exception("Unexpected error while calling Ollama: %s", exc)
            return "⚠️ Ocorreu um erro interno ao processar sua mensagem. Tente novamente."

        await self.db.save_message(user_id, "user", message)
        await self.db.save_message(user_id, "assistant", reply)

        return reply
