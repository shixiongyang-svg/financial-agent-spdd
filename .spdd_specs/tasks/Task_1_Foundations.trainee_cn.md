# 任务 1 — 基础设施（REASONS 画布，学员版）

> **学员版说明。** 这是你在第 1 周第 1 天收到的画布。它被**有意地在某些地方描述不足** —
> 缺失的细节就是你在分析步骤 + 画布补全练习中需要完成的工作。本任务的最终版本位于
> `Task_1_Foundations.md`；在导师签收本画布之前，不要阅读那个文件。在生成代码之前必须完成
> 标记为 **TODO(trainee)** 的章节。
>
> **对应：** 学习计划第 1 周 — *Python 基础设施与服务抽象*。
> **依赖：** `Task_0_Environment.md`（已完成，与最终版本相同）。
> **解锁：** `Task_2_Ingestion.trainee.md`、`Task_3_Orchestration.trainee.md`。

---

## 需求

### 分析上下文

TODO AI根据目前的实现，对提到的目录，产物等进行更新，如果没有的，标识为没有

**扫描到的领域关键词：** LLMService、OpenRouter、Ollama、
embeddings、settings、request_id、结构化日志、重试。
**现有产出物：** `.env.example`、任务 0 创建的 `app/` 骨架。
**已阅读的前置任务：** 任务 0（环境变量、healthz、settings 桩代码）。

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

TODO AI 填充 （填充后保留这里由AI填充字样）

##### 最终选择

在AI填充可选方案后，用户根据方案进行取舍决定

#### 日志量 vs 可追踪性

在使用日志追中的过程中，如果过多的日志虽然会提高可追踪性，但是会导致日志量倍增，反之亦然。
因此，可以首先对代码进行逻辑单元拆分。
同一个逻辑单元则只需要输入和输出的日志即可（我们认为逻辑单元都是可以进行单元测试或者手动测试的，只要有输入+输出，就可以复现任意一个请求）。

我们可以认为同一个进程上下文在没有被其他逻辑单元分割的情况下，认为是一个逻辑单元，比如

一个由其他进程调用的方法入口是逻辑单元的输入，方法返回，则为逻辑单元的输出。
在一个进程内，如果开启了其他进程的请求，比如，另外一个线程，一个Http请求，这种则认为是开启了另外一个逻辑单元，则要对调用时的参数和得到的返回结果进行日志打印。

##### 可选方案

TODO AI 填充 （填充后保留这里由AI填充字样）

##### 最终选择

在AI填充可选方案后，用户根据方案进行取舍决定

#### Pydantic 验证的严格性 vs 开发者体验

关于这个方向，我认为可以权衡的点并不多，从数据的角度出发，所有必要的数据验证都应该有，即使很麻烦，开发者也应该遵循，尤其是在AI的帮助下，不应该有很大的重复开发负担。

但是，仍然有一部分我认为是可以考虑的，比如在校验基础的数据格式的前提条件下，应该尽量放宽限制，比如，电话号码，只需要是数字即可，而不需要校验电话的长度，开头，等之类的。

##### 可选方案

TODO AI 填充 （填充后保留这里由AI填充字样）

##### 最终选择

在AI填充可选方案后，用户根据方案进行取舍决定

#### 结构化输出强制执行 vs LLM 合规性

在做结构化输出强制执行的同时，可能会输出一些不满足LLM合规性的信息。

我们不应该在任何地方在非必要的情况下，显示打印/存储不满足LLM合规性的信息，如果确实需要打印/存储，至少，应该带有明显的统一的标签来标识此处信息有合规性风险，
其次，应该进行根据具体信息的属性进行不同程度的掩盖处理，最后，如果明确要求明文输出，则不允许存在批量获取此类信息的接口，且针对此类信息应该提供单独的接口进行获取，且接口内部一定要有清晰的审计日志（谁，在什么时间，拿了哪条数据的哪个合规性数据）。

##### 可选方案

TODO AI 填充 （填充后保留这里由AI填充字样）

##### 最终选择

在AI填充可选方案后，用户根据方案进行取舍决定

---

## 结构

### 文件布局

TODO AI根据当前目录的情况对目录结构进行更新

```
app/
├── core/
│   ├── config.py             # Settings + get_settings()
│   ├── logging.py            # configure_logging + bind_request_id
│   ├── exceptions.py         # LLMProviderError, LLMOutputValidationError
│   └── services_container.py # ServicesContainer 数据类
├── services/
│   ├── llm_client.py         # LLMHTTPClient（httpx 封装）
│   └── llm_service.py        # LLMService（提供商切换）
└── api/
    └── main.py               # lifespan 装配容器；在此添加 /readyz
```

### 方法签名（契约）

TODO AI根据截止本任务所真实需要的config进行设置，而不是一次性设置所有，因此对Settings的内容要进行更新

```python
# app/core/config.py
class Settings(BaseSettings):
    pg_dsn: str
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
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768


@lru_cache
def get_settings() -> Settings: ...


TODO AI扩展方法用途说明，如果有外部链接进行辅助说明，也要贴上

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

TODO AI根据之前的目录对提到的文件或者是目录位置进行更新

> 前 4 步是固定的。步骤 5+ 是 **TODO(trainee)** —
> 根据验收标准 + 你的方案推导出来。你的
> 导师会在你生成代码之前签收完整的操作步骤列表。

1. **替换任务 0 的 `Settings` 桩代码**：在 `app/core/config.py` 中
   用 *结构* 章节的完整 Pydantic Settings 模型替换。添加
   `@lru_cache` 工厂函数。
2. **实现 `app/core/logging.py`**，包含 `configure_logging` 和
   `bind_request_id`。从 `Settings.log_format` 读取格式。
3. **实现 `app/core/exceptions.py`**，包含两个异常
   类。它们必须安全地序列化 `payload`（在打印时）。
4. **实现 `app/services/llm_client.py`**，封装
   `httpx.AsyncClient`。构造函数接受 `base_url`、`api_key`
   和可选的 `transport`，以便测试可以注入
   `httpx.MockTransport`。

5. **TODO(trainee) — 实现 `LLMService`**，支持两个提供商。
   提示："瞬态"失败不仅包括 HTTP 5xx — 还包括
   连接级错误（`httpx.TimeoutException`、
   `httpx.RequestError`）。在编写重试循环之前确定你的
   重试判定逻辑，并在你的权衡章节中记录该选择。
   对于 `complete`，使用验收标准中已确定的对话端点。
   对于 `embed`，标准路径为
   `embeddings`（OpenRouter）和 `api/embeddings`（Ollama，
   每次调用一个向量 — 你需要编写一个客户端侧的批量
   循环）。在你的权衡章节中记录任何偏差。
6. **TODO(trainee) — 将 `ServicesContainer` 接入 `app/api/main.py`
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
   --explicit-package-bases app data_pipelines`，以及
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
2. OpenRouter是啥？如何使用
3. Ollama是啥？如何使用
4. LLMProviderError应该在什么情况下出现
5. LLMOutputValidationError应该在什么情况下出现
6. 是否有多线程的场景，如果有，如何让request_id能够跨线程获取
7. Python的单例，容器是借助啥实现的，实现原理是啥？
8. 日志中，出现截断的提示词，是否应该在某个地方进行


## 实现计划

TODO AI生成实现计划，由用户批准通过后，按计划执行