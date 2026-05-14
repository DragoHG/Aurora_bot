import asyncio
import base64
import io
import logging
import os
import aiohttp
import discord

logger = logging.getLogger(__name__)

FOOOCUS_URL = "http://127.0.0.1:8888/v1/generation/text-to-image"
FOOOCUS_TIMEOUT = aiohttp.ClientTimeout(total=300)  # 5 minutes max for generation

FOOOCUS_OFFLINE_MSG = (
    "⚠️ O gerador de imagens está offline. "
    "Verifique se o Fooocus API está em execução e tente novamente."
)


def _parse_styles(raw: str) -> list[str]:
    """Converts a comma-separated style string into a clean list."""
    return [s.strip() for s in raw.split(",") if s.strip()]


def _build_fooocus_params() -> dict:
    """
    Builds the Fooocus API payload from environment variables.
    All generation parameters are configurable via .env at runtime.
    """
    base_model = os.getenv("FOOOCUS_BASE_MODEL", "realisticStockPhoto_v20.safetensors")
    refiner_model = os.getenv("FOOOCUS_REFINER_MODEL", "None")
    styles_raw = os.getenv("FOOOCUS_STYLE", "Fooocus V2,Fooocus Enhance")
    performance = os.getenv("FOOOCUS_PERFORMANCE", "Speed")
    aspect_ratio = os.getenv("FOOOCUS_ASPECT_RATIO", "1152*896")
    guidance_scale = float(os.getenv("FOOOCUS_GUIDANCE_SCALE", "7.0"))
    sharpness = float(os.getenv("FOOOCUS_SHARPNESS", "2.0"))

    params: dict = {
        "performance_selection": performance,
        "aspect_ratios_selection": aspect_ratio,
        "style_selections": _parse_styles(styles_raw),
        "image_number": 1,
        "image_seed": -1,
        "sharpness": sharpness,
        "guidance_scale": guidance_scale,
        "refiner_switch": 0.5,
        "save_meta": False,
        "save_extension": "png",
        "async_process": False,
        "base_model_name": base_model,
    }

    # Omit refiner field entirely when set to "None" (disables refiner pass)
    if refiner_model and refiner_model.lower() != "none":
        params["refiner_model_name"] = refiner_model

    return params


class ImageRequest:
    """Represents a single image generation request in the queue."""

    def __init__(self, prompt: str, channel: discord.TextChannel, user_mention: str):
        self.prompt = prompt
        self.channel = channel
        self.user_mention = user_mention


class FooocusEngine:
    def __init__(self):
        self.queue: asyncio.Queue[ImageRequest] = asyncio.Queue()

    async def start(self) -> None:
        """Reserved for API compatibility — Fooocus uses a per-request session."""

    async def close(self) -> None:
        """Reserved for API compatibility — no persistent session to close."""

    async def enqueue(
        self,
        prompt: str,
        channel: discord.TextChannel,
        user_mention: str,
    ) -> int:
        """
        Adds a generation request to the queue and returns its 1-based position.
        The queue size before the put() call reflects how many jobs are waiting.
        """
        position = self.queue.qsize() + 1
        await self.queue.put(ImageRequest(prompt, channel, user_mention))
        return position

    async def background_worker(self) -> None:
        """
        Asyncio task that drains the image queue sequentially.
        Processes exactly one generation at a time to prevent GPU OOM on limited VRAM.
        """
        logger.info("Image background worker started.")
        while True:
            request: ImageRequest = await self.queue.get()
            logger.info(
                "Generating image for %s | prompt: %.60s...",
                request.user_mention,
                request.prompt,
            )
            try:
                image_bytes = await self._generate_image(request.prompt)
                file = discord.File(fp=io.BytesIO(image_bytes), filename="aurora_image.png")
                await request.channel.send(
                    content=f"🖼️ {request.user_mention}, sua imagem ficou pronta!",
                    file=file,
                )
            except (aiohttp.ClientConnectorError, aiohttp.ClientOSError, ConnectionResetError) as exc:
                logger.error("Fooocus connection error: %s", exc)
                await request.channel.send(
                    f"{request.user_mention} — {FOOOCUS_OFFLINE_MSG}"
                )
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for Fooocus response.")
                await request.channel.send(
                    f"⏰ {request.user_mention}, o tempo limite de geração foi atingido. "
                    "Tente um prompt mais simples ou tente novamente mais tarde."
                )
            except Exception as exc:
                logger.exception("Unexpected error in image worker: %s", exc)
                await request.channel.send(
                    f"⚠️ {request.user_mention}, ocorreu um erro ao gerar sua imagem. "
                    "Tente novamente."
                )
            finally:
                self.queue.task_done()
                # Yield control back to the event loop before picking the next item
                await asyncio.sleep(0)

    async def _generate_image(self, prompt: str) -> bytes:
        """
        POSTs a generation request to the Fooocus API and returns the image bytes.

        A fresh ClientSession is created per request to avoid stale TCP connections
        in the aiohttp connection pool (Windows ProactorEventLoop WinError 64).

        Fooocus may return either an inline base64 string or a URL pointing to a
        local file. Both formats are handled transparently.
        """
        payload = {**_build_fooocus_params(), "prompt": prompt}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                FOOOCUS_URL,
                json=payload,
                timeout=FOOOCUS_TIMEOUT,
            ) as response:
                response.raise_for_status()
                data = await response.json()

            images: list = data if isinstance(data, list) else data.get("base64", [])
            if not images:
                raise ValueError("Fooocus returned no images in the response.")

            first = images[0]

            if isinstance(first, dict):
                b64_val = first.get("base64")
                if b64_val:
                    return base64.b64decode(b64_val)

                # base64 field is null — download the image from the local URL instead
                img_url = first.get("url")
                if not img_url:
                    raise ValueError("Fooocus returned null base64 and no URL.")
                async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=60)) as dl:
                    dl.raise_for_status()
                    return await dl.read()

            # Plain base64 string response
            return base64.b64decode(first)
