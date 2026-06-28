# Task 0 — Environment (REASONS Canvas)

> **Maps to:** Learning Plan Week 0 — *Environment & Project Skeleton*.
> **Depends on:** `0_Root_Architecture.md` only.
> **Unblocks:** `Task_1_Foundations.md`.

---

## Requirements

Based on `0_Root_Architecture.md`, set up the project environment and scaffold.

### Analysis context

**Domain keywords scanned:** docker compose, FastAPI, postgres,
pgvector, healthz

**Strategic direction:** keep the Day-1 surface area microscopic.

1. Scaffold the most basic API project, providing only a `/healthz` endpoint returning 200 OK. Use `uv` for Python project management with version-pinned dependencies.
2. Scaffold the most basic UI project, referencing the tech stack in the Root Constitution. Visiting `/` should return an empty placeholder page.
3. For convenient local development, support one-click startup via Docker Compose.
4. Since the API project will depend on PostgreSQL + pgvector in the future, provision a PostgreSQL database as a dependency of the API project.

### Why this task exists

A junior developer must be able to run `docker compose up` from a clean
clone and see a healthy stack within minutes. The agent's correctness
in later tasks depends on a reproducible runtime where every later
piece (Postgres, embeddings, LangGraph, evaluation) plugs into the same
container topology. Without this scaffold, every task downstream
spends time fighting infrastructure instead of building features.

### Acceptance criteria (Given/When/Then)

- **Given** a clean clone of the repository,
  **when** the developer runs `./start`,
  **then** a Docker application `financial-agent-spdd` is created with four services
  `financial-agent-ui`, `financial-agent-db`, `financial-agent-api`, and
  `financial-agent-nginx`, all reaching healthy state.
- **Given** all services are running,
  **when** a browser visits `http://financial-agent-ui.localhost.com`,
  **then** a page with placeholder information is displayed, and a request
  `GET http://financial-agent-api.localhost.com/healthz` is visible, returning
  status 200 with content "ok", and the browser displays the response.
- **Given** all services are running,
  **when** a database connection is opened with a connection tool,
  **then** the `pgvector` extension is installed (`CREATE EXTENSION IF NOT EXISTS vector`
  succeeds without error).

### Explicit non-goals for this task

- Do not add anything to the API project beyond `/healthz`.
- Do not add anything to the UI project beyond the `/` page.

---

## Entities

| Entity | Notes for Task 0 |
|---|---|
| `financial-agent-api` | FastAPI service, only `GET /healthz` returning `{"status":"ok"}`. Uses `uv` for dependency management. |
| `financial-agent-ui` | Frontend placeholder page service, `/` displays placeholder info and requests API `/healthz` to display the response. |
| `financial-agent-db` | PostgreSQL 16 + pgvector extension. Uses `pgvector/pgvector:pg16` image. |
| `financial-agent-nginx` | HTTP reverse proxy, routes domains to corresponding services (ui/api). |
| `pgvector` | Postgres extension. Must be available in the chosen image; the `pgvector/pgvector:pg16` image is preferred for zero install steps. |
| `Settings` | Stub class only — declares the env keys, no business logic yet. Concretised in Task 1. |

### Deployment topology overview

Task 0 is the only Task that owns runtime *topology* rather than data
shapes, so the diagram is a class-level view of the bring-up: which
container talks to which.

```mermaid
classDiagram
direction LR

class Nginx {
  +HTTP reverse proxy
  +financial-agent-ui.localhost.com → ui:port
  +financial-agent-api.localhost.com → api:port
}

class UI {
  +placeholder page /
  +GET /healthz → API
}

class API {
  +FastAPI app
  +healthz() → 200
  +Settings settings
}

class Db {
  +postgres pg16
  +pgvector extension
  +PG_DSN endpoint
}

Nginx "1" --> "1" UI : reverse proxy
Nginx "1" --> "1" API : reverse proxy
UI "1" ..> "1" API : HTTP request
API "1" --> "1" Db : PG_DSN
```

---

## Approach

### Design decisions

1. The API project uses `uv` for version management.
2. The UI project uses the technology mentioned in the Root Constitution.
3. The NGINX project currently only needs HTTP. Its reverse-proxy domains are
   routed correctly by configuring entries in the hosts file. Therefore, at
   startup, check whether the corresponding hosts entries mapping to 127.0.0.1
   are configured. If not, prompt the user for sudo access to modify them.
4. All API project code lives under `<rootDir>/codebases/financial-agent-api`.
5. All UI project code lives under `<rootDir>/codebases/financial-agent-ui`.
6. All Docker Compose service-related files (Dockerfile, env, etc.) live under
   the corresponding `support` directory, e.g.
   `<rootDir>/support/financial-agent-nginx/financial-agent-api.localhost.com.conf`,
   `<rootDir>/support/financial-agent-api/Dockerfile`.
