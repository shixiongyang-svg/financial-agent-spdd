# 任务 1 — 基础设施（REASONS 画布，学员版）

> **学员版说明。** 这是你在第 1 周第 1 天收到的画布。它被**有意地在某些地方描述不足** —
> 缺失的细节就是你在分析步骤 + 画布补全练习中需要完成的工作。本任务的最终版本位于
> `Task_1_Foundations.md`；在导师签收本画布之前，不要阅读那个文件。在生成代码之前必须完成
> 标记为 **TODO(trainee)** 的章节。
>
> **对应：** 学习计划第 1 周 — *Python 基础设施与服务抽象*。
> **依赖：** `Task_0_Environment.md`（已完成，与最终版本相同）。
> **解锁：** `Task_2_Ingestion.trainee.md`、`Task_3_Orchestration.trainee.md`。

**✅ 状态：已Approved**

---

## 需求

### 分析上下文

**扫描到的领域关键词：** LLMService、OpenRouter、Ollama、
embeddings、settings、request_id、结构化日志、重试。
**现有产出物：** `.env.example`（不存在，待本任务创建）、`app/` 骨架（不存在；实际代码位于 `codebases/financial-agent-api/src/financial_agent_api/`，当前仅有 `main.py` 含 `/healthz` 端点及空 `__init__.py`，无 `core/`、`services/` 子目录）。
**已阅读的前置任务：** 任务 0（`/healthz` 端点、CORSMiddleware、FastAPI 项目骨架；settings 桩代码**不存在**）。

**战略方向：** 一个提供商无关的外观层，统一处理对话 +
嵌入，通过 `Settings` 配置。重试和结构化输出解析隐藏在外观层
背后，调用方永远不需要关心。错误采用类型化异常，调用方可以
根据类型决定策略，而不需要解析错误消息字符串。

**TODO(trainee) — 风险识别。** 在编写任何代码之前，列出
**至少三个**你认为本任务引入的风险，以及你的设计如何缓解
这些风险。可以参考的风险类型示例：提供商响应格式漂移、
重试导致的成本放大、request_id 关联断链、日志中的密钥
泄露。在发起 PR 之前，将你的答案以编号列表的形式写在这里。

1. 目前未引入多环境配置
2. 环境变量中的明文配置
3. API KEY过期，超出限额之后的持续错误处理
4. 并没有提到如何限定LLM回复的固定格式
5. 返回消息解析失败后，缺少失败原因分析，比如，是否是因为结构化的输入消息构造不符合预期，或者LLM出现了偶尔的出现的问题，导致返回结果不是预期的情况，这种错误是否可以再一次交给LLM分析后，优化输入消息
6. 没有使用到 AsyncClient 级别的日志拦截器，修改日志时，漏掉需要修改的位置
7. Setting在所有环境都直接支持python -c调用导致配置信息泄漏，应该有额外限制
8. Retry的节点控制，避免嵌套Retry
9. 日志中截断的提示词，实际上在某些场景下是很重要的信息，是否应该根据场景，考虑在某个地方进行全量存储？

### 为什么有这个任务

智能体需要**一个统一的地方**知道如何与 LLM 对话，以及
**一个统一的地方**知道如何读取配置。没有这些抽象，每个
检索/合成/评估脚本都会直接耦合到 OpenRouter 或 Ollama，
导致代码库无法测试、无法推理、无法切换提供商。
任务 1 还引入了结构化日志契约，所有下游模块都依赖它
来实现可观测性和请求关联。

### 验收标准（Given/When/Then）

以下为契约，不得放宽。

- **Given** `.env` 中有有效的环境变量，
  **when** 运行 `python -c "from app.core.config import get_settings;
  print(get_settings().openrouter_model)"`，
  **then** 正常打印配置的模型名称，不抛出异常。
- **Given** `LLM_PROVIDER=openrouter` 且缺少
  `OPENROUTER_API_KEY`，
  **when** 调用 `get_settings()`，
  **then** Pydantic 从 `model_validator` 中抛出 `ValueError`
  并指出缺失的键。（在 `LLM_PROVIDER=ollama` 下该键是可选的。）
- **Given** 一个配置为 OpenRouter 的 `LLMService` 实例，以及一个
  模拟底层 `httpx.AsyncClient` 的测试，
  **when** 调用 `await llm.complete(messages=[{"role":"user","content":"hi"}])`，
  **then** 被模拟的 HTTP 层收到一个发送至
  `https://openrouter.ai/api/v1/chat/completions` 的 POST 请求。
