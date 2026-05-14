import logging
import discord
from discord.ext import commands

from image_engine import FooocusEngine

logger = logging.getLogger(__name__)


class ImageCog(commands.Cog, name="Image"):
    """Handles image generation requests via the Fooocus engine."""

    def __init__(self, bot: commands.Bot, fooocus: FooocusEngine):
        self.bot = bot
        self.fooocus = fooocus

    @commands.command(name="imagem", aliases=["img"])
    async def imagem(self, ctx: commands.Context, *, prompt: str = "") -> None:
        """
        Queues an image generation request.
        Usage: !imagem <image description>
        """
        if not prompt:
            await ctx.reply(
                "Por favor, forneça uma descrição para a imagem.\n"
                "Exemplo: `!imagem uma floresta encantada ao pôr do sol`",
                mention_author=False,
            )
            return

        position = await self.fooocus.enqueue(
            prompt=prompt,
            channel=ctx.channel,
            user_mention=ctx.author.mention,
        )

        queue_size = self.fooocus.queue.qsize()
        wait_estimate = queue_size * 2  # rough estimate in minutes

        if position == 1:
            status_msg = "Sua imagem está sendo gerada agora! Aguarde um momento."
        else:
            status_msg = (
                f"Sua imagem entrou na fila na posição **{position}**. "
                f"Estimativa de espera: ~{wait_estimate} min."
            )

        embed = discord.Embed(
            title="🎨 Pedido de Imagem Recebido",
            description=status_msg,
            color=discord.Color.purple(),
        )
        embed.add_field(name="Prompt", value=f"`{prompt[:200]}`", inline=False)
        embed.set_footer(text="O resultado será enviado aqui quando ficar pronto.")

        await ctx.reply(embed=embed, mention_author=False)

    @imagem.error
    async def imagem_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        logger.error("Error in !imagem command: %s", error)
        await ctx.reply(
            "⚠️ Ocorreu um erro ao processar seu pedido de imagem. Tente novamente.",
            mention_author=False,
        )


async def setup(bot: commands.Bot) -> None:
    fooocus: FooocusEngine = bot.fooocus  # type: ignore[attr-defined]
    await bot.add_cog(ImageCog(bot, fooocus))
