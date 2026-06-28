# Task 0 — 环境搭建（REASONS 画布）

> **映射到：** 学习计划第 0 周 — *环境搭建与项目骨架*。
> **依赖：** 仅依赖 `0_Root_Architecture.md`。
> **解锁：** `Task_1_Foundations.md`。

---

## 需求

### 分析上下文

**扫描到的领域关键词：** docker compose、FastAPI、postgres、
pgvector、healthz/readyz、env 文件。**已有的产物：**
`data/samples/complaints_sample.csv`、`data/raw_docs/*.txt`、
`.env.example`。**已阅读的前置任务：** 无 — Task 0 是启动任务。

**策略方向：** 将 Day-1 的覆盖面保持在最小范围。
一个 Dockerfile、一个 compose 文件、一个 `/healthz` 端点，无业务
逻辑。任何可以推迟到 Task 1（LLM 服务、Settings 类）的内容一律推迟。

**注意到的风险：** (1) pgvector 镜像变体很关键 — 如果镜像不是多架构的，
Apple Silicon Mac 上的 ARM 兼容性会很脆弱；(2) `.env.example` 必须列出
后续所有 Task 会用到的每一个环境变量键，即使 Task 0 本身不使用它们，
这样就不需要每周都去编辑示例文件。

### 为什么需要这个任务

一个初级开发者应该能够从干净的仓库克隆中运行 `docker compose up`，
并在几分钟内看到一个健康的服务栈。Agent 在后续任务中的正确性依赖于
一个可复现的运行时环境，后续的每一个组件（Postgres、embeddings、
LangGraph、评估）都接入同一个容器拓扑。没有这个脚手架，下游的每个
Task 都会花时间在基础设施上折腾，而不是构建功能。

### 验收标准（Given/When/Then）

- **给定** 仓库的一个干净克隆、一个包含 `PG_DSN` 和指向 Ollama 的
  模型字段的已填充 `.env` 文件，以及一个正在运行的本地 `ollama` 
  守护进程（或者如果开发者使用 OpenRouter 逃生通道，则需要
  `OPENROUTER_API_KEY`），
  **当** 开发者运行 `docker compose -f infra/docker-compose.yml up --build` 时，
  **那么** `app` 和 `db` 两个服务都应达到健康状态，并且
  `curl http://localhost:8000/healthz` 返回 `{"status": "ok"}`，
  HTTP 状态码为 200。
- **给定** `db` 服务正在运行，
  **当** 使用项目的 `PG_DSN` 打开一个连接时，
  **那么** `pgvector` 扩展已安装（`CREATE EXTENSION IF NOT EXISTS vector`
  能无错误地成功执行）。
- **给定** 测试套件通过 `pytest tests/test_health.py` 调用，
  **当** 它不依赖任何外部服务运行时，
  **那么** 所有测试在不访问网络的情况下通过。
- **给定** 开发者运行 `python -m data_pipelines.ingest_tables.build_starter_sample`
  *以及* `python -m data_pipelines.ingest_docs.fetch_starter_docs`，
  **当** 现有脚本完成后，
  **那么** 生成的 CSV 和 `.txt` 文件在形状上与数据准备阶段结束时
  产生的结果保持不变（1,000 行，4 个产品 × 250 条，
  `data/raw_docs/` 中有三个文本文件）。

### 本任务的明确非目标

- 不实现 LLM 客户端（Task 1）。
- 不实现检索逻辑、不实现 LangGraph 节点、不实现 prompts。
- 不做生产环境的密钥管理。本地 `.env` 文件就足够了。

---

## 实体

| 实体 | Task 0 注意事项 |
|---|---|
| `Settings` | 仅做桩类 — 声明环境变量键，暂时无业务逻辑。在 Task 1 中具体实现。 |
| `pgvector` | Postgres 扩展。必须在所选镜像中可用；首选 `pgvector/pgvector:pg16` 镜像，无需安装步骤。 |
| `request_id` | 保留关键字。`/healthz` 处理函数暂时不需要发出它，但 FastAPI 应用必须已附加一个占位中间件，以便 Task 1 可以扩展它。 |
| 已有数据产物 | `data/samples/complaints_sample.csv`、`data/raw_docs/*.txt`。**Task 0 不得触碰这些文件。** 仅确认目录布局存在。 |

### 部署拓扑概览

Task 0 是唯一拥有运行时*拓扑*（而非数据形态）的 Task，
因此该图是启动过程的类级别视图：哪些容器与哪些容器通信，
以及哪些环境变量键跨越了哪些边界。