- **Given** 一个配置为 Ollama 的 `LLMService` 实例，以及一个
  模拟底层 `httpx.AsyncClient` 的测试，
  **when** 调用 `await llm.complete(...)`，
  **then** 被模拟的 HTTP 层收到一个发送至
  `http://localhost:11434/api/chat` 的 POST 请求，并解包 `message.content`。
- **Given** 一个瞬态的 HTTP 5xx 响应，
  **when** `LLMService.complete` 运行，
  **then** 调用以指数退避重试，最多 **3 次尝试**，
  之后抛出 `LLMProviderError`。
- **Given** 任何服务或 LangGraph 节点记录结构化事件，
  **when** `LOG_FORMAT=json`，
  **then** 每条记录至少包含 `timestamp`、`level`、
  `request_id`、`event`，以及（在适用情况下）`duration_ms`。

---

## 实体

| 实体                         | 规格说明                                                                     |
|----------------------------|--------------------------------------------------------------------------|
| `Settings`                 | 根架构中列出的环境变量的 Pydantic Settings 模型。                                       |
| `LLMService`               | 提供商无关的外观层。两个方法：`complete`（对话）和 `embed`（批量嵌入）。                            |
| `LLMProviderError`         | 自定义异常。携带 `provider`、`status_code`、`payload`、`request_id`。                |
| `LLMOutputValidationError` | 自定义异常，在结构化输出解析失败时抛出。（在任务 4 中使用，但在此定义。）                                   |
| `request_id`               | UUIDv4。由中间件生成。注入到每一行日志中。                                                 |
| `ServicesContainer`        | 普通数据类，绑定 `Settings` + `LLMService`。在 `app/api/main.py` 的 lifespan 中构造一次。 |

### 类图 — TODO(trainee)

> 宪章中的 *SPDD 纪律* 规范要求每个任务画布在实体章节中附带
> 一个 `classDiagram`（或当拓扑为图结构时使用 `flowchart`）。
> 在生成代码之前，使用 Mermaid 在此绘制一个。建议的形状：
> `Settings`、`LLMService`、`ServicesContainer`、
> `LLMProviderError`、`LLMOutputValidationError`。展示包含关系
> （`ServicesContainer` *拥有* `Settings`、`LLMService`）和
> 依赖关系（`LLMService` *抛出* 两种异常；`LLMService`
> *读取* `Settings`）。

---

## 方案

### 设计决策

1. **单一的 `Settings` 类**，使用 Pydantic `model_validator`
   在缺少必需环境变量时提前报错。代码库中不存在分散的
   逐模块环境变量读取。
2. **一个 `LLMService` 外观层**，包含两个方法（`complete`、
   `embed`）。提供商差异（Ollama vs OpenRouter）存在于
   服务*内部*；调用方永远看不到。
3. **一个薄 HTTP 层**（`LLMHTTPClient` 封装
   `httpx.AsyncClient`），以便测试可以通过 `httpx.MockTransport`
   进行替换，而不需要猴子补丁整个网络栈。
4. **类型化异常**（`LLMProviderError`、
   `LLMOutputValidationError`），使调用方按类型分支，而不是
   解析错误字符串。
5. **通过 ContextVar 实现结构化日志。** 一个 `request_id`
   中间件在 API 入口处绑定该 id；日志记录器从
   ContextVar 中读取。不需要在每个函数签名中传递 id。

### TODO(trainee) — 接受的权衡

> 列出你选择的设计所接受的权衡。提示：思考
> 重试预算 vs 延迟、日志量 vs 可追踪性、
> Pydantic 验证的严格性 vs 开发者体验，以及
> 结构化输出强制执行 vs LLM 合规性。**至少三项**，
> 每项以 *"我们接受 X 因为 Y，尽管 Z"* 的形式表述。
> 这个列表是你的审阅者在代码审查中会对照检查的内容。

#### 重试预算 vs 延迟

在LLMService经由不同的提供商借助LLMHttpClient发送请求时，不可避免的会出现比如网络波动导致/请求超时等可以重试的错误。
每次重试，会额外消耗token，且Token消耗和Prompt大小有关，因此要控制重试次数和针对不同大小Prompt使用不同的重试策略。
另外，在控制请求时间不要过长的前提下，每次延迟的时间越长，则最终可以重试的次数越少

因此，最终，我们要考虑合理的重试预算来决定在总时长一定，根据不同的Prompt来决定重试策略。

##### 思考维度

1. 哪些错误是可以重试的
2. 多大的Prompt进行几次重试？
3. Prompt的大小和使用token情况进行关联是否合理，如果合理，是否应该根据Prompt来决定在时长一定的情况下的重试次数？

##### 可选方案

（由AI填充）

**方案 A：固定次数 + 固定退避间隔**
- 重试 3 次，每次等待固定 1s
- 实现最简单；对小 Prompt 浪费等待，对大 Prompt 可能不够
- 适合概念验证阶段

