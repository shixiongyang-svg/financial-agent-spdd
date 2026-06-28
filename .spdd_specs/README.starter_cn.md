# 金融帮助台 Agent

> **关于本 README。**
> 这是项目 README 的*种子*版本 — 作为 Task 0 的一部分复制到
> `/README.md` 的文件。以下所有内容都有意保持最小化：它涵盖
> Task 0 交付的内容（Docker Compose、`/healthz`、项目骨架），
> 不涉及更多。每个后续的 `Task_<N>_<Topic>.trainee.md` 都包含
> 一个*更新 README* 操作，每周为这个文件增加一个新部分。
> 到第 7 周时，你的 README 将与这个种子版本看起来截然不同 —
> 这是预期的轨迹。
>
> 如果你忍不住想偷看第 8 周结束时 README"应该"是什么样子，
> 我们建议等到你完成第 7 周。课程大纲的陷阱与揭示节奏在每周
> 的目标画布在周日给你惊喜时效果更好。

一个容器化的、基于 LangGraph 的 Agent，以 CFPB 公开数据为依据
回答消费金融问题。在 8 周内逐步构建；本 README 每周增加一个部分。

章程文件是
[`.spdd_specs/0_Root_Architecture.trainee.md`](.spdd_specs/0_Root_Architecture.trainee.md)。
在 Day 1 通读一遍；以下所有内容都假设你至少略读了它。

## 快速开始（第 0 周 — 仅环境）

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
curl http://localhost:8000/healthz   # → {"status": "ok"}
```

这就是第 0 周结束时整个用户可见的表面积。`app` 容器响应一个健康
探测端点；`db` 容器已启动但是空的。还没有 Agent。

## 项目布局

```text
app/                    # FastAPI 应用（第 0 周仅 /healthz）
data/                   # 入门语料库（只读；第 2 周交付）
data_pipelines/         # 空 — 从第 2 周开始填充
infra/                  # Dockerfiles + compose
tests/                  # Pytest 套件（第 0 周一个测试）
.spdd_specs/            # SPDD 画布 — 你的周任务简报
```

## 本地开发

```bash
poetry install
poetry run ruff check .
poetry run pytest -q
```

## 下一步学习什么

课程大纲通过 SPDD 规范集交付。我们建议先读章程，然后按收到
的每个周任务依次阅读。

### 已在你的 Day-1 包中

| 文件 | 何时阅读 |
|---|---|
| [`0_Root_Architecture.trainee.md`](.spdd_specs/0_Root_Architecture.trainee.md) | Day 1 — 章程。 |
| [`AI_OPERATIONS.md`](.spdd_specs/AI_OPERATIONS.md) | Day 1 — 如何在这个项目上驱动你的 AI 编码工具。我们建议在第一次 AI 编码会话之前阅读。 |
| [`tasks/Task_0_Environment.md`](.spdd_specs/tasks/Task_0_Environment.md) | 第 0 周 — 你在这里。 |
| [`tasks/Task_1_Foundations.trainee.md`](.spdd_specs/tasks/Task_1_Foundations.trainee.md) | 第 1 周 — 如果你想预览，但先把第 0 周做完。 |

### 在后续周日分发中到达

| 文件 | 周 |
|---|---|
| `tasks/Task_2_Ingestion.trainee.md` | 第 2 周 |
| `tasks/Task_3_Orchestration.trainee.md` | 第 3 周 |
| `tasks/Task_4_Prompts.trainee.md` | 第 4 周 |
| `tasks/Task_5_Evaluation.trainee.md` | 第 5 周 |
| `tasks/Task_6_DataQuality.trainee.md` | 第 6 周 |
| `tasks/Task_7_Safety.trainee.md` | 第 7 周 |
| `tasks/Task_8_Extensions.trainee.md` | 第 8 周（可选结业项目） |

每个周任务以*更新 README* 操作结束，该操作指向要添加到此文件
的一个新部分。到第 7 周时，本 README 应该与起点看起来截然不同。
