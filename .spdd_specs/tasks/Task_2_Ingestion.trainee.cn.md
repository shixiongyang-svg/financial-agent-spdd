# 第 2 周 — 从基础设施到朴素 RAG

你在第 1 周完成了：`Settings`、`LLMService`、带 `request_id` 的结构化日志。
智能体现在可以调用 LLM，但还不能*检索*任何东西。这周我们引入语料库。

## 这周你会得到

- `.spdd_specs/tasks/Task_2_Ingestion.trainee.md` — 你的周一任务指南。
- 周日：最终画布 `Task_2_Ingestion.md`。

## 这周引入的内容

1. **`complaints` 和 `docs` 表**，加上一个 `doc_embeddings` pgvector 表。
2. **两个摄取脚本** — 一个用于公开 CSV（`ingest_public_data.py`），一个用于 markdown 语料库（`embed_starter_docs.py`）。
3. **`RetrievalService`** 包含两个方法（`retrieve_docs`、`retrieve_complaints`）。

这周你在构建一个*刻意简化*的 RAG。它看起来会工作。未来的周次可能会重新审视检索选择 —
相信我们保持这周表面简洁是有原因的。

## 为什么这样设计

- **为什么是固定大小的分块，而不是基于章节的分块？** 因为基于章节的分块需要文档解析器，
  我们希望你在投入更好的方案之前先感受到固定大小分块的召回失败。跳过这个教训，
  下次你就会优化错误的地方。

- **为什么用 `apply_schema` 配合字符串替换，而不是 Alembic？** 权衡在宪章的"风险与权衡"部分有文档记录。
  这里是为了教学简洁，*不是*生产环境应该复制的模式。

- **为什么在 `complaint_id` 上执行 upsert，而不是只做 insert？** 因为摄取脚本必须是幂等的。
  在相同的 CSV 上重新运行它不应该导致重复计数。

## 第 2 周常见陷阱

| 陷阱                                  | 表现形式                             | 解决方案                                                                                      |
|-------------------------------------|----------------------------------|-------------------------------------------------------------------------------------------|
| 字符串格式化 SQL                          | `f"WHERE product = '{product}'"` | 使用 SQLAlchemy `text()` 配合绑定参数。宪章禁止在接受用户输入的任何地方使用字符串构造 SQL。                                |
| 嵌入维度漂移                              | 摄取写入 768 维向量；后续代码读取 1536 维。      | 模式中的 `/* EMBEDDING_DIM */` 占位符是契约；`apply_schema` 从 `Settings.embedding_dim` 替换。选择一个并坚持使用。 |
| 从 `RetrievalService` 返回 ORM 对象      | 会话生命周期逃逸出服务；测试开始以莫名的原因失败。        | 在服务内部投影到 `DocumentChunk` / `ComplaintRow` Pydantic 模型，然后再返回。                              |
| 忘记 `request_id: str \| None = None` | 公共服务方法缺少此参数；结构化日志失去关联。           | 这是第 1 周日志契约所要求的。每个公共方法都需要它。                                                               |

## 周三自检

- [ ] *风险识别* 涵盖 `(source_file, chunk_index)` 对的去重、嵌入维度漂移和 `narrative` 列的个人身份信息处理。
- [ ] *接受的权衡* 命名了固定大小分块 vs 基于章节的分块、`IF NOT EXISTS` 模式 vs 迁移、ILIKE vs 全文搜索。
- [ ] *类图* 显示了 `RetrievalService → SQLAlchemy session_factory → Postgres`，
  加上用于嵌入的 `LLMService` 注入。
- [ ] *操作步骤* 已编号。模式文件名固定为 `0001_create_tables.sql`（最终版本将假定这个命名）。

## 周日会揭示什么

最终画布会固定 `RetrievalService` 的确切签名，这是课程其余部分依赖的，
包括你可能还没写的参数和 SQL 中的 ILIKE / ORDER BY 子句。期望有小的协调差异：
你的 `__init__` 可能缺少 `embedding_dim` 参数，或者你的 `retrieve_complaints` 可能缺少位置参数。

## 深入探索（可选阅读）

