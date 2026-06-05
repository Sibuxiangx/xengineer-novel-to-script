# XEngineer AI 小说转剧本工具

七牛云 XEngineer 新工科计划第三批次参赛项目。

## 选题

题目三：AI 小说转剧本工具

很多小说作者希望将自己的作品改编成剧本。本项目计划开发一款 AI 辅助剧本创作工具，降低改编门槛，提升效率。

目标能力：

- 将 3 个章节以上的小说文本自动转换为结构化剧本。
- 输出可编辑、可校验、可进一步打磨的 YAML 剧本初稿。
- 提供剧本 YAML Schema 文档，并说明 Schema 的设计原因。
- 帮助作者理解章节、人物、场景、冲突、对白与舞台动作之间的改编关系。

## 初步产品方向

项目会优先做成一个面向作者的改编工作台，而不是单次 Prompt 生成器。

计划工作流：

1. 导入 3 个及以上小说章节。
2. 分析章节结构、主要人物、地点、时间线与关键事件。
3. 将小说内容拆分为剧本场次。
4. 生成符合 YAML Schema 的剧本初稿。
5. 校验 YAML 结构并提示可修复问题。
6. 支持作者查看、编辑、重新生成局部内容并导出结果。

## 计划交付物

- Web 应用或桌面可运行应用。
- 剧本 YAML Schema 设计文档。
- 小说转剧本核心流程。
- YAML 校验与错误提示。
- README 使用说明。
- Demo 视频链接。

## 当前状态

仓库创建于第三批次题目开放后。当前后端已完成项目创建、TXT 导入分章、剧情索引、剧本 YAML 生成、harness 校验、局部编辑、修复、版本管理与导出闭环。

## 运行方式

### 后端

后端使用 Python、uv、FastAPI、Pydantic、Pydantic AI、SQLAlchemy async、SQLite 与本地文件存储。

```bash
cd backend
uv sync
cp .env.example .env
uv run fastapi dev app/main.py
```

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

当前后端已支持的基础流程：

1. `POST /projects` 创建改编项目。
2. `POST /projects/{project_id}/ebook/import-txt` 导入 TXT 正文并自动分章。
3. `POST /projects/{project_id}/ebook/infer-split-rule` 通过 Agent 推导、检查并修订长篇 TXT 分章规则。
4. `GET /projects/{project_id}/chapters` 查看导入后的章节。
5. `PATCH /projects/{project_id}/chapters/{chapter_id}` 手动编辑章节标题或正文。
6. `POST /projects/{project_id}/book-index` 调用 DeepSeek Agent 生成 `book_index.json`。
7. `GET /projects/{project_id}/book-index` 读取已生成的剧情索引。
8. `POST /projects/{project_id}/scripts/generate` 基于章节与 `book_index.json` 生成 `script.yaml`。
9. `POST /projects/{project_id}/scripts/validate` 使用 harness 校验剧本 YAML。
10. `POST /projects/{project_id}/scripts/edit` 通过结构化 YAML patch 局部编辑当前剧本。
11. `POST /projects/{project_id}/scripts/repair` 根据 harness 错误修复未通过校验的 YAML。
12. `GET /projects/{project_id}/scripts/versions` 查看通过校验并保存的剧本版本。
13. `GET /projects/{project_id}/scripts/versions/{version_id}` 查看某个版本的 YAML。
14. `POST /projects/{project_id}/scripts/versions/{version_id}/restore` 回滚到某个已接受版本。
15. `GET /projects/{project_id}/scripts/exports/script.yaml` 导出当前剧本 YAML。
16. `GET /projects/{project_id}/scripts/exports/screenplay-schema.json` 导出剧本 JSON Schema。

分章规则：

- 能识别类似 `第一章 标题`、`第1章 标题`、`Chapter 1` 的章节标题。
- 如果短篇文本没有分章标题，会保存为单章 `全文`，用户后续仍可手动编辑。
- 对于超长 TXT，可先使用 Agent 分章推导接口：本地抽取 head / middle / tail 片段，LLM 生成标题行规则，本地切分全文，LLM 检查统计与疑似漏切标题，必要时请求问题上下文并重写规则。
- Agent 请求的上下文会被后端按预算裁剪，避免把整本书或大段文本重新发送给模型。

AI 能力说明：

- 生产路径不会使用静态兜底内容冒充模型结果。
- 如果缺少 `DEEPSEEK_API_KEY` 或模型服务异常，接口会返回明确错误。
- 后端使用 Pydantic AI 的 `DeepSeekProvider` 调用 `deepseek-v4-pro`，兼容 DeepSeek 思考模式下的工具调用。
- 测试通过依赖注入 mock 模型边界，不影响生产路径真实调用。

剧本版本规则：

- 只有通过 harness 校验的 YAML 会写入 `script.yaml` 并生成版本快照。
- 生成、编辑、修复都会返回校验报告，便于前端展示错误与可量化指标。
- 局部编辑使用 `replace_script`、`patch_scene`、`replace_scene`、`insert_event`、`patch_event`、`delete_event` 等结构化操作，方便后续对话式迭代。

运行质量检查：

```bash
cd backend
uv run pytest
uv run ruff check .
uv run pyright
```

真实 DeepSeek 链路冒烟：

```bash
cd backend
uv run python -m app.tools.deepseek_smoke
```

该命令会读取 `.env` 中的 `DEEPSEEK_API_KEY`，使用临时 SQLite 与临时 artifacts 完成“创建项目 -> 导入三章短文 -> 生成 book_index.json -> 生成 script.yaml -> harness 校验并保存版本”的真实链路。默认不会保留运行产物；需要保留时可执行 `uv run python -m app.tools.deepseek_smoke --keep-artifacts`，产物会写入已被 git 忽略的 `backend/data/deepseek-smoke/`。

## 依赖说明

当前后端依赖：

- FastAPI：Web API 与自动化 OpenAPI 文档。
- Pydantic / Pydantic Settings：请求、响应、配置与领域模型。
- Pydantic AI：DeepSeek Agent 编排与结构化输出。
- SQLAlchemy async / aiosqlite：SQLite 异步数据访问。
- python-dotenv：本地环境变量管理。
- PyYAML：后续 YAML 解析、校验与导出。
- socksio：支持本地 SOCKS 代理环境下的 DeepSeek HTTP 调用。

当前后端开发依赖：

- pytest / pytest-asyncio：后端自动化测试。
- httpx：FastAPI 测试客户端。
- Ruff：Python lint 与导入检查。
- Pyright：Python 静态类型检查。

所有第三方依赖会持续在此处列明，并说明原创功能边界。
