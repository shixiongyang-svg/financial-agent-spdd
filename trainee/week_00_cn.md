# 第 0 周 — Day 1 / 环境搭建

欢迎。这是唯一一个*不是*"陷阱与揭示"模式的周。第 0 周是
纯搭建工作：Docker Compose 绿灯通过、一个返回 200 的
`/healthz` 端点、项目骨架就位。你本周的 `.trainee.md` 与
目标文档相同 — 这次不需要你来逆向工程什么。

## 建议的第一步（约 2 分钟）

将这个解压后的文件夹初始化为一个 git 仓库。我们建议：

```bash
cd <你的解压文件夹>
git init
git add .
git commit -m "initial: Day-1 trainee bundle"
```

如果你想与导师分享你的工作（大多数学员都会这样做），
将仓库推送到你偏好的托管平台。**我们建议的仓库名：
`financial-agent-spdd`。** 它既体现了项目本身（一个金融
帮助台 Agent），也体现了方法论（结构化 Prompt 驱动开发）。
你当然可以选择其他名字 — 这个名字只是一个提示，不是规则。

如果你不想把工作放在托管的 git 服务器上，那也没问题。
本地提交和每周打包发回给导师的方式同样可行。
与你的导师沟通哪种方式更适合你。

## 你在周五之前可能交付的内容

一个可工作的起点 — 仅此而已。具体来说：

- 解压后的文件夹已纳入 git 追踪，已完成初始提交。
- `docker compose up` 启动两个容器：`web`（FastAPI）
  和 `db`（Postgres + pgvector）。两者均健康。
- `curl http://localhost:8000/healthz` → `200 {"status": "ok"}`。
- 一个包含章程所固定工具版本的骨架 `pyproject.toml`。
- 项目根目录下的 `README.md`（将 `.spdd_specs/README.starter.md`
  复制到那里，从第 1 周开始逐步完善它）。
- 一个断言 `/healthz` 返回 200 的测试。

这个列表有意保持精简。我们建议暂时不要碰 Agent 代码、
检索、prompts — 那些会在后续几周里，在你还没有的规范之上落地，
提前编码往往会让周五白费功夫。基础层应该是无聊的、可工作的、
可复现的，这样接下来的八周才能在此基础上构建。

## 这个 Day-1 包中包含什么

- `.spdd_specs/0_Root_Architecture.trainee.md` — 你的项目
  章程。我们建议在 Day 1 完整通读一遍，然后在接下来的八周里，
  每次 AI 编码会话都将其作为上下文附加。
- `.spdd_specs/AI_OPERATIONS.md` — 如何在这个*项目*上高效地
  驱动你的 AI 编码工具。我们建议在第一次打开 AI 编码工具之前
  阅读它。里面的五条规则能帮你省下好几个小时。
- `.spdd_specs/README.starter.md` — 要复制到项目根目录的
  种子 README。
- `.spdd_specs/tasks/Task_0_Environment.md` — 你的周任务
  简报。*注意：* 第 0 周没有 `.trainee` 变体，因为规范和
  目标文档有意保持相同。`.trainee` 变体从第 1 周开始。
- （`trainee/week_01.md` 也在这个包中 — 那是下周的概览，
  如果你想提前预览，我们已经放进来了。我们建议先把第 0 周
  做完。）

## 为什么这周看起来这么简单

因为之后的所有内容都依赖于一个可工作的本地服务栈和可重复的
容器构建。我们见过两种让学员团队翻车的失败模式：

1. **脆弱的本地 Python 环境。** 学员直接将依赖安装到宿主机的
   Python 中；第 0 周看起来一切正常；然后到了第 5 周，同事的
   机器无法复现评估结果，团队开始责怪评估管线。评估本身没问题 —
   环境才是 bug。Docker 往往是解药。
2. **跳过 pgvector 设置。** 学员为了省时间，运行不带 pgvector 的
   Postgres，计划在检索功能到来时再添加扩展。然后第 2 周就花了两天
   时间来处理一个与他们本地安装冲突的 `CREATE EXTENSION`。
   我们建议现在就搞定它。

## 周三自查

