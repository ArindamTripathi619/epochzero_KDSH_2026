# LLM Configuration Guide

Our system supports multiple LLM providers, allowing you to switch between cost-effective local models and high-performance cloud APIs.

## Supported Providers

1.  **Local Ollama** (Default): No cost, high privacy.
2.  **OpenAI**: High reasoning quality, fast.
3.  **Anthropic**: Best for long-context narrative reasoning.
4.  **OpenRouter**: Access multiple models (including free ones) via a single API.

---

## 1. Local Configuration (Ollama)

By default, the system looks for a local Ollama instance running Mistral.

**Environment Variables (`.env`)**:
```bash
USE_CLOUD=false
LLM_MODEL=mistral
OLLAMA_URL=http://localhost:11434/api/chat
```

**Prerequisites**:
1.  Install [Ollama](https://ollama.com/).
2.  Run `ollama pull mistral`.
3.  Ensure Ollama is running (`ollama serve`).

---

## 2. OpenAI Configuration

To use GPT-4o or GPT-3.5, provide your API key.

**Environment Variables (`.env`)**:
```bash
USE_CLOUD=true
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-proj-your-openai-key-here
```

**Custom Base URL** (for proxies):
```bash
OPENAI_API_BASE=https://your-proxy-url.com/v1
```

---

## 3. Anthropic Configuration

Claude 3.5 Sonnet is highly recommended for Track A due to its narrative reasoning capabilities.

**Environment Variables (`.env`)**:
```bash
USE_CLOUD=true
LLM_MODEL=claude-3-5-sonnet-20240620
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here
```

---

## 4. OpenRouter Configuration

Ideal for accessing free models or a unified interface.

**Environment Variables (`.env`)**:
```bash
USE_CLOUD=true
LLM_MODEL=google/gemini-flash-1.5-exp
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key-here
```

---

## Configuration Logic (Priority)

The `ConsistencyJudge` determines the provider based on your environment variables in this order:

1.  **Anthropic**: If `ANTHROPIC_API_KEY` is present and `LLM_MODEL` contains "claude".
2.  **OpenRouter**: If `OPENROUTER_API_KEY` is present and `OPENAI_API_KEY` is missing.
3.  **OpenAI**: If `OPENAI_API_KEY` is present.
4.  **Local**: Fallback if no valid cloud keys are found or if `USE_CLOUD=false`.

## Switching Models on the Fly

You can override settings for a single run without editing `.env`:

```bash
# Run with GPT-4o
USE_CLOUD=true LLM_MODEL=gpt-4o python3 main.py

# Run with local Llama3
USE_CLOUD=false LLM_MODEL=llama3 python3 main.py
```

## Performance Comparison

| Provider | Model | Typical Runtime (80 queries) | Cost |
|----------|-------|------------------------------|------|
| Ollama | Mistral | 20-25 minutes | $0 |
| OpenAI | GPT-4o | 3-5 minutes | ~$2.00 |
| Anthropic | Claude 3.5 | 3-5 minutes | ~$3.00 |

> [!TIP]
> For rapid iteration and validation, use a cloud API. For the final large-scale run, use local Ollama to save costs if the reasoning quality is sufficient.