7. **`db` service uses the `pgvector/pgvector:pg16` image**. Avoid the
   "install extension at startup" dance by picking an image that already has
   the binary in place.
8. Dependency versions must reference the Root Constitution. If not defined
   there, use the latest mutually compatible stable versions.
9. In the API project, each module must have a corresponding test module that
   can be executed successfully.

### Trade-offs accepted

- The Dockerfile installs the full project venv inside the runtime image.
  That is wasteful but simple; Task 6's multi-stage build will shrink it.
- The repository structure is created upfront in this Task even though most
  folders will be empty until later Tasks touch them. This is intentional:
  keeping the layout stable from day one prevents AI from "discovering"
  alternative locations during code generation.

---

## Execution Plan

Execute the following steps in order:

1. **Scaffold API project** (`codebases/financial-agent-api/`): Use `uv` to manage
   the Python project, FastAPI framework, only `GET /healthz` endpoint returning
   `{"status":"ok"}`, include `tests/` test module.
2. **Scaffold UI project** (`codebases/financial-agent-ui/`): Basic placeholder page,
   `/` displays placeholder info, frontend requests
   `GET http://financial-agent-api.localhost.com/healthz` and displays the response.
3. **Scaffold Nginx reverse proxy**: Place `.conf` files under
   `support/financial-agent-nginx/`, route domains to corresponding services (HTTP only for now).
4. **Provision PostgreSQL database**: Use `pgvector/pgvector:pg16` image,
   service name `financial-agent-db`.
5. **Write Docker Compose**: Four services `financial-agent-api`, `financial-agent-ui`,
   `financial-agent-db`, `financial-agent-nginx`. `api` depends on `db`.
6. **Write `./start` launch script**: Check if `/etc/hosts` has the domain →
   127.0.0.1 mappings. If missing, prompt user for sudo access to add them.
   Then run `docker compose up`.
7. **Create project config files**: `.env.example`, `README.md` (quickstart, project layout, etc.).

---

## Structure

### Files this task creates or amends

```text
financial-agent-spdd_week_00/
├── start                                 # CREATE (one-click start script)
├── .env.example                          # CREATE
├── README.md                             # CREATE (skeleton)
├── docker-compose.yml                    # CREATE
├── codebases/
│   ├── financial-agent-api/              # CREATE (API project)
│   │   ├── pyproject.toml                # CREATE (uv project config)
│   │   ├── uv.lock                       # CREATE (uv lock file)
│   │   ├── src/
│   │   │   └── financial_agent_api/
│   │   │       ├── __init__.py           # CREATE
│   │   │       ├── main.py               # CREATE (FastAPI + /healthz)
│   │   │       └── core/
│   │   │           ├── __init__.py       # CREATE
│   │   │           └── config.py         # CREATE (Settings skeleton)
│   │   └── tests/
│   │       ├── __init__.py               # CREATE
│   │       └── test_health.py            # CREATE
│   └── financial-agent-ui/               # CREATE (UI project)
│       ├── package.json                  # CREATE
│       ├── public/
│       │   └── index.html                # CREATE (placeholder page)
│       └── src/
│           └── App.js                    # CREATE (calls API /healthz)
├── support/
│   ├── financial-agent-api/
│   │   └── Dockerfile                    # CREATE
│   ├── financial-agent-ui/
│   │   └── Dockerfile                    # CREATE
│   └── financial-agent-nginx/
│       ├── nginx.conf                    # CREATE
│       ├── financial-agent-api.localhost.com.conf   # CREATE
│       └── financial-agent-ui.localhost.com.conf    # CREATE
└── .spdd_specs/
    └── tasks/
        └── Task_0_Environment.trainee.md  # AMEND (this file)
```

### Existing files this task must respect

- All files under `.spdd_specs/` remain unchanged (except this file).
- All files under `trainee/` remain unchanged.

### Configuration shape

`.env.example`:

```dotenv
# Postgres connection
PG_DSN=postgresql+psycopg://app:app@financial-agent-db:5432/app

# Logging mode: 'json' for production, 'text' for local dev.
LOG_FORMAT=text

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma3:27b
OLLAMA_OPS_MODEL=qwen3.5:4b

# Embedding model
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768

# LLM provider
LLM_PROVIDER=ollama

# OpenRouter (optional)
# OPENROUTER_API_KEY=
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# OPENROUTER_MODEL=gpt-4.1-mini
```

#### Compute paths — pick whichever fits your machine

The curriculum is provider-agnostic. There is no "right" path; pick
the one that keeps your laptop fans honest and your tab open.