在请导师签收第 0 周之前，你可能想确认以下几点：

- [ ] `docker compose up` 启动后两个容器均绿灯通过，
      `/healthz` 返回 200。
- [ ] `pyproject.toml` 存在，且包含章程所固定的
      `fastapi`、`pydantic`、`pydantic-settings`、
      `loguru`、`pytest`、`ruff`、`mypy` 版本。
- [ ] 仓库根目录下存在 `README.md`，且内容是
      `.spdd_specs/README.starter.md` 的内容（你每周都会
      完善它）。
- [ ] `infra/docker-compose.yml` 存在，且固定了带 pgvector
      的 Postgres 镜像。
- [ ] 一个测试（`tests/test_healthz.py` 或类似文件）通过。
- [ ] 你能重读章程（`0_Root_Architecture.trainee.md`）并 —
      大声地、对同事或对自己 — 解释每个 REASONS 部分的含义。
      如果有任何不清楚的地方，现在就是提问的时机。你前面还有
      八周的 REASONS 画布。

## 第 0 周常见陷阱

| 陷阱 | 表现 | 更稳妥的做法 |
|---|---|---|
| 添加应用代码"抢跑" | 你在第 1 周规范落地之前就开始写 `app/services/llm_service.py`。 | 我们建议等待。第 1 周的规范会固定你还不知道的函数签名，提前编码往往导致周五重做。 |
| 跳过 pgvector | Postgres 镜像是普通的 `postgres:16`。 | 章程建议使用 `pgvector/pgvector:pg16` 并给出了确切标签 — 用它比之后折腾 `CREATE EXTENSION` 省事多了。 |
| 提交 `.env` 文件 | 真实密钥进入了 git 历史。 | `.env` 默认被 git 忽略。`.env.example` 随仓库发布，包含占位键；章程列出了所有变量。 |
| 跳过 README | "我后面再写。" | README 是规范 `.trainee.md` 对外部人员的映射。大多数周的周五 PR 都包含一个小的 README diff — 早早养成习惯，维护成本就很低。 |

## 周日会揭示什么

对于第 0 周，*什么都没有改变*。目标画布
（`Task_0_Environment.md`）就是你所依据的同一个文件。
本周没有"揭示"环节 — 第 0 周是有意在学员轨道和目标轨道之间
共享的。真正的 `.trainee.md` 工作流从第 1 周周一开始。

## 拓展阅读（可选）

- *《The Twelve-Factor App》* — 环境变量章节是
  `pydantic-settings` 的思想渊源。
- Docker Compose 文档中关于 `depends_on` 配合 `condition:
  service_healthy` 的部分 — `web` 如何在 `db` 通过
  `/pg_isready` 之后才启动。
- pgvector README 的"快速开始"页面 — 即使第 2 周才真正使用它，
  也值得一看。
- **FastAPI 作为 AI 默认框架：** 现代 AI 应用编排的是嵌入生成、
  向量搜索和 LLM 推理 — 而不是单个 API 调用。FastAPI 的
  async-first 架构天然适合现代 AI 和 RAG 系统的重度 I/O 模式。
  [How FastAPI Became Python's Fastest-Growing Framework](https://dzone.com/articles/how-fastapi-became-pythons-fastest-growing-framework)
- **高性能向量扩展（`pgvectorscale`）：** 虽然 `pgvector`
  可以直接在 PostgreSQL 中存储嵌入向量，但生产环境常常会碰到
  性能瓶颈。`pgvectorscale` 建立在 `pgvector` 之上，添加了
  StreamingDiskANN 索引类型，以在受限内存下实现大规模高召回率
  向量搜索。
  [pgvector, pgvectorscale, and the Postgres Vector Search Stack](https://www.softwareseni.com/pgvector-pgvectorscale-and-the-postgres-vector-search-stack-explained/)
- **容器启动顺序：** 确保 FastAPI 后端在 Postgres 完全健康之后
  才启动，这一点至关重要。
  [Docker Compose Startup Order Docs](https://docs.docker.com/compose/how-tos/startup-order/)

---

当第 0 周绿灯通过时，深呼吸一下。接下来的八周才是课程大纲
真正开始的地方。