- pgvector 索引类型（HNSW vs IVFFlat）的入门指南 — 以及各自何时更优。
  （你这周不会构建索引，但这个选择对第 6 周很重要。）
  [pgvector 官方索引文档](https://github.com/pgvector/pgvector#indexing)

- Anthropic / OpenAI 食谱中关于分块策略的章节。固定大小分块的失败频率远高于基于章节的分块。
  [Pinecone: LLM 应用的分块策略](https://www.pinecone.io/learn/chunking-strategies/)

- CFPB 消费者投诉数据字典，让你理解 `Issue` 值真正意味着什么。
  [CFPB 消费者投诉数据库数据字典](https://cfpb.github.io/api/ccdb/data_dictionary.html)

- **AI 时代的 SQL 注入：** 类似 `f"WHERE product = '{product}'"` 这样的字符串格式化 SQL 被禁止；
  使用 SQLAlchemy `text()` 配合绑定参数。
  [SQLAlchemy: 安全地使用文本 SQL](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html)

## 阅读后的问题

TODO AI依次回答这里的问题，由用户Approve后才产生实现计划

1. `doc_embeddings` pgvector 表 是需要和 `docs` 表 关联吗？是通过什么方式关联的？
   **[AI回答]**
   需要关联，且应当是**强关联**。

   推荐方式：
   - `docs` 表使用主键 `id`（通常是 `bigserial` 或 `uuid`）
   - `doc_embeddings` 表包含 `doc_id` 外键，引用 `docs.id`
   - 在 SQL 中使用 `FOREIGN KEY (doc_id) REFERENCES docs(id) ON DELETE CASCADE`

   这样做的好处：
   - 保证 embedding 行不会“悬空”（引用不存在的文档）
   - 删除文档时自动清理对应向量
   - 检索时可以稳定地 `JOIN docs ON doc_embeddings.doc_id = docs.id`
2. `doc_embeddings`的数据是如何产生的
   **[AI回答]**
   产生链路通常是：
   1. 读取 markdown 原文
   2. 按固定 chunk 规则切分文本
   3. 对每个 chunk 调用 embedding 接口（本项目通过 `LLMService.embed`）
   4. 得到 `List[float]` 向量后写入 `doc_embeddings.embedding`（pgvector）
   5. 同时写入关联信息（`doc_id`、`chunk_index`、可能的 `chunk_text`/`content`）

   简单说：`doc_embeddings` 不是手工写入，而是由**摄取脚本 + embedding 模型推理**生成。
3. 固定大小的分块意思是对Markdown的内容按照固定长度进行Substring这种操作吗？
   **[AI回答]**
   是这个方向，但建议不是“生硬 substring”，而是“**固定窗口 + 轻量边界处理**”。

   实操上通常是：
   - 先将 markdown 转成纯文本或近似纯文本
   - 按固定字符数（例如 800~1200）切块
   - 可选重叠（例如 overlap 100~200）以减少语义断裂

   课程里强调“固定大小分块”，核心是先用简单、可重复的方法，不引入复杂章节解析器。
4. apply_schema字符串匹配替换，具体细节是啥？根据宪章中的，我仍然没有读懂，我首先理解有不同的SQL文件，然后通过辅助函数来执行这些SQL，然后可能是通过在数据库中新建辅助表来记录SQL的执行从而达到避免重复执行的目的，但是你说的替换 `/* EMBEDDING_DIM */` 这个是啥，是哪里有这个固定的字符串？为啥要替换？替换之后会如何？
   **[AI回答]**
   你的理解方向是对的，这里再拆开说：

   - 有一个 schema SQL 文件（例如 `0001_create_tables.sql`），里面包含建表语句。
   - 其中向量列通常写成占位形式，例如：
     `embedding vector(/* EMBEDDING_DIM */)`
   - `apply_schema` 在执行 SQL 前，会把这个占位符字符串替换为配置值（如 `1536`），形成最终 SQL：
     `embedding vector(1536)`
   - 然后再把替换后的 SQL 发送给数据库执行。

   为什么要替换：
   - pgvector 的维度必须是**常量**，不能用运行时参数绑定
   - 不同模型维度不同（如 768、1024、1536），用占位符可避免硬编码

   与“避免重复执行”是两件事：
   - **占位符替换**：解决 SQL 模板参数化
   - **幂等执行**：通常靠 `CREATE TABLE IF NOT EXISTS`（本训练任务采用）而不是迁移历史表
5. 对于Markdown内容的digest的幂等性，是通过哪个信息可以作为唯一ID？
   **[AI回答]**
   建议用“**稳定输入字段的哈希**”作为幂等键，而不是数据库自增 ID。

   常见做法：
   - 文档级：`digest = sha256(source_file + normalized_content)`
   - 分块级：`chunk_digest = sha256(source_file + chunk_index + chunk_text)`

   对本周任务最实用的是分块级唯一约束：
   - `UNIQUE(source_file, chunk_index)`（课程里也特别提到这一对）
   - 或进一步用 `UNIQUE(chunk_digest)`

   这样同一份文件重复摄取时会 upsert / ignore，而不会产生重复行。
6. 所以，本周的任务就是写消费脚本，把提供的脚本作为语料库原始信息消费并存入到数据库是吗？
   **[AI回答]**
   基本正确，但范围稍微更完整一些。本周是“**摄取 + 可检索**”：

   1. 建立三张核心表：`complaints`、`docs`、`doc_embeddings`
   2. 完成两个摄取脚本：
      - 公开投诉 CSV -> `complaints`
      - markdown 语料 -> `docs` + `doc_embeddings`
   3. 实现 `RetrievalService` 的两个查询方法：
      - `retrieve_docs`
      - `retrieve_complaints`

   所以不仅是“入库”，还要确保后续 Agent 能把数据“查出来”。
7. 因为我看到涉及到向量的存储，本周是否需要调用LLM的embedding功能对原始信息转换成向量（至少我认为embedding是干这个活的）
   **[AI回答]**
   需要，且这是本周关键步骤之一。

   你理解是对的：embedding 的职责就是把文本映射为向量，以支持向量相似度检索。

   本周至少要做到：
   - 在 markdown 摄取流程中调用 `LLMService.embed`
   - 将返回向量写入 `doc_embeddings`
   - 维度与 `Settings.embedding_dim` 一致（否则会插入失败或检索异常）

   这也是为什么文档强调 `/* EMBEDDING_DIM */` 占位符必须与模型维度契约一致。

## 实现计划

（已拟定，等待你批准后开始实现）

### 范围与目标

- [ ] 在 `financial-agent-api` 内落地本周最小可用 RAG 基础：`complaints`、`docs`、`doc_embeddings` 三表 + 两个摄取脚本 + `RetrievalService` 两个检索方法。
- [ ] 保持幂等（重复执行不重复入库）与安全约束（参数化 SQL、不泄露密钥、日志带 `request_id`）。
- [ ] 原始数据输入路径全部使用环境变量控制，不在代码中硬编码目录。

### 目录结构（本阶段）

- [ ] API 代码结构（`codebases/financial-agent-api/`）：
  - `src/financial_agent_api/db/schema/0001_create_tables.sql`
  - `src/financial_agent_api/db/schema.py`
  - `src/financial_agent_api/scripts/ingest_public_data.py`
  - `src/financial_agent_api/scripts/embed_starter_docs.py`
  - `src/financial_agent_api/scripts/initialize_data.py`
  - `src/financial_agent_api/services/retrieval_service.py`
- [ ] 本地数据目录结构（仓库根目录）：
  - `data/complaints/`（CSV 输入目录）
  - `data/docs/`（Markdown 语料目录）
- [ ] 本地私有配置目录结构（仓库根目录）：
  - `.local-config/llm.env`（本地模型/密钥环境变量文件，git 忽略）
  - 说明：`data/` 目录仅用于可提交的数据语料，不存放本地私有配置
- [ ] 容器内目录约定：
  - 通过 `./data:/app/data:ro` 挂载
  - `COMPLAINTS_CSV_PATH=/app/data/complaints/...`
  - `DOCS_SOURCE_DIR=/app/data/docs`

### 阶段 1 — 数据库与模式初始化

- [ ] 新增 schema 文件（命名固定为 `0001_create_tables.sql`），包含：
  - `complaints`（按 `complaint_id` 唯一）
  - `docs`（文档与分块元数据）
  - `doc_embeddings`（`doc_id` 外键指向 `docs.id`，`embedding vector(/* EMBEDDING_DIM */)`）
  - `(source_file, chunk_index)` 唯一约束（或等价幂等约束）
- [ ] 实现/补充 `apply_schema`：
  - 执行前替换 `/* EMBEDDING_DIM */ -> Settings.embedding_dim`
  - 使用 `CREATE ... IF NOT EXISTS` 实现可重复执行

### 阶段 2 — 摄取脚本

- [ ] `ingest_public_data.py`：
  - 从 `COMPLAINTS_CSV_PATH` 读取公开 CSV，清洗并写入 `complaints`
  - 以 `complaint_id` upsert，保证幂等
  - 全部 SQL 使用绑定参数（禁止字符串拼接 SQL）
- [ ] `embed_starter_docs.py`：
  - 从 `DOCS_SOURCE_DIR` 读取 markdown 语料
  - 固定窗口分块（可带 overlap）
  - 调用 `LLMService.embed` 生成向量并写入 `doc_embeddings`
  - 与 `docs` 建立稳定关联（`doc_id` 外键），重复执行不重复写入

### 阶段 3 — RetrievalService

- [ ] 新增 `RetrievalService` 并注入 `session_factory` 与 `LLMService`（按现有容器模式接线）。
- [ ] 实现 `retrieve_docs`：
  - 对 query 生成 embedding
  - 向量相似度检索 `doc_embeddings` 并回表 `docs`
  - 返回 Pydantic DTO（不返回 ORM 对象）
- [ ] 实现 `retrieve_complaints`：
  - 使用 ILIKE + ORDER BY 的基础检索
  - 返回 Pydantic DTO（不返回 ORM 对象）
- [ ] 公共方法保持 `request_id: str | None = None`，并延续结构化日志约定。

### 阶段 4 — 配置与依赖接线

- [ ] 在 `Settings` 增补本周所需最小配置（如 `embedding_model`、`embedding_dim`、数据库连接项）。
- [ ] 在 `Settings` 增加并校验原始数据路径配置：
  - `COMPLAINTS_CSV_PATH`
  - `DOCS_SOURCE_DIR`
- [ ] `ServicesContainer` / 应用启动流程中完成 `RetrievalService` 注册与注入。
- [ ] `.env.example` 与本周新增配置项保持一致（仅占位符，无真实密钥）。

### 阶段 5 — 本地容器构建与初始化

- [ ] 更新根目录 `docker-compose.yml` 的 `financial-agent-api` 服务：
  - 设置环境变量 `COMPLAINTS_CSV_PATH`、`DOCS_SOURCE_DIR`
  - 路径指向容器内 `/app/data/...`（来源于根目录 `./data` 挂载）
  - 增加固定 `env_file` 路径：`./.local-config/llm.env`（用于本地真实大模型配置）
- [ ] 为 API 容器增加 volume 挂载：
  - `./data:/app/data:ro`
- [ ] 更新容器启动脚本（或 entrypoint）：
  - 服务启动前执行初始化流程（`apply_schema` + 初始摄取流程）
  - 初始化失败时容器应显式失败，不静默跳过
  - 由 `start` 脚本负责交互式生成 `./.local-config/llm.env`，entrypoint 只消费该文件并启动
- [ ] 更新 `start` 脚本与 `README`：
  - 首次运行（无 `./.local-config/llm.env`）必须进入交互流程：
    1. 提示用户选择模型提供商（`ollama` / `openrouter`）
    2. 根据选择逐项询问参数并即时校验非空
       - Ollama：`OLLAMA_BASE_URL`、`OLLAMA_CHAT_MODEL`、`EMBEDDING_MODEL`
       - OpenRouter：`OPENROUTER_API_KEY`、`OPENROUTER_MODEL`、`EMBEDDING_MODEL`
    3. 自动写入固定值：`COMPLAINTS_CSV_PATH=/app/data/complaints/...`、`DOCS_SOURCE_DIR=/app/data/docs`
    4. 将结果写入 `./.local-config/llm.env`，并提示“配置已保存，后续将自动复用”
  - 第二次及后续运行（存在 `./.local-config/llm.env`）：
    - 不再询问任何输入
    - 明确提示“使用已有配置”
    - 同时提示“如需重置请删除 `./.local-config`”
  - README 需提供交互流程说明与示例交互文案（首启 vs 二次运行）
  - 明确“重置方式”为删除目录：`rm -rf ./.local-config`
  - 明确“重新初始化方式”为再次运行 `start` 并按交互重新填写
- [ ] 更新 `.gitignore`：
  - 忽略 `.local-config/`（避免提交本地密钥）

### 阶段 6 — 测试与验收

- [ ] 增加/补齐测试：
  - schema 占位符替换与幂等执行
  - 两个摄取脚本的幂等性
  - 环境变量缺失/路径不存在时的明确失败行为
  - docker-compose 本地启动时 API 能读取 `/app/data` 下语料并完成初始化
  - `start` 交互流程覆盖：首启有交互、二次运行无交互、重置后恢复交互
  - `RetrievalService` 两个方法的返回形状与关键过滤逻辑
- [ ] 运行并通过仓库现有 lint、type-check、tests。

### 风险处理（纳入本次实现）

- [ ] 维度漂移：schema 与运行时统一使用 `Settings.embedding_dim`。
- [ ] 重复入库：`complaint_id` upsert + `(source_file, chunk_index)` 唯一约束。
- [ ] SQL 注入：仅使用参数化 SQL（`text()` + bound params）。
- [ ] 日志安全：不记录 key，提示词按既定策略截断记录。

### 当前收敛计划（2026-07-16 更新）

- [ ] P0. 初始化可观测性补齐：在 `initialize_data` 流程显式启用日志配置，并输出阶段摘要（schema/complaints/docs-embedding），失败时打印阶段上下文。
- [ ] P0. 验证口径对齐：保留 complaints 按 `complaint_id` 去重（1000 原始行 -> 400 唯一 ID）的既定契约，并在 README/验收说明中明确该口径。
- [ ] P1. 文档摄取覆盖修正：`DOCS_SOURCE_DIR` 同时支持 `.md` 与 `.txt`，保证样例数据可入库并生成 embeddings。
- [ ] P1. `start` 交互补齐：显式询问并写入 `EMBEDDING_DIM`（可带模型推断默认值）。
- [ ] P1. 验收步骤固化：提供 compose 启动后 SQL 核对清单（`complaints_count`、`docs_count`、`doc_embeddings_count`、`vector_dims`、`digest` 完整性）。