**方案 B：固定次数 + 指数退避（含 jitter）**
- 重试 3 次，退避时间 = min(base × 2^attempt + random_jitter, max_wait)，如 1s→2s→4s
- 符合验收标准（最多 3 次），指数退避避免服务端雪崩，jitter 避免惊群
- 不区分 Prompt 大小；通过全局 `timeout` 参数兜底整体耗时
- **本阶段推荐**：实现清晰，与 httpx 的 `timeout` 正交配合

**方案 C：基于 Prompt token 估算的动态重试预算**
- 粗估 token 数（字符数 / 4），token > 阈值时减少重试次数
- 更精细控制成本，但需维护阈值策略，过早引入复杂度
- 适合任务 4+ Prompt 较大时再引入

##### 最终选择

我们接受方案B，因为方案B考虑了等待，也使用了timeout进行兜底确保不会因为指数避让导致时间过长，且实现成本更小，尽管没有根据Prompt动态估算token数来决定重试次数，从而在某种程度上节省Token

#### 日志量 vs 可追踪性

在使用日志追中的过程中，如果过多的日志虽然会提高可追踪性，但是会导致日志量倍增，反之亦然。
因此，可以首先对代码进行逻辑单元拆分。
同一个逻辑单元则只需要输入和输出的日志即可（我们认为逻辑单元都是可以进行单元测试或者手动测试的，只要有输入+输出，就可以复现任意一个请求）。

我们可以认为同一个进程上下文在没有被其他逻辑单元分割的情况下，认为是一个逻辑单元，比如

一个由其他进程调用的方法入口是逻辑单元的输入，方法返回，则为逻辑单元的输出。
在一个进程内，如果开启了其他进程的请求，比如，另外一个线程，一个Http请求，这种则认为是开启了另外一个逻辑单元，则要对调用时的参数和得到的返回结果进行日志打印。

##### 可选方案

（由AI填充）

**方案 A：全链路 DEBUG 日志**
- 每个中间步骤都打 `logger.debug`；生产关闭 DEBUG 级别
- 可追踪性最高，但日志量大，I/O 压力大

**方案 B：逻辑单元边界日志（仅输入 + 输出）**
- 只在逻辑单元的入口（参数）和出口（返回值 / 异常）各打一条 INFO
- 每条日志携带 `request_id`，可完整复现任意一次请求
- 与本文档"日志量 vs 可追踪性"分析结论一致；**本阶段推荐**

**方案 C：结构化采样日志**
- 生产按一定比例采样（如 1%）打 DEBUG；100% 打 INFO 边界日志
- 灵活，但需要采样基础设施支持，当前阶段过重

##### 最终选择

我们接受方案B，因为其日志量更少，且满足了可追踪性的基本要求，同时实现成本相对更小，尽管少了详细DEBUG日志

#### Pydantic 验证的严格性 vs 开发者体验

关于这个方向，我认为可以权衡的点并不多，从数据的角度出发，所有必要的数据验证都应该有，即使很麻烦，开发者也应该遵循，尤其是在AI的帮助下，不应该有很大的重复开发负担。

但是，仍然有一部分我认为是可以考虑的，比如在校验基础的数据格式的前提条件下，应该尽量放宽限制，比如，电话号码，只需要是数字即可，而不需要校验电话的长度，开头，等之类的。

##### 可选方案

（由AI填充）

**方案 A：全量严格校验**
- 对 URL 格式、API key 前缀（`sk-or-`）、model 名称合法字符等逐一添加 `@field_validator`
- 最早发现配置错误，但开发者调试时频繁遇到校验失败；维护成本高

**方案 B：仅校验必填字段存在性 + 基本类型**
- `model_validator` 只做"openrouter 模式下 api_key 不能为空"；其他字段只做 Pydantic 的类型推断
- 开发者友好，错误在运行时才被外部系统拒绝
- **本阶段推荐**：符合文档中"校验基础数据格式，尽量放宽限制"的原则

**方案 C：分层校验（Settings + 运行时 guard）**
- Settings 只做最基础校验；在 `LLMHTTPClient` 初始化时再做运行时检查（如 URL 可达性 ping）
- 将配置校验和服务可用性校验分离，但增加了启动时间

##### 最终选择

我们接受方案B，因为其保证了必填信息的存在和类型的正确，尽管其无法保证配置信息的有效性，但是任何配置信息都应该在上线时，进行人工/自动化测试确保其有效性。

#### 结构化输出强制执行 vs LLM 合规性

我们应该追求输出的确定性，即要么确定性的正确输出，要么时确定性的失败，而不是成功时，但是输出并不是预期的情况。