> **Note:** Cursor is no longer available for this curriculum. The
> paths below are ordered by cost-effectiveness; your existing
> setup is not negated.

1. **Company Copilot (default).** Apply for a GitHub Copilot or
   similar company coding-plan seat if available. No personal
   billing, fits your existing workflow.

2. **Opencode Go($5 1st Month, $10 following).** Low-cost
   subscription. Models: DeepSeek V4, Mimo v2.5, Minimax 3.
   The first month is $5; subsequent months are $10.

3. **Opencode Zen(Do not enable Billing).** Free, no billing
   setup needed. Built-in models provide good performance for
   curriculum work at zero cost.

4. **DeepSeek official top-up.** Directly recharge a DeepSeek
   account and use their API. Pay-as-you-go, no lock-in.

5. **Local Ollama / mlx-community-optiq.** Free and fully offline
   after pulling models, but slower on consumer hardware. On a
   16 GB Mac where `gemma3:27b` swaps badly, switching
   `OLLAMA_CHAT_MODEL=qwen3.5:4b` is a fully accepted fallback.
   Synthesis loses some flair; the curriculum still lands.

6. **Your existing Coding Plan subscription.** If you already
   use Cline, Continue, Windsurf, or another plan, it works fine.
   The curriculum does not mandate a specific provider.

---

## Operation Steps (strict execution order)

Your AI coding tool must perform these steps top-to-bottom and stop on the first
failure.

### Step 1: Scaffold API Project (`codebases/financial-agent-api/`)

1.1 Initialize the project with `uv init`, or manually create `pyproject.toml`.

1.2 `pyproject.toml` dependency configuration:

```toml
[project]
name = "financial-agent-api"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115,<0.120",
    "uvicorn[standard]>=0.30,<1.0",
    "pydantic>=2.7,<3.0",
    "pydantic-settings>=2.4,<3.0",
    "loguru>=0.7,<1.0",
    "httpx>=0.27,<1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-asyncio>=0.23,<1.0",
    "httpx[http2]>=0.27",
    "mypy>=1.10,<2.0",
    "ruff>=0.5,<1.0",
]
```

1.3 Create `src/financial_agent_api/__init__.py`,
   `src/financial_agent_api/core/__init__.py` (empty files).

1.4 Write `src/financial_agent_api/core/config.py` skeleton:

```python
"""Application configuration (skeleton — concretised in Task 1)."""

from typing import Literal
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pg_dsn: str
    llm_provider: Literal["ollama", "openrouter"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gemma3:27b"
    ollama_ops_model: str = "qwen3.5:4b"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    openrouter_api_key: str | None = None
    openrouter_model: str = "gpt-4.1-mini"
    log_format: Literal["json", "text"] = "text"

    @model_validator(mode="after")
    def _require_openrouter_key(self) -> "Settings":
        if self.llm_provider == "openrouter" and not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY required when LLM_PROVIDER=openrouter")
        return self


def get_settings() -> Settings:
    return Settings()  # Task 1 will replace with @lru_cache
```

1.5 Write `src/financial_agent_api/main.py`:

```python
"""Financial Helpdesk Agent — FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Financial Helpdesk Agent", version="0.0.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

1.6 Write `tests/__init__.py` (empty file).

1.7 Write `tests/test_health.py`:

```python
"""Tests for the /healthz endpoint."""

from fastapi.testclient import TestClient
from financial_agent_api.main import app

client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

1.8 Run `uv lock` to generate `uv.lock`, then `uv run pytest tests/` to verify
   tests pass.

### Step 2: Scaffold UI Project (`codebases/financial-agent-ui/`)

2.1 Create `package.json`, using a simple static HTML page (no heavy framework,
   in keeping with the "minimal surface area" principle).

2.2 Create `public/index.html` — placeholder page containing:
- Project title "Financial Helpdesk Agent"
- Placeholder information
- JavaScript calling `GET http://financial-agent-api.localhost.com/healthz`
  and displaying the response.

2.3 Create `src/App.js` (if using a framework like React), otherwise inline JS
   directly in `index.html`.

2.4 The UI project only needs to serve `/` returning this page via an HTTP server.

### Step 3: Scaffold Nginx Reverse Proxy (`support/financial-agent-nginx/`)

3.1 Create `nginx.conf` (main configuration).

3.2 Create `financial-agent-api.localhost.com.conf` — reverse proxy to
   `financial-agent-api:8000`.

3.3 Create `financial-agent-ui.localhost.com.conf` — reverse proxy to the
   `financial-agent-ui` service port.

3.4 HTTP only for now (port 80).

### Step 4: Write Dockerfiles for Each Service