```mermaid
classDiagram
direction LR

class App {
  +FastAPI app
  +healthz() 200
  +Settings settings
}

class Db {
  +postgres pg16
  +pgvector extension
  +PG_DSN endpoint
}

class Ollama {
  +host daemon (不在 compose 中)
  +OLLAMA_BASE_URL
}

class StarterCorpus {
  <<只读>>
  +complaints_sample.csv
  +raw_docs/*.txt
}

class Settings {
  +str PG_DSN
  +str LLM_PROVIDER
  +str OLLAMA_BASE_URL
  +str EMBEDDING_MODEL
  +int EMBEDDING_DIM
}

App "1" --> "1" Db          : PG_DSN
App "1" ..> "1" Ollama      : OLLAMA_BASE_URL (Task 1+)
App "1" ..> "1" StarterCorpus : 读取 (Task 2+)
App "1" *-- "1" Settings    : 拥有
```

---

## 方案

### 设计决策

1. **`Dockerfile.app` 采用单阶段构建**，而非多阶段构建，在本 Task 中。
   在有真正的 Python 代码需要优化构建缓存之前，保持镜像简单。
   多阶段优化放在 Task 6，与其余的生产环境加固一起完成。
2. **`db` 服务使用 `pgvector/pgvector:pg16` 镜像**。通过选择已内置
   扩展二进制文件的镜像，避免"启动时安装扩展"的额外步骤。
3. **暂时不添加 `langgraph` 依赖。** 现在固定版本可能会导致版本变化
   在 Task 3 中引发问题。在 Task 3 中再添加。
4. **健康检查是一个简单的处理函数。** `GET /healthz` *不*检查数据库。
   一个单独的 `GET /readyz` 处理函数将在 Task 1 中添加，以便部署能
   区分"进程是存活的"和"下游依赖可达"。
5. **`.env.example` 存放在仓库中，`.env` 不存放。** 开发者复制示例
   文件。CI 直接使用环境变量。

### 已接受的权衡

- Dockerfile 在运行时镜像中安装完整的项目 venv。这是浪费但简单的做法；
  Task 6 的多阶段构建将缩小镜像体积。
- 仓库结构在本 Task 中预先创建，即使大多数文件夹在后续 Task 中才会
  填充。这是有意为之：从一开始保持布局稳定，防止 AI 在代码生成过程中
  "发现"替代位置。

---

## 结构

### 本任务创建或修改的文件

```text
financial-agent/
├── pyproject.toml                       # 修改（扩展现有内容）
├── poetry.lock                          # 创建
├── .env.example                         # 创建
├── README.md                            # 创建（骨架）
├── infra/
│   ├── docker/
│   │   └── Dockerfile.app               # 创建
│   └── docker-compose.yml               # 创建
├── app/
│   ├── __init__.py                      # 创建
│   ├── api/
│   │   ├── __init__.py                  # 创建
│   │   └── main.py                      # 创建（仅 healthz）
│   ├── core/
│   │   ├── __init__.py                  # 创建
│   │   └── config.py                    # 创建（骨架）
│   ├── services/
│   │   └── __init__.py                  # 创建
│   └── tools/
│       └── __init__.py                  # 创建
└── tests/
    ├── __init__.py                      # 创建
    └── test_health.py                   # 创建
```

### 本任务必须尊重的已有文件

- `pyproject.toml` 已声明 `httpx>=0.27,<1.0`。在原位置扩展；
  不要从头重写。
- `data_pipelines/__init__.py`、`data_pipelines/ingest_tables/__init__.py`、
  `data_pipelines/ingest_docs/__init__.py` 已存在。保持不动。
- `.gitignore` 已存在。仅在需要时追加条目。
- `.venv/` 由开发者创建；不要提交它。

### 配置形态

`.env.example`：

```dotenv
# 提供商策略：Ollama 为主要方案，OpenRouter 为可选逃生通道。
LLM_PROVIDER=ollama

# Postgres 连接。主机使用 loopback 用于在 compose 外部运行的
# 数据导入/评估脚本；在 compose 网络内部覆盖为 db:5432。
PG_DSN=postgresql+psycopg://app:app@localhost:5432/app

# 日志模式：'json' 用于生产环境，'text' 用于本地开发。
LOG_FORMAT=text

# Ollama（本地）— 将 OLLAMA_CHAT_MODEL 设置为 `ollama list` 显示的内容。
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma3:27b
OLLAMA_OPS_MODEL=qwen3.5:4b

# 嵌入模型。nomic-embed-text -> 768 维。如果更改模型，
# 请更新 EMBEDDING_DIM 并重新应用模式（不可变的列类型）。
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768

# OpenRouter（可选）。仅当 LLM_PROVIDER=openrouter 时需要。
# OPENROUTER_API_KEY=
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# OPENROUTER_MODEL=gpt-4.1-mini
```