如果模型不支持，我们未来可以通过引入一些中间件，来兼容结构化输出prompt到自觉性prompt的转换和可能出现的非结构化输出到结构化输出的转换。

##### 可选方案

（由AI填充）

**方案 A：始终使用 API 强制结构化输出，解析失败即抛异常（本阶段推荐）**
- 所有 LLM 调用统一传入 `response_format={"type":"json_object"}`；Pydantic 解析失败直接抛 `LLMOutputValidationError`，原始响应记录在异常 `payload` 中
- 行为完全确定：要么得到类型安全的结构化对象，要么得到明确的异常，不存在"成功但输出不符合预期"的中间状态
- 上层调用方可按需决定重试策略，职责清晰
- 当前阶段 Ollama / OpenRouter 均支持 `json_object` 模式，无兼容性问题；未来若遇到不支持的模型，在 `LLMHTTPClient` 层引入中间件处理，上层逻辑不受影响

**方案 B：优先 API 强制，降级为 Prompt 自觉性输出**
- 先尝试 `response_format`；若 provider 返回"不支持"错误，则退回到 Prompt 中要求模型输出 JSON，解析失败时抛异常
- 增加了 provider 兼容性，但引入了"Prompt 自觉"路径，输出不再完全确定——模型可能在 Prompt 路径下成功返回但格式错误，违背确定性原则
- 适合需要同时支持大量不同能力模型的场景，当前阶段过重

**方案 C：始终依赖 Prompt 自觉性，解析失败时重试**
- 不使用 `response_format`，仅在 Prompt 中要求 JSON 输出；解析失败时重试或抛异常
- 兼容性最佳，但成功路径下仍可能出现格式偏差（模型加废话前缀、字段缺失等），无法保证确定性
- 不符合"确定性正确或确定性失败"的原则

##### 最终选择

我们接受方案A，因为其完全符合追求确定性的核心思想，尽管可能出现异常，但是我们还是尽可能选择支持的模型来对接

---

## 结构

### 文件布局

```
codebases/financial-agent-api/
├── src/
│   └── financial_agent_api/
│       ├── core/
│       │   ├── config.py             # Settings + get_settings()（待创建）
│       │   ├── logging.py            # configure_logging + bind_request_id（待创建）
│       │   ├── exceptions.py         # LLMProviderError, LLMOutputValidationError（待创建）
│       │   └── services_container.py # ServicesContainer 数据类（待创建）
│       ├── services/
│       │   ├── llm_client.py         # LLMHTTPClient（httpx 封装）（待创建）
│       │   └── llm_service.py        # LLMService（提供商切换）（待创建）
│       ├── __init__.py               # 已存在（空）
│       └── main.py                   # 已存在：/healthz；本任务新增 lifespan + /readyz
├── tests/
│   ├── __init__.py                   # 已存在
│   ├── test_health.py                # 已存在
│   ├── test_config.py                # 待创建
│   ├── test_llm_service.py           # 待创建
│   └── test_logging.py               # 待创建
├── pyproject.toml                    # 已存在
├── uv.lock                           # 已存在
└── .env.example                      # 不存在，待本任务创建
```

### 方法签名（契约）

```python
# app/core/config.py
class Settings(BaseSettings):
    llm_provider: Literal["ollama", "openrouter"] = "ollama"
    log_format: Literal["json", "text"] = "text"
    # 条件性字段，见验收标准
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "gpt-4.1-mini"
    # 带默认值的字段
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "gemma3:27b"
    ollama_ops_model: str = "qwen3.5:4b"
    # Task 2 起添加:
    # pg_dsn: PostgresDsn
    # embedding_model: str = "nomic-embed-text"
    # embedding_dim: int = 768


@lru_cache
def get_settings() -> Settings: ...


# get_settings() 使用 @lru_cache 保证进程内单例。
# 测试中可通过 get_settings.cache_clear() 重置以注入不同配置。
# pydantic-settings 文档：https://docs.pydantic.dev/latest/concepts/pydantic_settings/

# app/services/llm_service.py
class LLMService:
    def __init__(self, settings: Settings, http_client: LLMHTTPClient) -> None: ...

    async def complete(
            self,
            messages: list[dict[str, str]],
            *,
            model: str | None = None,
            temperature: float = 0.0,
            max_tokens: int | None = None,
            response_format: str | None = None,
            request_id: str | None = None,
    ) -> str: ...

    # Task 2 起实现；此处仅定义签名存根
    async def embed(
            self,
            inputs: list[str],
            *,
            model: str | None = None,
            request_id: str | None = None,
    ) -> list[list[float]]: ...
```

---

