# Financial Helpdesk Agent API

A FastAPI-based backend service providing LLM integration, structured logging, and configuration management for the
Financial Helpdesk Agent.

## Architecture

- **Configuration Management:** Pydantic Settings with environment variable support
- **LLM Integration:** Provider-agnostic facade supporting OpenRouter and Ollama
- **Structured Logging:** JSON and text formats with request tracing
- **HTTP Client:** Async httpx wrapper with retry logic
- **Testing:** Comprehensive pytest suite with 100% coverage targets

## Requirements

- Python 3.11+
- uv (dependency manager)
- (Optional) Ollama for local LLM inference

## Local Development

### Prerequisites

Install required tools:

```bash
# Install uv (macOS)
brew install uv

# Install Ollama (optional, for local LLM inference)
brew install ollama
```

### Setup

1. **Clone and navigate to the API directory:**

```bash
cd codebases/financial-agent-api
```

2. **Create environment file:**

```bash
cp .env.example .env
```

3. **Install dependencies:**

```bash
uv sync --dev
```

### Configuration

Edit `.env` to configure your settings:

```bash
# LLM Provider: "ollama" (default, local) or "openrouter" (cloud API)
LLM_PROVIDER=ollama

# Log format: "text" (default) or "json"
LOG_FORMAT=text

# OpenRouter settings (required if LLM_PROVIDER=openrouter)
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=gpt-4.1-mini

# Ollama settings (used if LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma3:27b
OLLAMA_OPS_MODEL=qwen3.5:4b
```

### Running Ollama (Optional)

If using Ollama locally:

```bash
# Start Ollama service (runs on http://localhost:11434)
ollama serve

# In another terminal, pull required models:
ollama pull gemma3:27b
ollama pull qwen3.5:4b
```

## Development Commands

### Run Tests

```bash
# Run all tests with verbose output
uv run pytest tests/ -v

# Run tests with coverage report
uv run pytest tests/ -v --cov=src --cov-report=html

# Run a specific test file
uv run pytest tests/test_llm_service.py -v

# Run tests matching a pattern
uv run pytest tests/ -k "test_openrouter" -v
```

### Type Checking

```bash
# Run mypy with strict mode
uv run mypy --strict --explicit-package-bases src/

# Check a specific file
uv run mypy --strict src/financial_agent_api/services/llm_service.py
```

### Code Quality

```bash
# Run ruff linter (checks style, imports, etc.)
uv run ruff check src/ tests/

# Auto-fix ruff issues
uv run ruff check --fix src/ tests/

# Run all quality checks
uv run ruff check src/ tests/ && \
uv run mypy --strict --explicit-package-bases src/
```

### Run Server Locally

```bash
# Start development server with auto-reload
uv run uvicorn financial_agent_api.main:app --app-dir src --reload --host 0.0.0.0 --port 8000

# Test the API
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

### Verify Configuration

```bash
# Test that settings load correctly
uv run python -c "from financial_agent_api.core.config import get_settings; print(get_settings().openrouter_model)"
```

## Project Structure

```
src/financial_agent_api/
├── core/
│   ├── config.py              # Settings + get_settings()
│   ├── exceptions.py          # LLMProviderError, LLMOutputValidationError
│   ├── logging.py             # configure_logging, bind_request_id
│   └── services_container.py  # ServicesContainer dataclass
├── services/
│   ├── llm_client.py          # LLMHTTPClient (httpx wrapper)
│   └── llm_service.py         # LLMService (provider-agnostic facade)
├── __init__.py
└── main.py                    # FastAPI application

tests/
├── test_config.py             # Settings validation tests
├── test_health.py             # Health endpoint tests
├── test_llm_service.py        # LLM service + retry logic tests
├── test_logging.py            # Logging configuration tests
└── __init__.py
```

## Key Features

### Multi-Provider LLM Support

```python
from financial_agent_api.services.llm_service import LLMService