#### 计算路径 — 选择适合你机器的方式

课程大纲是与提供商无关的。没有"正确"的路径；选择能让你的
笔记本风扇保持安静、浏览器标签保持打开的那个。

> **注意：** Cursor 不再适用于本课程。以下路径按性价比排序；
> 你现有的设置不受影响。

1. **公司 Copilot（默认）。** 如果有的话，申请一个 GitHub Copilot
   或类似的公司编码计划席位。无需个人付费，适配你现有的工作流。

2. **Opencode Go（首月 $5，后续 $10）。** 低成本订阅。
   模型：DeepSeek V4、Mimo v2.5、Minimax 3。
   首月 $5，后续月份 $10。

3. **Opencode Zen（不要启用计费）。** 免费，无需设置计费。
   内置模型在课程工作中提供良好性能，零成本。

4. **DeepSeek 官方充值。** 直接充值 DeepSeek 账户并使用其 API。
   按量付费，无绑定。

5. **本地 Ollama / mlx-community-optiq。** 拉取模型后完全免费
   且离线运行，但在消费级硬件上较慢。在 16 GB Mac 上，
   如果 `gemma3:27b` 交换严重，切换为 `OLLAMA_CHAT_MODEL=qwen3.5:4b`
   是完全可接受的降级方案。生成质量会有所下降；课程大纲仍然可用。

6. **你现有的编码计划订阅。** 如果你已经在使用 Cline、Continue、
   Windsurf 或其他计划，它们都能正常工作。课程大纲不强制要求特定提供商。

### `infra/docker-compose.yml` 骨架（目标形态）

```yaml
version: "3.9"

services:
  app:
    build:
      context: ..
      dockerfile: infra/docker/Dockerfile.app
    env_file: ../.env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  db_data:
```

---

## 操作步骤（严格按顺序执行）

你的 AI 编码工具必须从上到下执行这些步骤，并在第一个失败处停止。

1. **扩展 `pyproject.toml`。** 添加 Task 0/1 的运行时依赖：

   ```toml
   [project]
   dependencies = [
       "httpx>=0.27,<1.0",
       "fastapi>=0.115,<0.120",
       "uvicorn[standard]>=0.30,<1.0",
       "pydantic>=2.7,<3.0",
       "pydantic-settings>=2.4,<3.0",
       "loguru>=0.7,<1.0",          # 或 structlog；选择其一
   ]

   [project.optional-dependencies]
   dev = [
       "pytest>=8.0,<9.0",
       "pytest-asyncio>=0.23,<1.0",
       "httpx[http2]>=0.27",        # 用于 ASGI 测试客户端
       "mypy>=1.10,<2.0",
       "ruff>=0.5,<1.0",
   ]
   ```

   如果使用 Poetry，生成 `poetry.lock`；否则在 `README.md` 中
   记录 `uv` 等效命令。

2. **搭建包结构。** 为 `app/`、`app/api/`、`app/core/`、
   `app/services/`、`app/tools/` 和 `tests/` 创建空的
   `__init__.py` 文件。暂时不要创建 `app/core/prompts/` 文件夹
   （Task 4 的工作）。

3. **编写 `app/core/config.py` 骨架。**

   ```python
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
               raise ValueError("当 LLM_PROVIDER=openrouter 时需要 OPENROUTER_API_KEY")
           return self

   def get_settings() -> Settings:
       return Settings()  # Task 1 将替换为 @lru_cache
   ```

   无业务逻辑；这只是为了让 FastAPI 应用可以导入它。

4. **编写 `app/api/main.py`，包含一个路由。**

   ```python
   from fastapi import FastAPI

   app = FastAPI(title="Financial Helpdesk Agent", version="0.0.0")

   @app.get("/healthz")
   def healthz() -> dict[str, str]:
       return {"status": "ok"}
   ```

