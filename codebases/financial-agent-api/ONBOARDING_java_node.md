# Financial Agent API Onboarding（面向 Java / Node 开发者）

这份文档帮你快速把这个 Python API 项目映射到你熟悉的 Java（Spring）/Node（Express/Nest）思维模型，并能本地跑起来、调试、跑 UT。

## 1. 先建立心智模型（Java/Node -> Python）

| 你熟悉的概念                                                        | 本项目对应                                                |
|---------------------------------------------------------------|------------------------------------------------------|
| Spring Boot `@ConfigurationProperties` / Node `dotenv` config | `core/config.py` 的 `Settings`（Pydantic Settings）     |
| Spring `@Controller` / Express route handler                  | `main.py` 里的 FastAPI endpoint（`/healthz`, `/readyz`） |
| Servlet Filter / Express middleware                           | `request_id_middleware`                              |
| Service 层                                                     | `services/llm_service.py`                            |
| HTTP Client（WebClient / axios）                                | `services/llm_client.py`（基于 `httpx.AsyncClient`）     |
| 全局异常对象                                                        | `core/exceptions.py`                                 |
| 应用启动生命周期钩子                                                    | FastAPI `lifespan`                                   |

---

## 2. 项目结构（只看 API）

```text
codebases/financial-agent-api/
├── src/financial_agent_api/
│   ├── main.py                      # 应用入口、lifespan、中间件、健康检查
│   ├── core/
│   │   ├── config.py                # Settings + get_settings()（缓存）
│   │   ├── logging.py               # JSON/Text 日志 + request_id ContextVar
│   │   ├── exceptions.py            # LLMProviderError / LLMOutputValidationError
│   │   └── services_container.py    # 轻量服务容器
│   └── services/
│       ├── llm_client.py            # 底层 HTTP 封装
│       └── llm_service.py           # Provider 无关 LLM facade
├── tests/
│   ├── test_config.py
│   ├── test_logging.py
│   ├── test_llm_service.py
│   └── test_health.py
├── .env.example
└── pyproject.toml
```

---

## 3. 本地运行（推荐命令）

> 本项目使用 `uv` 管理依赖和运行命令，类似 Node 的 `pnpm dlx` / Java 的 wrapper 思路。

```bash
cd codebases/financial-agent-api
cp .env.example .env
uv sync --dev
uv run uvicorn financial_agent_api.main:app --app-dir src --reload
```

启动后：

- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/readyz`

---

## 4. 运行 UT / 质量检查

```bash
cd codebases/financial-agent-api

# 单元测试
uv run pytest -q

# Lint
uv run ruff check .

# 严格类型检查
uv run mypy --strict --explicit-package-bases src
```

---

## 5. 配置说明（`.env`）

核心变量（见 `.env.example`）：

- `LLM_PROVIDER=ollama|openrouter`
- `LOG_FORMAT=text|json`
- `OPENROUTER_API_KEY`（仅 `openrouter` 模式必填）
- `OPENROUTER_BASE_URL`、`OPENROUTER_MODEL`
- `OLLAMA_BASE_URL`、`OLLAMA_CHAT_MODEL`、`OLLAMA_OPS_MODEL`

配置加载入口：`financial_agent_api.core.config.get_settings()`  
它带 `@lru_cache(maxsize=1)`，相当于“进程内单例配置对象”。

---

## 6. 请求链路（一次调用发生了什么）

1. 请求进入 FastAPI
2. `request_id_middleware` 读取/生成 `X-Request-Id`
3. `bind_request_id()` 存入 `ContextVar`
4. 业务日志自动带 `request_id`
5. 响应返回时写回 `X-Request-Id` 响应头

这相当于 Java MDC / Node AsyncLocalStorage 的 request correlation。

---

## 7. LLM 调用逻辑（你最可能改的部分）

`LLMService.complete()` 做了这些事：

1. 读取 provider（openrouter / ollama）
2. 构造 provider 对应 payload
3. 调用 `LLMHTTPClient.request()`
4. 失败时按策略处理：
    - 重试：HTTP 5xx、`httpx.RequestError`、`httpx.TimeoutException`
    - 不重试：HTTP 4xx（含 429）
    - 最大尝试数：3（指数退避 + jitter）
5. 统一抛 `LLMProviderError`（携带 provider / status_code / payload / request_id）

---

## 8. 调试建议（Java/Node 背景常踩坑）

1. **“命令找不到 pytest”**：不要直接 `pytest`，统一用 `uv run pytest -q`。
2. **“配置和我想的不一样”**：`Settings` 默认会读取当前目录 `.env`；跑测试时注意工作目录。
3. **“日志没带 request_id”**：确认请求经过了中间件，且日志通过标准 `logging` 输出。
4. **“openrouter 模式启动报错”**：检查 `OPENROUTER_API_KEY` 是否配置。
5. **“切 provider 后行为不一致”**：先看 `llm_service.py` 中 `_path_for_provider` 和 `_extract_content`。

---

## 9. 快速上手改造路径（建议）

1. 先跑通本地服务 + 全量 UT
2. 改一个最小点（例如新增 `/v1/chat/ping`）
3. 给新逻辑补测试（优先 MockTransport，不要真实外网请求）
4. 跑 `pytest + ruff + mypy` 再提交

这条路径最稳，能快速适应 Python/FastAPI 的开发反馈循环。