# Seamlessly switch between providers via configuration
llm = LLMService(settings=settings, http_client=http_client)
response = await llm.complete(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.0,
    max_tokens=1000,
)
```

### Structured Logging

Logs include `request_id` for distributed tracing:

**JSON format:**

```json
{
  "timestamp": "2026-07-12T11:48:03.417+08:00",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "llm_complete_success",
  "duration_ms": 123.456
}
```

**Text format:**

```
2026-07-12T11:48:03.417+08:00 INFO [550e8400-e29b-41d4-a716-446655440000] llm_complete_success duration_ms=123.456
```

### Automatic Request Tracing

Every HTTP request gets a unique `request_id` that flows through all logs:

```bash
curl -H "X-Request-Id: my-custom-id" http://127.0.0.1:8000/readyz
# Response includes: X-Request-Id: my-custom-id
# All logs for this request tagged with this ID
```

### Retry Logic

LLM requests automatically retry with exponential backoff:

- Up to 3 attempts
- Exponential delay: 1s → 2s → 4s (plus jitter)
- Retries on: HTTP 5xx, timeouts, connection errors
- No retry on: HTTP 4xx, 429 (rate limit)

## Testing

The project includes comprehensive tests covering:

- ✅ Configuration loading and validation
- ✅ Provider-specific endpoint routing
- ✅ Retry behavior and backoff
- ✅ Error handling and exception safety
- ✅ Structured logging formats
- ✅ Request ID propagation

All tests pass with 100% coverage target:

```bash
uv run pytest tests/ -v
# 21 passed in 0.19s
```

## API Endpoints

### Health Checks

- `GET /healthz` — Basic liveness probe
- `GET /readyz` — Readiness probe (returns 200 OK)

Both endpoints return `{"status": "ok"}`.

## Environment Variables Reference

| Variable              | Required | Default                        | Description                                                 |
|-----------------------|----------|--------------------------------|-------------------------------------------------------------|
| `LLM_PROVIDER`        | ❌        | `ollama`                       | LLM provider: `ollama` or `openrouter`                      |
| `LOG_FORMAT`          | ❌        | `text`                         | Log format: `text` or `json`                                |
| `OPENROUTER_API_KEY`  | ✅*       | —                              | OpenRouter API key (*required if `LLM_PROVIDER=openrouter`) |
| `OPENROUTER_BASE_URL` | ❌        | `https://openrouter.ai/api/v1` | OpenRouter endpoint                                         |
| `OPENROUTER_MODEL`    | ❌        | `gpt-4.1-mini`                 | Default OpenRouter model                                    |
| `OLLAMA_BASE_URL`     | ❌        | `http://localhost:11434`       | Ollama endpoint                                             |
| `OLLAMA_CHAT_MODEL`   | ❌        | `gemma3:27b`                   | Default Ollama chat model                                   |
| `OLLAMA_OPS_MODEL`    | ❌        | `qwen3.5:4b`                   | Ollama ops/utility model                                    |

## Security Considerations

1. **Never commit `.env`** — Use `.env.example` with placeholders only
2. **API Keys are redacted** — Automatically stripped from logs and exceptions
3. **Request validation** — Pydantic validates all inputs
4. **No global singletons** — Uses constructor-based dependency injection

## Troubleshooting

### Tests fail with "module not found"

```bash
# Reinstall dependencies
uv sync --dev
```

### Settings validation fails

```bash
# Check your .env file
cd codebases/financial-agent-api
cat .env | grep LLM_PROVIDER

# If using OpenRouter, ensure API key is set
cat .env | grep OPENROUTER_API_KEY
```

### Ollama connection refused

```bash
# Start Ollama service
ollama serve

# Test connectivity
curl http://localhost:11434/api/tags
```

### mypy strictness issues

```bash
# Run mypy in watch mode to debug incrementally
uv run mypy --strict --explicit-package-bases src/ --show-error-context
```

## Contributing

When adding new features:

1. Update `.env.example` if new environment variables are added
2. Add corresponding tests in `tests/`
3. Ensure `mypy --strict`, `ruff check`, and `pytest` all pass
4. Update this README if the architecture or setup changes

## References

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [httpx Async Client](https://www.python-httpx.org/)
- [pytest](https://docs.pytest.org/)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [OpenRouter API](https://openrouter.ai/docs/)
