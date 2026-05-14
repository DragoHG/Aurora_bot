import logging
import re
import discord
from discord.ext import commands

from ai_engine import OllamaEngine

logger = logging.getLogger(__name__)

# Commands that should be handled by ImageCog, not the chat listener
IGNORED_PREFIXES = ("!imagem", "!img")


class ChatCog(commands.Cog, name="Chat"):
    """Handles free-form text conversations via the Ollama engine."""

    def __init__(self, bot: commands.Bot, ollama: OllamaEngine):
        self.bot = bot
        self.ollama = ollama

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Responds when a message contains the trigger word "aurora" or @mentions the bot.
        Ignores bots, DMs, and prefix commands.

        If the message also contains an embedded !imagem / !img command, it is
        extracted and routed directly to the FooocusEngine instead of Ollama,
        preventing the LLM from hallucinating fake image responses.
        """
        if message.author.bot:
            return

        if not message.guild:
            return

        content = message.content.strip()

        if not content:
            return

        # Let ImageCog handle messages that start directly with the image command
        if any(content.lower().startswith(prefix) for prefix in IGNORED_PREFIXES):
            return

        # Let other prefix commands pass through unhandled
        if content.startswith(self.bot.command_prefix):
            return

        bot_mentioned = self.bot.user in message.mentions
        has_trigger = "aurora" in content.lower()

        if not bot_mentioned and not has_trigger:
            return

        user_id = str(message.author.id)
        user_name = message.author.display_name

        # Detect !imagem / !img embedded mid-sentence (e.g. "Aurora make a !imagem of X")
        # and route to Fooocus instead of sending the full message to the LLM.
        img_match = re.search(r"!(?:imagem|img)\s+(.*)", content, re.IGNORECASE | re.DOTALL)
        if img_match:
            image_prompt = img_match.group(1).strip()
            logger.info("Mid-sentence image command from %s: %.80s...", user_name, image_prompt)
            fooocus = self.bot.fooocus  # type: ignore[attr-defined]
            position = await fooocus.enqueue(
                prompt=image_prompt,
                channel=message.channel,
                user_mention=message.author.mention,
            )
            queue_size = fooocus.queue.qsize()
            wait_estimate = queue_size * 2
            status_msg = (
                "Sua imagem está sendo gerada agora! Aguarde um momento."
                if position == 1
                else f"Sua imagem entrou na fila na posição **{position}**. Estimativa: ~{wait_estimate} min."
            )
            embed = discord.Embed(
                title="🎨 Pedido de Imagem Recebido",
                description=status_msg,
                color=discord.Color.purple(),
            )
            embed.add_field(name="Prompt", value=f"`{image_prompt[:200]}`", inline=False)
            embed.set_footer(text="O resultado será enviado aqui quando ficar pronto.")
            await message.reply(embed=embed, mention_author=True)
            return

        logger.info("Chat trigger from %s (%s): %.80s...", user_name, user_id, content)

        async with message.channel.typing():
            reply = await self.ollama.chat(user_id, user_name, content)

        # Append any extra @mentions from the original message (excluding the bot and author)
        # so referenced users are notified naturally at the end of the reply.
        extra_mentions = [
            u.mention
            for u in message.mentions
            if u.id != self.bot.user.id and u.id != message.author.id
        ]
        if extra_mentions:
            reply = reply.rstrip() + "\n" + " ".join(extra_mentions)

        # Discord's native reply already pings the author via notification.
        # Split into 2000-character chunks to respect the API message limit.
        if len(reply) <= 2000:
            await message.reply(reply, mention_author=True)
        else:
            chunks = [reply[i : i + 2000] for i in range(0, len(reply), 2000)]
            await message.reply(chunks[0], mention_author=True)
            for chunk in chunks[1:]:
                await message.channel.send(chunk)


async def setup(bot: commands.Bot) -> None:
    ollama: OllamaEngine = bot.ollama  # type: ignore[attr-defined]
    await bot.add_cog(ChatCog(bot, ollama))
