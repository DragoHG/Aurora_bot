# Aurora Bot

A modular, asynchronous, and resilient Discord bot that combines local text generation ([Ollama](https://ollama.com)) and local image generation ([Fooocus API](https://github.com/lllyasviel/Fooocus)) in a single bot — with GPU VRAM protection via sequential image queuing.

---

## Features

- **Conversational AI** — responds whenever someone mentions "Aurora" in a message or @mentions the bot directly, using any Ollama-compatible LLM
- **Per-user system prompts** — each user gets their own personality context stored in SQLite; the server owner can have a fully custom prompt
- **Sliding-window memory** — the last 10 messages per user are injected as conversation history, keeping context without overflowing the model's context window
- **Image generation** — `!imagem <prompt>` queues a Stable Diffusion XL generation request via Fooocus API
- **Natural image routing** — if a user says *"Aurora, make a !imagem of X"*, the bot detects the embedded command and routes it to the image engine instead of the LLM
- **VRAM-safe sequential queue** — only one image is generated at a time, preventing GPU Out-of-Memory errors on constrained hardware
- **Fully configurable via `.env`** — LLM model, SDXL model, styles, resolution, system prompts, and more — no code changes needed

---

## Architecture

```
Discord Message
       │
       ▼
┌──────────────┐
│  cogs/chat   │  ── trigger: "aurora" in text OR @mention
└──────┬───────┘
       │
       ├── !imagem detected mid-sentence?
       │         │
       │         ▼
       │   ┌─────────────┐     asyncio.Queue     ┌───────────────┐
       │   │ cogs/image  │ ──────────────────────▶│ FooocusEngine │──▶ Fooocus API :8888
       │   └─────────────┘                        │ background    │
       │                                          │ worker        │
       │                                          └───────────────┘
       │
       ▼ (plain text message)
┌──────────────┐
│ OllamaEngine │  aiohttp POST /api/chat  ──▶  Ollama :11434
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ DatabaseManager  │  SQLite (users + chat_history)
└──────────────────┘
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | 3.11 recommended |
| [Ollama](https://ollama.com) | Running locally on port `11434` |
| [Fooocus API](https://github.com/mrhan1993/Fooocus-API) | Running locally on port `8888` |
| A Discord bot token | [Discord Developer Portal](https://discord.com/developers/applications) |

> **GPU note:** Fooocus requires a CUDA-capable GPU. The sequential queue in this bot is specifically designed to protect 8 GB VRAM GPUs from OOM errors.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/aurora-bot.git
cd aurora-bot
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the bot

```bash
cp .env.example .env
```

Edit `.env` with your values (see [Configuration](#configuration) below).

### 5. Enable the Message Content Intent

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Open your application → **Bot**
2. Under **Privileged Gateway Intents**, enable **Message Content Intent**
3. Save changes

### 6. Run the bot

```bash
python main.py
```

---

## Configuration

All settings live in `.env`. Copy `.env.example` to get started.

### Discord

| Variable | Description | Default |
|---|---|---|
| `DISCORD_TOKEN` | Your bot token | **required** |
| `OWNER_ID` | Your Discord user ID | **required** |
| `COMMAND_PREFIX` | Prefix for bot commands | `!` |

### Database

| Variable | Description | Default |
|---|---|---|
| `DB_PATH` | Path to the SQLite file | `aurora.db` |

### Text Engine (Ollama)

| Variable | Description | Default |
|---|---|---|
| `OLLAMA_MODEL` | Model name to load | `qwen2.5` |
| `DEFAULT_SYSTEM_PROMPT` | Personality for all users | friendly assistant |
| `OWNER_SYSTEM_PROMPT` | Personality when talking to the owner | direct, respectful |

### Image Engine (Fooocus)

| Variable | Description | Default |
|---|---|---|
| `FOOOCUS_BASE_MODEL` | SDXL checkpoint filename | `realisticStockPhoto_v20.safetensors` |
| `FOOOCUS_REFINER_MODEL` | Refiner model (`None` to disable) | `None` |
| `FOOOCUS_STYLE` | Comma-separated style presets | `Fooocus V2,Fooocus Enhance` |
| `FOOOCUS_PERFORMANCE` | `Speed` / `Quality` / `Extreme Speed` | `Speed` |
| `FOOOCUS_ASPECT_RATIO` | Output resolution (`width*height`) | `1152*896` |
| `FOOOCUS_GUIDANCE_SCALE` | CFG scale | `7.0` |
| `FOOOCUS_SHARPNESS` | Sharpness (1.0 – 30.0) | `2.0` |

---

## Usage

### Chat

Simply mention **Aurora** anywhere in your message:

```
Hey Aurora, what is a Kubernetes operator?
```

Or @mention the bot directly:

```
@Aurora explain the CAP theorem
```

### Image Generation

Use the `!imagem` command with a description:

```
!imagem a futuristic city at night with neon lights and rain
```

You can also trigger image generation naturally within a message:

```
Aurora, please make a !imagem of a medieval knight in a forest
```

### Image Queue

When multiple users request images simultaneously, requests are queued. The bot replies immediately with the queue position:

```
🎨 Pedido de Imagem Recebido
Your image is in queue at position 2. Estimated wait: ~2 min.
Prompt: `a futuristic city at night`
```

---

## Project Structure

```
aurora-bot/
├── main.py            # Entry point — bot class, setup_hook, event handlers
├── database.py        # DatabaseManager — SQLite via aiosqlite
├── ai_engine.py       # OllamaEngine — async text generation
├── image_engine.py    # FooocusEngine — async image queue + background worker
├── cogs/
│   ├── chat.py        # ChatCog — on_message listener + image command routing
│   └── image.py       # ImageCog — !imagem / !img command
├── .env.example       # Configuration template
├── requirements.txt   # Python dependencies
└── README.md
```

---

## Dependencies

```
discord.py>=2.3.2
aiohttp>=3.9.5
aiosqlite>=0.20.0
python-dotenv>=1.0.1
```

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## License

[MIT](https://choosealicense.com/licenses/mit/)