5. **编写 `infra/docker/Dockerfile.app`。** 单阶段 Python 3.11
   slim 基础镜像。安装 Poetry（或 `uv`），先复制 `pyproject.toml`
   和 `poetry.lock`，安装依赖，然后复制 `app/`。以非 root 用户运行。
   最终命令：

   ```dockerfile
   CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

6. **编写 `infra/docker-compose.yml`**，匹配上面的骨架。

7. **编写 `.env.example`**，匹配上面的配置形态。

8. **编写 `README.md` 骨架。** 章节：*快速开始*、*项目布局*、
   *数据准备*、*健康端点*。快速开始命令：

   ```bash
   cp .env.example .env
   # 如果使用 Ollama（默认）：一次性拉取模型
   #   ollama pull gemma3:27b
   #   ollama pull qwen3.5:4b
   #   ollama pull nomic-embed-text
   # 如果使用 OpenRouter：设置 OPENROUTER_API_KEY 和 LLM_PROVIDER=openrouter
   docker compose -f infra/docker-compose.yml up --build
   curl http://localhost:8000/healthz
   ```

9. **编写 `tests/test_health.py`。** 使用 FastAPI 的 `TestClient`
   访问 `/healthz` 并断言 JSON 响应体。不得直接导入 `Settings`，
   以便在没有设置环境变量的情况下也能运行。

10. **本地验证。** 运行 `pytest tests/test_health.py` *以及*
    `docker compose -f infra/docker-compose.yml up --build`
    （后台运行；开发者可以 `Ctrl-C` 结束）。确认两者均成功。

11. **打印最终摘要**，列出创建的文件、修改的文件以及用户可以
    重新运行的验证命令。

---

## 规范

- 文件夹打包：`app/` 和 `tests/` 下的每个目录都有一个 `__init__.py`，
  即使是空的。这避免了隐式命名空间包，并使 `mypy` 满意。
- Python 文件以一行描述意图的模块文档字符串开头。
- 配置访问始终通过 `get_settings()` 进行；绝不在 `config.py` 外部
  直接读取 `os.environ`。
- 导入顺序：标准库、第三方、本地。各组之间空一行。
- 行长度：100 个字符；由 `ruff` 默认值强制执行。
- Docker 层顺序是依赖文件优先，代码其次。仅在依赖变更时使缓存失效。

---

## 防护措施

### 本任务不得做的事

1. **不得创建或修改 `data/` 下的任何文件。** 从此处开始，入门语料库
   是只读的。
2. **不得将 `langgraph` 或 `langchain-core` 加入 `pyproject.toml`。**
   这些是 Task 3 的依赖。
3. **不得实现 `LLMService` 或 `RetrievalService` 桩。** Task 1 拥有
   LLM 抽象；Task 2 拥有检索。
4. **不得向 `docker-compose.yml` 添加向量存储服务。** `pgvector`
   在 `db` Postgres 容器内运行。
5. **不得向依赖中添加 `chroma`、`qdrant`、`weaviate` 或 `faiss`。**
6. **不得添加 Streamlit。** UI 是 Task 5 的工作。
7. **不得添加数据库迁移工具**（不添加 Alembic，不添加 Atlas）。
   模式创建属于 Task 2 的首次数据导入脚本。如果 AI 能在画布中
   证明其合理性，迁移工具可以在 Task 6 中引入。
8. **不得将密钥写入镜像。** 所有密钥通过 compose 中的 `env_file`
   从 `.env` 获取。
9. **不得在 CI 中默认运行需要网络的测试。** 将它们标记为
   `@pytest.mark.network`，并除非设置了环境变量标志，否则跳过。

### 错误处理细节

- 如果 `docker compose up` 因 `pgvector/pgvector:pg16` 不可用而失败，
  降级使用 `postgres:16`，并添加一个显式的 `init.sql` 来运行
  `CREATE EXTENSION vector;`。在 `README.md` 中记录该降级方案。
  不要在不更新 README 的情况下静默更改镜像。
- 如果 `pyproject.toml` 中已包含一个与本画布要求版本不同的依赖，
  在运行日志中提出冲突并停止；不要通过升级或降级来"自动解决"。

### 验证命令（在最后打印给用户）

```bash
cp .env.example .env  # 然后要么启动 `ollama serve`（默认），要么
                       # 设置 OPENROUTER_API_KEY + LLM_PROVIDER=openrouter
pytest tests/test_health.py
docker compose -f infra/docker-compose.yml up --build
curl -fsS http://localhost:8000/healthz   # 期望返回 {"status":"ok"}
```