## 操作步骤（严格按顺序执行）

> 前 4 步是固定的。步骤 5+ 是 **TODO(trainee)** —
> 根据验收标准 + 你的方案推导出来。你的
> 导师会在你生成代码之前签收完整的操作步骤列表。

1. **替换任务 0 的 `Settings` 桩代码**：在 `src/financial_agent_api/core/config.py` 中
   用 *结构* 章节的完整 Pydantic Settings 模型替换。添加
   `@lru_cache` 工厂函数。
2. **实现 `src/financial_agent_api/core/logging.py`**，包含 `configure_logging` 和
   `bind_request_id`。从 `Settings.log_format` 读取格式。
3. **实现 `src/financial_agent_api/core/exceptions.py`**，包含两个异常
   类。它们必须安全地序列化 `payload`（在打印时）。
4. **实现 `src/financial_agent_api/services/llm_client.py`**，封装
   `httpx.AsyncClient`。构造函数接受 `base_url`、`api_key`
   和可选的 `transport`，以便测试可以注入
   `httpx.MockTransport`。

5. **TODO(trainee) — 实现 `LLMService.complete`**，支持两个提供商。
   提示："瞬态"失败不仅包括 HTTP 5xx — 还包括
   连接级错误（`httpx.TimeoutException`、
   `httpx.RequestError`）。在编写重试循环之前确定你的
   重试判定逻辑，并在你的权衡章节中记录该选择。
   使用验收标准中已确定的对话端点。
   `embed` 方法在 Task 2 中与 `embedding_model`、`embedding_dim` 一同实现。
6. **TODO(trainee) — 将 `ServicesContainer` 接入 `src/financial_agent_api/main.py`
   的 lifespan，并添加 `/readyz`。** 在修改 `main.py` 时，添加
   request-id 中间件：读取传入的 `X-Request-Id`
   请求头（如果存在），否则生成一个 UUIDv4；通过
   `bind_request_id` 绑定它；并在传出的
   响应上设置 `X-Request-Id`，以便下游服务可以关联。HTTP
   请求头是公共契约；ContextVar 是进程内的
   载体。
7. **TODO(trainee) — 编写测试**：`test_config.py`、
   `test_llm_service.py`（使用 `httpx.MockTransport`）、
   `test_logging.py`。目标是新模块达到 100% 覆盖率。
8. **更新 `README.md`**，添加 *本地开发* 章节，涵盖
   `poetry install`、标准的 Ollama 路径（`ollama pull …`），
   以及如何运行 `pytest` + `mypy --strict`。最终版
   README 的 *本地开发* 章节在你起草完自己的版本后是一个有用的参考。
9. **验证**：运行 `pytest`、`ruff check .`、`mypy --strict
   --explicit-package-bases src`，以及
   `./scripts/smoke.sh`（该脚本从任务 3+ 开始存在；在此之前，
   手动执行 `curl /healthz` 和 `curl /readyz`）。

---

## 规范

- 仅使用基于构造函数的依赖注入。不允许全局单例。
- 所有新函数都有类型标注；`mypy --strict` 通过。
- I/O 路径默认使用异步。
- 所有 DTO 使用 Pydantic v2。
- 结构化日志在每条记录中携带 `request_id`。
- 公共服务方法（`complete`、`embed`）声明
  `request_id: str | None = None`。默认值 `None` 在
  日志记录时解析为 ContextVar 的绑定值，绝不
  记录为 `null`。下面的安全措施 4 禁止*绕过*
  ContextVar 通过临时参数传递；它并*不*禁止文档中列出的
  `request_id` 参数。
- 日志中的提示词截断为 500 字符，带有 `_truncated: true`
  标记。

---

## 安全措施

1. **不要在 `app/core/config.py` 之外导入 `os.getenv`。**
   其他每个模块都从 `Settings` 实例读取。
2. **不要静默吞掉 LLM 错误。** 重试是有上限的，
   最终失败抛出 `LLMProviderError` 并携带上游
   负载。
3. **不要记录 `OPENROUTER_API_KEY`** 或任何包含它的
   请求头。在日志层进行脱敏。
4. **不要绕过 `bind_request_id`**，通过任意关键字参数
   传递 `request_id`。ContextVar 是规范的
   载体。
5. **不要提交真实的 API 密钥。** `.env` 已被 gitignore；
   `.env.example` 仅包含占位符。

---

> **规格漂移监控。** 当你的实现与这个画布有差异时
> （例如你发现 LLM 客户端需要一个未记录的 `timeout`
> 参数），在同一个 PR 中**首先**编辑此画布 — 这是项目的
> *SPDD 纪律*规范。只有代码差异而没有更新规格的提交
> 会被审查阻塞。

