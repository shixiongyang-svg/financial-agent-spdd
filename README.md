# Financial Helpdesk Agent

A Dockerised, LangGraph-based "Financial Helpdesk Agent" that ingests
bounded public CFPB consumer-finance data, answers consumer questions
about fees, loans, mortgages, and complaints with grounded citations,
and operates safely under explicit guardrails.

## Quickstart

```bash
# Start all services
./start
```

## Project Layout

```text
financial-agent-spdd_week_00/
├── start                          # One-click startup script
├── README.md                      # Project README
├── docker-compose.yml             # Docker Compose orchestration
├── codebases/
│   ├── financial-agent-api/       # FastAPI backend
│   │   ├── pyproject.toml         # uv project configuration
│   │   ├── uv.lock                # Dependency lock file
│   │   ├── src/
│   │   │   └── financial_agent_api/
│   │   │       ├── __init__.py
│   │   │       └── main.py        # FastAPI application entry point
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_health.py     # /healthz endpoint tests
│   └── financial-agent-ui/        # Frontend placeholder
│       ├── package.json
│       ├── public/
│       │   └── index.html         # Static placeholder page
│       └── src/
│           └── App.js             # UI application entry point
├── support/                       # Docker and infrastructure support
│   ├── financial-agent-api/
│   │   └── Dockerfile
│   ├── financial-agent-ui/
│   │   └── Dockerfile
│   └── financial-agent-nginx/
│       ├── nginx.conf
│       ├── financial-agent-api.localhost.com.conf
│       └── financial-agent-ui.localhost.com.conf
├── trainee/                       # Trainee guides
└── .spdd_specs/                   # SPDD specification canvases
```

## Services

| Service                 | Description              | URL                                      |
|-------------------------|--------------------------|------------------------------------------|
| `financial-agent-nginx` | HTTP reverse proxy       | Port 80                                  |
| `financial-agent-api`   | FastAPI backend          | http://financial-agent-api.localhost.com |
| `financial-agent-ui`    | Frontend placeholder     | http://financial-agent-ui.localhost.com  |
| `financial-agent-db`    | PostgreSQL 16 + pgvector | localhost:5432                           |

## Health Endpoints

```bash
# API health check
curl -fsS http://financial-agent-api.localhost.com/healthz
# Expected: {"status":"ok"}

# API project tests
docker compose exec financial-agent-api uv run pytest tests/ -v
```

## 本地开发

### API 基础设施环境变量

后端位于 `codebases/financial-agent-api`，可复制 `.env.example` 为 `.env` 后本地运行：

```bash
cd codebases/financial-agent-api
cp .env.example .env
uv sync --dev
uv run uvicorn financial_agent_api.main:app --app-dir src --reload
```

关键变量：

- `LLM_PROVIDER=ollama|openrouter`
- `LOG_FORMAT=text|json`
- `OPENROUTER_API_KEY`：仅在 `LLM_PROVIDER=openrouter` 时必填
- `OPENROUTER_MODEL`、`OLLAMA_CHAT_MODEL`、`OLLAMA_OPS_MODEL`：分别控制默认模型

验证示例：

```bash
cd codebases/financial-agent-api
uv run python -c "from financial_agent_api.core.config import get_settings; print(get_settings().openrouter_model)"
uv run curl -fsS http://127.0.0.1:8000/readyz
```

## Development

- **Runtime:** Python 3.11+
- **Dependency manager:** uv
- **HTTP server:** FastAPI + uvicorn
- **Agent orchestration:** LangGraph
- **Database:** PostgreSQL + pgvector
- **Testing:** pytest