4.1 `support/financial-agent-api/Dockerfile` — single-stage build, Python 3.11
   slim base image:
- Install `uv`
- Copy `pyproject.toml` and `uv.lock` first, install dependencies
- Then copy `src/`
- Run as non-root user
- CMD: `["uv", "run", "uvicorn", "financial_agent_api.main:app", "--host", "0.0.0.0", "--port", "8000"]`

4.2 `support/financial-agent-ui/Dockerfile` — based on nginx or node image,
   serving the static page.

### Step 5: Write `docker-compose.yml`

5.1 Four services: `financial-agent-api`, `financial-agent-ui`,
   `financial-agent-db`, `financial-agent-nginx`.

5.2 `financial-agent-db` uses `pgvector/pgvector:pg16` image, health check
   using `pg_isready`.

5.3 `financial-agent-api` depends on `financial-agent-db`
   (`condition: service_healthy`).

5.4 All services join the same Docker network, Nginx exposes port 80.

### Step 6: Write `./start` Launch Script

6.1 Check if `/etc/hosts` already has the following mappings:
```
127.0.0.1 financial-agent-ui.localhost.com
127.0.0.1 financial-agent-api.localhost.com
```

6.2 If missing, prompt the user and request sudo access to add them.

6.3 Run `docker compose up --build -d`.

6.4 Once all services are healthy, print the access URLs:
- UI: `http://financial-agent-ui.localhost.com`
- API healthz: `http://financial-agent-api.localhost.com/healthz`
- DB: `localhost:5432`

### Step 7: Create Project Config Files

7.1 Create `.env.example` (content per the configuration shape above).

7.2 Create `README.md` skeleton with sections: *Quickstart*, *Project Layout*,
   *Health Endpoints*.

### Step 8: Local Verification

8.1 Run `./start` to confirm all services start successfully.

8.2 Run `curl -fsS http://financial-agent-api.localhost.com/healthz` expecting
   `{"status":"ok"}`.

8.3 Browser visit `http://financial-agent-ui.localhost.com` to confirm the
   placeholder page displays correctly and the API request succeeds.

8.4 Enter `codebases/financial-agent-api/`, run `uv run pytest tests/` to confirm
   tests pass.

8.5 Connect to the database, execute `CREATE EXTENSION IF NOT EXISTS vector;` to
   confirm pgvector is installed.

---

## Norms

### API Project
- Folder packaging: every directory under `src/` and `tests/` has an
  `__init__.py` even if empty. This avoids implicit namespace packages
  and makes `mypy` happy.
- Python files start with a one-line module docstring describing intent.
- Configuration access is always through `get_settings()`; never read
  `os.environ` directly outside `config.py`.
- Imports order: standard library, third-party, local. One blank line
  between groups.
- Line length: 100 characters; enforced by `ruff` defaults.

### Docker
- Docker layer order is dependency-files-first, code-second. Bust the
  cache only on dependency changes.
- Dockerfiles live under `support/<service-name>/`, not in the code
  directories.

---

## Safeguards

### What this task must NOT do

1. **Do not add anything to the API project beyond `/healthz`.**
2. **Do not add anything to the UI project beyond the `/` page.**
3. **Do not pull `langgraph` or `langchain-core` into dependencies.**
   Those are Task 3 dependencies.
4. **Do not implement `LLMService` or `RetrievalService`.**
   Task 1 owns the LLM abstraction; Task 2 owns retrieval.
5. **Do not add a standalone vector-store service to `docker-compose.yml`.**
   `pgvector` runs inside the `db` Postgres container.
6. **Do not add `chroma`, `qdrant`, `weaviate`, or `faiss` to deps.**
7. **Do not bake secrets into images.** All secrets come from `.env`
   via `env_file` in compose.
8. **Do not create or modify any file under `data/`.** The starter
   corpus is read-only from this point onward.

### Error handling specifics

- If `docker compose up` fails because `pgvector/pgvector:pg16` is
  unavailable, fall back to `postgres:16` with an explicit `init.sql`
  that runs `CREATE EXTENSION vector;`. Document the fallback in
  `README.md`. Do not silently change the image without updating the
  README.
- If the `./start` script fails to modify `/etc/hosts`, print a clear
  error message and exit.

### Verification command (printed to the user at the end)

```bash
# 1. One-click start all services
./start

# 2. API health check
curl -fsS http://financial-agent-api.localhost.com/healthz   # expect {"status":"ok"}

# 3. UI page access
# Browser open http://financial-agent-ui.localhost.com

# 4. API project tests
cd codebases/financial-agent-api && uv run pytest tests/ -v

# 5. Database pgvector extension verification
# Connect using PG_DSN, then execute:
# CREATE EXTENSION IF NOT EXISTS vector;
```
