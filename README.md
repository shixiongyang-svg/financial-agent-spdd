# Financial Helpdesk Agent

A Dockerised, LangGraph-based "Financial Helpdesk Agent" that ingests
bounded public CFPB consumer-finance data, answers consumer questions
about fees, loans, mortgages, and complaints with grounded citations,
and operates safely under explicit guardrails.

## Quickstart

```bash
# First run: interactive provider/config setup, then start services
./start
```

Behavior of `./start`:

- **First run** (no `./.local-config/llm.env`): asks you to choose provider (`ollama` or `openrouter`) and input required values, then saves them to `./.local-config/llm.env`.
- **Subsequent runs**: no prompts; reuses the saved config automatically.
- **Reset config**: delete local config directory and run again:

```bash
rm -rf ./.local-config
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
- `COMPLAINTS_CSV_PATH`、`DOCS_SOURCE_DIR`：容器内固定为 `/app/data/...`

### 交互式本地配置（推荐）

本项目默认通过根目录 `./start` 进行交互式配置并启动：

1. 首次运行会创建 `./.local-config/llm.env`（本地私有，不提交）。
2. 你只需按提示选择模型并输入必要参数。
3. 第二次运行起直接复用，不再询问。

交互时会根据模型提供商要求不同变量：

- Ollama：`OLLAMA_BASE_URL`、`OLLAMA_CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`
- OpenRouter：`OPENROUTER_API_KEY`、`OPENROUTER_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`

### OpenRouter 免费模型快速验证脚本

根目录提供了一个脚本，可自动拉取模型目录并完成两段验证：
1) 从 `output_modalities=text` 列表里选择可用 `:free` 聊天模型做对话测试；2) 从 `output_modalities=embeddings` 列表里探测可用 embedding 模型并识别向量维度。遇到 429 会按 `Retry-After` 重试，但会限制等待上限并快速切换候选模型，避免卡太久。

```bash
python scripts/openrouter_free_smoke.py
```

脚本流程：

1. 输入 `OPENROUTER_API_KEY`（隐藏输入）
2. 拉取当前可用 `:free` 聊天模型并自动优先挑选常见模型
3. 使用脚本内置测试消息自动验证聊天返回（无需手动输入）
4. 自动验证一个可用 `EMBEDDING_MODEL` 并检测 `EMBEDDING_DIM`
5. 输出可直接粘贴的推荐环境变量：`OPENROUTER_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM`

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
