# OpenClaw Readwise Article Saver

A [Letta/MemGPT](https://github.com/letta-ai/letta) tool for OpenClaw that automatically saves article links to [Readwise Reader](https://readwise.io/read) with **LLM-powered content-based tagging**.

## What It Does

```
You:     https://mp.weixin.qq.com/s/AbCdEf
OpenClaw: ✅ 微信文章「深度学习在金融领域的应用」已保存到 Readwise Reader。
            标签: AI agent, China, Startup Growth
            （服务端抓取 + minimax/minimax-m2.7 自动打标签）
```

Instead of tagging every article with a generic "openclaw" label, this tool:
1. Fetches the article content (with WeChat-specific handling)
2. Sends the text to an LLM (via OpenRouter) to classify it against a ~40-tag taxonomy
3. Saves the article to Readwise with those tags

## Architecture

```
URL received
    │
    ├── WeChat? → Server-side fetch (impersonate MicroMessenger)
    │               │
    │               ├── Content valid? → Extract text → LLM tags → Save with HTML + tags
    │               └── Content empty? → Fallback: URL-only save (tag: "openclaw")
    │
    └── Other? → Fetch content → LLM tags → URL-only save with tags
                    │
                    └── Fetch failed? → URL-only save (tag: "openclaw")
```

### Model Configuration

Tagging calls go through **OpenRouter**, a unified API gateway to 200+ models. The default model is **MiniMax M2.7** (`minimax/minimax-m2.7`). Switching models requires changing **one environment variable** — no code changes:

```bash
# Default: MiniMax M2.7 ($0.30/M input, $1.20/M output)
export TAGGING_MODEL="minimax/minimax-m2.7"

# Alternatives — just change this line:
export TAGGING_MODEL="minimax/minimax-m2.5"        # MiniMax M2.5
export TAGGING_MODEL="anthropic/claude-sonnet-4"    # Claude Sonnet
export TAGGING_MODEL="google/gemini-2.5-flash"      # Gemini Flash
export TAGGING_MODEL="deepseek/deepseek-r1"         # DeepSeek R1
export TAGGING_MODEL="openai/gpt-4o-mini"           # GPT-4o Mini
```

Full model list: [openrouter.ai/models](https://openrouter.ai/models)

## Setup

### Prerequisites

- A running OpenClaw (Letta) server
- Python 3.10+
- `letta` SDK: `pip install letta`
- A [Readwise access token](https://readwise.io/access_token)
- An [OpenRouter API key](https://openrouter.ai/keys)

### Step 1: Clone

```bash
git clone https://github.com/YOUR_USERNAME/openclaw-readwise-saver.git
cd openclaw-readwise-saver
```

### Step 2: Set Environment Variables

On your OpenClaw server:

```bash
# Required
export READWISE_TOKEN="your_readwise_access_token"
export OPENROUTER_API_KEY="your_openrouter_api_key"

# Optional: override tagging model (default: minimax/minimax-m2.7)
export TAGGING_MODEL="minimax/minimax-m2.7"
```

### Step 3: Register the Tool

```bash
python register_tool.py

# Or specify directly
python register_tool.py \
  --base-url http://your-openclaw-server:8283 \
  --agent-id ag-xxxxxxxx

# Update after code changes
python register_tool.py --update
```

### Step 4 (Recommended): Patch Agent System Prompt

```python
from letta import create_client
from system_prompt_patch import SYSTEM_PROMPT_PATCH

client = create_client(base_url="http://your-openclaw-server:8283")
agent = client.get_agent(agent_id="your-agent-id")
client.update_agent(
    agent_id=agent.id,
    system=agent.system + "\n\n" + SYSTEM_PROMPT_PATCH
)
```

## File Structure

```
openclaw-readwise-saver/
├── README.md                  # This file
├── save_article_tool.py       # Core: Letta tool function with OpenRouter tagging
├── register_tool.py           # One-click registration script
└── system_prompt_patch.py     # Agent system prompt snippet
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `READWISE_TOKEN` | Yes | — | Readwise access token |
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key (for auto-tagging) |
| `TAGGING_MODEL` | No | `minimax/minimax-m2.7` | Any OpenRouter model ID |

## Cost Estimate (MiniMax M2.7)

Each tagging call: ~5,500 input tokens + ~20 output tokens.

| Volume | Monthly Cost |
|--------|-------------|
| 5 articles/day | ~$2.50 |
| 10 articles/day | ~$5.00 |
| 20 articles/day | ~$10.00 |

To reduce costs, switch to a cheaper model:
```bash
export TAGGING_MODEL="minimax/minimax-m2.5"  # Free tier available
```

## Taxonomy

The built-in taxonomy covers ~40 tags across these domains:

| Domain | Example Tags |
|--------|-------------|
| AI & Technology | `AI agent`, `Chips`, `AI 上下文` |
| Finance | `VC`, `PE`, `Private Credit`, `Equity`, `M&A`, `Market` |
| Politics & IR | `Politics`, `IR` (always kept separate) |
| Economics | `Economics`, `infra`, `Consumer` |
| Startups | `Startup Growth`, `Founder` |
| Geography | `China`, `US`, `Europe`, `Middle East` |
| Key Figures | `Ray Dalio`, `Paul Graham`, `Howard Marks`, `Trump` |
| Companies | `YC`, `Anthropic`, `Cursor`, `Space X` |
| Personal | `Career`, `Personal Development`, `Mindset`, `Guide` |

The model can also create new tags when the taxonomy has gaps, following the same style rules.

### Customizing the Taxonomy

Edit the `TAGGING_SYSTEM_PROMPT` string in `save_article_tool.py`, then re-register:
```bash
python register_tool.py --update
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| All articles tagged `openclaw` | `OPENROUTER_API_KEY` not set | Set the env var |
| `❌ READWISE_TOKEN not set` | Env var missing | Set `READWISE_TOKEN` |
| `❌ API returned 401` (Readwise) | Token expired | Regenerate at [readwise.io/access_token](https://readwise.io/access_token) |
| Tags seem wrong | Article text too short | Check ✅ vs ⚠️ — if ⚠️, content wasn't fetched |
| `⚠️ 内容可能不完整` | WeChat blocked fetch | Open in WeChat → share to Readwise manually |
| Agent doesn't call the tool | System prompt missing | Apply prompt patch (Step 4) |
| Tagging timeout | Model too slow | Try `google/gemini-2.5-flash` for faster inference |

## License

MIT
