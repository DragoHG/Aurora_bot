import asyncio
import logging
import os

from dotenv import load_dotenv

# load_dotenv() MUST be called before any local imports because database.py,
# ai_engine.py and image_engine.py read os.getenv() at module level (import time).
load_dotenv()

import discord
from discord.ext import commands

from database import DatabaseManager
from ai_engine import OllamaEngine
from image_engine import FooocusEngine

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aurora_bot")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")

COGS = [
    "cogs.chat",
    "cogs.image",
]


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------
class AuroraBot(commands.Bot):
    """
    Main Aurora bot class.
    Holds references to all engines so Cogs can access them via bot attributes.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required to read message content

        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)

        self.db = DatabaseManager()
        self.ollama = OllamaEngine(self.db)
        self.fooocus = FooocusEngine()

    async def setup_hook(self) -> None:
        """
        Called after login but before on_ready.
        Used to initialize async resources and load Cogs.
        """
        await self.db.setup()
        logger.info("Database initialized.")

        await self.ollama.start()
        await self.fooocus.start()
        logger.info("Engine HTTP sessions started.")

        # Start the image generation worker as a background asyncio task
        self.loop.create_task(
            self.fooocus.background_worker(),
            name="fooocus_background_worker",
        )
        logger.info("Image background worker task created.")

        for cog in COGS:
            await self.load_extension(cog)
            logger.info("Cog loaded: %s", cog)

    async def on_ready(self) -> None:
        logger.info("Aurora Bot online as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="your messages | !imagem",
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return  # Silently ignore unknown commands
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(
                f"⚠️ Missing argument: `{error.param.name}`. "
                f"Use `{COMMAND_PREFIX}help` to see available commands.",
                mention_author=False,
            )
            return
        logger.error("Unhandled error in command '%s': %s", ctx.command, error)

    async def close(self) -> None:
        """Gracefully shuts down all engine resources before closing."""
        logger.info("Shutting down Aurora Bot...")
        await self.ollama.close()
        await self.fooocus.close()
        await super().close()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
async def main() -> None:
    bot = AuroraBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