## 阅读后的问题

TODO AI需要根据这些问题填充问题的答案，由客户确认更新所有问题为解决后，再进行实现计划的填充

1. 在TODO风险识别这里，我列出来了8项，每项你都要给出是否是现阶段必须要解决的风险，如果是，则需要在实现计划中明确解决思路
   **[AI回答]**
   - 风险1（未引入多环境配置）：**现阶段不必须**。本任务只需支持本地 `.env`，多环境配置（dev/staging/prod）在后续 CI/CD 阶段处理。
   - 风险2（环境变量明文配置）：**现阶段不必须**，但需确保 `.env` 已加入 `.gitignore`（任务 0 约束），`.env.example` 只含占位符（安全措施 5 覆盖）。
   - 风险3（API KEY过期/超限后持续错误）：**现阶段必须部分解决**。重试 3 次后需抛出 `LLMProviderError`（验收标准覆盖），不能无限重试；但速率限制的特殊处理（429 不应重试）需在实现计划中明确。
   - 风险4（未限定LLM回复固定格式）：**现阶段不必须**。`response_format` 参数已在 `complete` 签名中预留，强制结构化输出在 Task 4 中使用。
   - 风险5（返回消息解析失败后缺少原因分析）：**现阶段不必须**。`LLMOutputValidationError` 在此定义但 Task 4 才使用；原始 payload 存入异常供上层分析，已足够。
   - 风险6（AsyncClient级别日志拦截器缺失）：**现阶段必须解决**。`LLMHTTPClient` 封装 httpx 时，应在统一位置（`llm_client.py`）处理请求/响应日志，避免后续遗漏。实现计划中明确：在 `LLMHTTPClient` 的 `request` 方法打入/出边界日志。
   - 风险7（Settings在所有环境支持`python -c`导致配置泄漏）：**现阶段不必须**。当前阶段只有开发环境，生产部署限制（禁止 `-c`、只读挂载等）属于运维规范，超出本任务范围。
   - 风险8（Retry节点控制，避免嵌套Retry）：**现阶段必须解决**。`LLMService.complete` 内的重试不应与外层调用方的重试叠加。实现计划中明确：重试逻辑**只在 `LLMService` 内部**，调用方不应再包一层重试。
   - 风险9（截断提示词是否应全量存储）：**现阶段不必须**。本任务先按规范截断到 500 字符 + `_truncated: true` 标记；全量存储（如写入结构化日志 sink）在可观测性需求确认后再引入。
2. OpenRouter是啥？如何使用
   **[AI回答]**
   OpenRouter（https://openrouter.ai）是一个统一的 LLM API 代理平台，提供兼容 OpenAI 格式的 REST API，后端可路由到 GPT-4、Claude、Gemini、Mistral 等数十个模型。

   使用方式：
   1. 注册并在 https://openrouter.ai/keys 获取 API Key（格式 `sk-or-v1-...`）
   2. 将 Key 设为环境变量 `OPENROUTER_API_KEY`
   3. 调用端点：`POST https://openrouter.ai/api/v1/chat/completions`，请求体与 OpenAI Chat Completions API 完全一致
   4. 请求头需携带 `Authorization: Bearer <key>`，可选 `HTTP-Referer`（标识来源）

   本项目中通过 `LLMService.complete` 封装，调用方无需关心具体 HTTP 细节。
3. Ollama是啥？如何使用
   **[AI回答]**
   Ollama（https://ollama.ai）是本地运行开源 LLM 的工具，支持 Llama、Gemma、Qwen 等模型，提供 REST API。

   使用方式：
   1. 安装：`brew install ollama`（macOS）或参考官网
   2. 启动服务：`ollama serve`（默认监听 http://localhost:11434）
   3. 拉取模型：`ollama pull gemma3:27b`
   4. 对话端点：`POST http://localhost:11434/api/chat`，请求体：`{"model":"gemma3:27b","messages":[...],"stream":false}`
   5. 嵌入端点：`POST http://localhost:11434/api/embeddings`，请求体：`{"model":"nomic-embed-text","prompt":"..."}`

   本项目中通过 `LLMService` 封装，`llm_provider=ollama` 时自动路由到本地 Ollama 实例。
4. LLMProviderError应该在什么情况下出现
   **[AI回答]**
   以下情况抛出 `LLMProviderError`：
   - HTTP 5xx 响应（服务端错误），经重试 3 次仍失败后
   - HTTP 429（速率限制/超出配额），不重试，直接抛出
   - `httpx.TimeoutException`（请求超时），重试后仍失败
   - `httpx.RequestError`（连接失败、DNS 解析失败等），重试后仍失败
   - HTTP 4xx（除 429 外，如 401 未授权、400 请求格式错误），不重试，直接抛出

   异常携带：`provider`（"openrouter"/"ollama"）、`status_code`（HTTP 状态码或 None）、`payload`（响应体原文）、`request_id`（关联日志追踪）。
