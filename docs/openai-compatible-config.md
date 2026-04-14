# OpenAI Compatible Configuration

PlotPilot supports OpenAI-compatible providers through the following runtime keys:

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://your-gateway.example.com/v1
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.4
OPENAI_API_MODE=auto
OPENAI_TIMEOUT=120
OPENAI_MAX_RETRIES=2
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Recommended `OPENAI_API_MODE` values:

- `chat`: for gateways that only expose `/chat/completions`
- `responses`: for providers with a working `/responses` implementation
- `auto`: default and preferred; regular text uses chat, advanced reasoning/state uses responses

Example presets:

```env
# Chat-completions-only router
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://your-router.example.com/v1
OPENAI_MODEL=mimo-v2-pro
OPENAI_API_MODE=chat
```

```env
# Native or full Responses-compatible provider
LLM_PROVIDER=openai
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.4
OPENAI_API_MODE=responses
```

The workbench “模型接入” panel writes these values into the repository root `.env`
and updates the running API process environment at save time.
