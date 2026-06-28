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

## Development

- **Runtime:** Python 3.11+
- **Dependency manager:** uv
- **HTTP server:** FastAPI + uvicorn
- **Agent orchestration:** LangGraph
- **Database:** PostgreSQL + pgvector
- **Testing:** pytest