5. LLMOutputValidationError应该在什么情况下出现
   **[AI回答]**
   `LLMOutputValidationError` 在以下情况下抛出：
   - LLM 返回了 HTTP 200，但响应内容无法被解析为预期的结构化格式（如调用方期望 JSON 但 LLM 返回了 Markdown）
   - Pydantic 模型验证失败（字段缺失、类型不匹配等）

   注意与 `LLMProviderError` 的区别：`LLMProviderError` 表示传输层/提供商层面的失败（LLM 没有正常返回）；`LLMOutputValidationError` 表示 LLM 正常返回但**内容**不符合预期格式。

   本任务中只定义此异常类，在 Task 4 中实际使用。
6. 是否有多线程的场景，如果有，如何让request_id能够跨线程获取
   **[AI回答]**
   本项目使用 FastAPI + asyncio，主要并发模型是**单线程异步**（协程），不是多线程。

   `contextvars.ContextVar` 在 asyncio 中天然支持：每个异步任务（`asyncio.Task`）有独立的 context 副本，`request_id` 绑定后在同一个请求的所有 `await` 调用链中自动可见，无需手动传递。

   但以下场景需注意：
   - `asyncio.create_task()` 会复制父任务的 context（Python 3.7+），子任务可见父任务绑定的 `request_id`，✅ 安全
   - `loop.run_in_executor()`（将同步代码扔到线程池）中，ContextVar **不会自动传播**到工作线程。如果有此场景，需手动在 executor callable 中重新绑定 `request_id`
   - 本任务不涉及 `run_in_executor`，暂不需要处理
7. Python的单例，容器是借助啥实现的，实现原理是啥？
   **[AI回答]**
   本项目中的两种"单例"机制：

   **1. `@lru_cache` 实现 Settings 单例**
   ```python
   from functools import lru_cache
   @lru_cache
   def get_settings() -> Settings:
       return Settings()
   ```
   原理：`lru_cache` 缓存函数的返回值，无参函数只会执行一次，后续调用返回同一对象。
   测试重置：`get_settings.cache_clear()` 清除缓存，下次调用重新初始化。

   **2. FastAPI `lifespan` 实现 ServicesContainer 单例**
   ```python
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       container = ServicesContainer(settings=get_settings(), llm=LLMService(...))
       app.state.container = container  # 挂载到 app.state
       yield
       # 清理资源
   ```
   原理：`lifespan` 在应用启动时执行一次，将 `ServicesContainer` 实例挂载到 `app.state`；每个请求通过依赖注入 `Request.app.state.container` 获取同一实例。

   这是**构造函数 DI**（依赖注入）而非传统单例模式，便于测试（测试可替换 `app.state.container`）。
8. 日志中，出现截断的提示词，是否应该在某个地方进行
   **[AI回答]**
   当前阶段的决策：**不做全量存储**，截断到 500 字符 + `_truncated: true` 标记。

   原因：
   1. 提示词可能包含用户隐私数据，全量存储需要额外的数据脱敏和访问控制，超出本任务范围
   2. 全量提示词可能很大（数 KB），写入日志会显著增加存储成本

   如果后续需要全量调试：
   - 可在 `DEBUG` 级别打完整提示词（生产不开启 DEBUG）
   - 或引入专门的"提示词审计日志"（写入独立存储，有访问控制），在 Task 4/5 中根据需要添加
   - `request_id` 贯穿全链路，可通过 `request_id` 关联重放请求


## 实现计划

（等待用户批准后执行）

### 前置准备

- [ ] P0. 确认 `codebases/financial-agent-api/` 下无 `.env` 文件（不提交真实密钥）；创建 `.env.example`，内容含 `LLM_PROVIDER`、`LOG_FORMAT`、`OPENROUTER_API_KEY`（占位符）、`OPENROUTER_MODEL`、`OLLAMA_BASE_URL`、`OLLAMA_CHAT_MODEL`、`EMBEDDING_MODEL`、`EMBEDDING_DIM` 等占位项

### 阶段 1 — 基础配置与异常

- [ ] 1.1 创建 `src/financial_agent_api/core/` 目录及 `__init__.py`
- [ ] 1.2 实现 `src/financial_agent_api/core/config.py`
  - `Settings(BaseSettings)` 包含本任务所需字段（不含 `pg_dsn`）
  - `model_validator(mode="after")`：`llm_provider=openrouter` 时 `openrouter_api_key` 不能为 None，否则抛 `ValueError`
  - `@lru_cache` 的 `get_settings()` 工厂函数
- [ ] 1.3 实现 `src/financial_agent_api/core/exceptions.py`
  - `LLMProviderError(Exception)`：字段 `provider: str`、`status_code: int | None`、`payload: str`、`request_id: str | None`；`__str__` 安全序列化
  - `LLMOutputValidationError(Exception)`：字段 `raw_response: str`、`validation_error: str`
- [ ] 1.4 编写 `tests/test_config.py`，覆盖：settings 正常加载、openrouter 缺 key 时 ValueError、ollama 模式下 key 可选

### 阶段 2 — 结构化日志

- [ ] 2.1 实现 `src/financial_agent_api/core/logging.py`
  - `configure_logging(settings: Settings)` — 基于 `loguru`，根据 `log_format` 切换 JSON / 文本格式；JSON 格式 serialize=True，文本格式带颜色
  - `bind_request_id(request_id: str)` — 将 `request_id` 写入 `contextvars.ContextVar`
  - `get_request_id() -> str` — 读取 ContextVar，未绑定时返回 `"no-request-id"`
  - loguru `record["extra"]` 注入：通过 `logger.configure(patcher=...)` 自动将 ContextVar 中的 `request_id` 注入每条日志
- [ ] 2.2 编写 `tests/test_logging.py`，覆盖：JSON 格式时字段存在、request_id 正确注入、截断标记

### 阶段 3 — HTTP 客户端与 LLMService

- [ ] 3.1 创建 `src/financial_agent_api/services/` 目录及 `__init__.py`
- [ ] 3.2 实现 `src/financial_agent_api/services/llm_client.py`
  - `LLMHTTPClient` 封装 `httpx.AsyncClient`
  - 构造函数：`base_url: str`、`api_key: str | None`、`timeout: float = 30.0`、`transport: httpx.AsyncBaseTransport | None = None`
  - `async def post(path: str, json: dict) -> dict` — 在入口/出口打边界日志（截断 prompt 字段到 500 字符），返回 JSON；HTTP 错误直接透传给调用方处理
  - `async def aclose()` — 关闭底层 client
- [ ] 3.3 实现 `src/financial_agent_api/services/llm_service.py`
  - `LLMService(settings, http_client)` 实现 `complete` 和 `embed`
  - 可重试错误：`httpx.TimeoutException`、`httpx.RequestError`、HTTP 5xx；**不重试** 4xx（含 429）
  - 重试策略：指数退避 + jitter，最多 3 次（基数 1s，上限 8s）；使用 `asyncio.sleep`
  - 3 次后仍失败：抛 `LLMProviderError`
  - `complete`：OpenRouter 路径 `/chat/completions`，Ollama 路径 `/api/chat`，返回 `str`
  - `embed`：OpenRouter 路径 `/embeddings`，Ollama 路径 `/api/embeddings`（逐条调用后聚合），返回 `list[list[float]]`
- [ ] 3.4 实现 `src/financial_agent_api/core/services_container.py`
  - `@dataclass class ServicesContainer`：`settings: Settings`、`llm: LLMService`
- [ ] 3.5 编写 `tests/test_llm_service.py`，覆盖：OpenRouter/Ollama 端点正确、重试 3 次后抛异常、embed 批量循环（Ollama）

### 阶段 4 — 接入 main.py

- [ ] 4.1 更新 `src/financial_agent_api/main.py`
  - 添加 `lifespan`：启动时 `configure_logging`、构造 `ServicesContainer`、挂载到 `app.state`；关闭时 `await llm_client.aclose()`
  - 添加 request-id 中间件：读取 `X-Request-Id` 请求头（存在则用，否则生成 UUID4）→ `bind_request_id` → 设置响应头 `X-Request-Id`
  - 添加 `/readyz` 端点：返回 `{"status": "ok"}` 即可（后续任务扩展为真实健康检查）

### 阶段 5 — 验证

- [ ] 5.1 运行 `pytest tests/` 确保全绿
- [ ] 5.2 运行 `ruff check src/ tests/`
- [ ] 5.3 手动 `curl http://localhost:8000/healthz` 和 `curl http://localhost:8000/readyz` 验证
- [ ] 5.4 手动验证 `python -c "from financial_agent_api.core.config import get_settings; print(get_settings().openrouter_model)"` 正常输出

### 注意事项

- 重试逻辑**仅在 `LLMService` 内部**，禁止调用方再包重试（避免嵌套，见风险 8）
- `OPENROUTER_API_KEY` 不得出现在任何日志中（`llm_client.py` 的边界日志需排除 headers）
- 所有新函数加类型标注