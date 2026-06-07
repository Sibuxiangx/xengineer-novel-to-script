<p align="center">
  <img src="frontend/public/brand/scriptweaver-icon.png" alt="ScriptWeaver icon" width="120" />
</p>

# ScriptWeaver

> 面向小说作者与内容策划的 AI 结构化剧本工作台。

![ScriptWeaver 产品图](frontend/src/assets/hero.png)

ScriptWeaver 是七牛云 XEngineer 新工科计划第三批次参赛项目，面向「AI 小说转剧本工具」选题。产品目标不是做一次性的 Prompt 生成器，而是提供一个可持续协作的剧本工作台：导入小说 TXT，通过 Chat Agent 完成分章确认、剧情索引、结构化剧本生成、验证、局部编辑、修复与版本管理。

## 选题

题目三：AI 小说转剧本工具

很多小说作者希望将自己的作品改编成剧本。本项目开发一款 AI 辅助剧本创作工具，降低改编门槛，提升结构化交付效率。

目标能力：

- 将 3 个章节以上的小说文本自动转换为结构化剧本。
- 输出可编辑、可校验、可进一步打磨的 YAML 剧本初稿。
- 提供剧本 YAML Schema 文档，并说明 Schema 的设计原因。
- 帮助作者理解章节、人物、场景、冲突、对白与舞台动作之间的改编关系。

## 产品方向

项目优先做成一个面向作者的改编工作台，而不是单次 Prompt 生成器。

计划工作流：

1. 导入 3 个及以上小说章节。
2. 分析章节结构、主要人物、地点、时间线与关键事件。
3. 将小说内容拆分为剧本场次。
4. 生成符合 YAML Schema 的剧本初稿。
5. 校验 YAML 结构并提示可修复问题。
6. 支持作者查看、编辑、重新生成局部内容、切换历史版本并导出结果。

## 计划交付物

- Web 应用或桌面可运行应用。
- 剧本 YAML Schema 设计文档：[`docs/screenplay-yaml-schema.md`](docs/screenplay-yaml-schema.md)。
- 小说转剧本核心流程。
- YAML 校验与错误提示。
- README 使用说明。
- Demo 视频链接。

## 当前状态

仓库创建于第三批次题目开放后。当前后端已完成项目创建、TXT 导入分章、剧情索引、上下文打包、剧本 YAML 生成、本地验证、基于旧结果的问题修复、rejected draft 保存、局部编辑、版本管理、SSE 心跳与可观测性闭环，并新增面向 Chat 产品形态的 Agent 会话、真实工具调用流与用户确认点。当前前端已基于 Ant Design X 重建为三栏结构：左侧承载结构目录与会话历史，中间作为剧本预览、可视化编辑、YAML 源码和历史版本的核心工作区，右侧作为 AI 协作对话与折叠运行详情入口。

## 运行方式

### 一键启动开发环境

需要同时查看前端并调用本地后端时，可以在仓库根目录执行：

```bash
pnpm run dev
```

默认启动地址：

- 前端：`http://localhost:5173`
- 后端：`http://127.0.0.1:8000`

脚本会自动导出 `VITE_API_BASE_URL=http://127.0.0.1:8000`，并在退出时同时停止前后端进程。如果首次运行缺少 `backend/.env`、`backend/.venv` 或 `frontend/node_modules`，脚本会补齐基础本地环境。

启动前会先执行后端环境变量预检：

- 如果 `backend/.env` 不存在，会从 `backend/.env.example` 创建。
- 如果必填变量为空，会在终端中用交互式提示要求补齐，例如 `DEEPSEEK_API_KEY`。
- 如果当前不是交互式终端，预检会直接失败并提示缺少的变量，避免启动后才在 Agent 调用阶段报错。
- 已配置环境时可执行 `pnpm run env:check` 快速检查。

### 后端

后端使用 Python、uv、FastAPI、Pydantic、Pydantic AI、SQLAlchemy async、SQLite 与本地文件存储。

```bash
cd backend
uv sync
cp .env.example .env
uv run fastapi dev app/main.py
```

### 后端环境变量

后端配置文件位于 `backend/.env`，该文件已被 `.gitignore` 忽略，不应提交到仓库。可以手动复制示例文件，也可以直接运行 `pnpm run dev` 让脚本引导创建。

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 是 | 无 | DeepSeek API Key。生产路径没有静态兜底，缺失时 Agent 会明确报错。 |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek 兼容 API 基址。 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-v4-pro` | Chat Agent 与复杂推理默认模型。 |
| `DEEPSEEK_FAST_MODEL` | 否 | `deepseek-v4-flash` | 剧情索引、初版剧本 YAML 等高吞吐结构化生成模型。 |
| `MODEL_CONTEXT_LIMIT` | 否 | `1000000` | 本地上下文预算估算上限。 |
| `BACKEND_CORS_ORIGINS` | 否 | `http://localhost:5173` | 允许访问后端的前端来源，多个值用英文逗号分隔。 |
| `SQLITE_DATABASE_URL` | 否 | `sqlite+aiosqlite:///./data/app.db` | 本地 SQLite 异步数据库地址。 |
| `LOCAL_ARTIFACT_ROOT` | 否 | `./data/projects` | 小说章节、剧情索引、剧本 YAML 等本地产物目录。 |
| `DATABASE_ECHO` | 否 | `false` | 是否输出 SQLAlchemy SQL 日志。 |

常用检查命令：

```bash
pnpm run env:check
```

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

当前后端已支持的基础流程：

产品主入口是 Chat Agent：

1. `POST /chat/sessions` 创建对话会话，用于左侧项目区。
2. `GET /chat/sessions` 获取会话列表。
3. `GET /chat/sessions/{session_id}` 获取消息、待确认项和最近剧本版本。
4. `POST /chat/sessions/{session_id}/runs/stream` 通过 SSE 发送用户消息。上传或粘贴 TXT 时，第一条消息可以同时包含改编要求；后端会立刻返回一条确认收到的 assistant 消息，然后依次推导项目名、创建项目、推导分章规则，并返回 `tool.confirm.required` 等待用户确认。
5. `POST /chat/sessions/{session_id}/confirmations/{confirmation_id}/stream` 通过 SSE 处理确认。确认分章后，后端会自动导入章节、生成 `book_index.json`、生成并校验 `script.yaml`，并通过 `asset.updated` 通知前端刷新资产区。
6. `GET /chat/sessions/{session_id}/assets/chapters` 读取会话项目的章节资产。
7. `GET /chat/sessions/{session_id}/assets/book-index` 读取会话项目的 `book_index.json`。
8. `GET /chat/sessions/{session_id}/assets/scripts/versions` 读取会话项目的 YAML 版本列表，包括 accepted versions 和 rejected drafts。
9. `GET /chat/sessions/{session_id}/assets/scripts/versions/{version_id}` 读取某个 YAML 版本详情。

SSE 事件类型：

- `run.started`：一次 Agent 执行开始。
- `run.progress`：长任务阶段进度，例如 `source_ingestion_agent`、`build_book_index`、`generate_script_yaml` 的 started / completed / failed。
- `heartbeat`：长任务运行期间的 SSE 保活事件，避免连接长时间无输出。
- `message.delta`：助手可展示回复片段。
- `tool.call.started` / `tool.call.completed`：工具调用开始与完成。
- `tool.confirm.required`：需要用户确认的工具结果，例如分章预览。
- `asset.updated`：章节、剧情索引、剧本 YAML 等资产更新。
- `validation.completed`：本地验证完成，包含 accepted/rejected 状态、validation report、repair 次数和 context report。
- `model.usage.estimated`：本地估算模型输入 token 和上下文块使用情况。
- `run.waiting_confirmation` / `run.completed` / `run.completed_with_errors`：执行暂停、成功完成或生成可接管产物但仍存在错误。
- `error`：可展示错误，不用静态兜底冒充成功。

产品 API 已完成减法：前端只应使用 `/health` 与 `/chat/**`。项目、分章、索引、剧本生成、校验、编辑、修复和版本管理仍由后端 service 层保留，但不再作为公开底层 router 暴露给产品前端。

分章规则：

- 能识别类似 `第一章 标题`、`第1章 标题`、`Chapter 1` 的章节标题。
- 如果短篇文本没有分章标题，会保存为单章 `全文`，用户后续仍可手动编辑。
- 对于超长 TXT，Chat Agent 会在内部执行分章推导：本地抽取 head / middle / tail 片段，LLM 生成标题行规则，本地切分全文，LLM 检查统计与疑似漏切标题，必要时请求问题上下文并重写规则。
- Agent 请求的上下文会被后端按预算裁剪，避免把整本书或大段文本重复发送给模型。
- `book_index.json`、剧本生成、YAML 编辑和 repair 都会经过 `ContextPromptBuilder` 与 `ContextPacker`。后端使用本地 DeepSeek V4 tokenizer 估算 token，响应、详情接口和 SSE 中的 `context_report` / `model.usage.estimated` 会展示有效预算、估算 token、包含块和省略块。

AI 能力说明：

- 生产路径不会使用静态兜底内容冒充模型结果。
- 如果缺少 `DEEPSEEK_API_KEY` 或模型服务异常，接口会返回明确错误。
- 后端使用 Pydantic AI 的 `DeepSeekProvider` 调用 `deepseek-v4-pro`，兼容 DeepSeek 思考模式下的工具调用。
- 测试通过依赖注入 mock 模型边界，不影响生产路径真实调用。
- 当前 `model_usage_events` 会记录本地估算 input tokens。真实 provider usage 将在后续接入 Pydantic AI result usage 后继续补齐。

剧本版本规则：

- 通过本地验证的 YAML 会写入当前 `script.yaml`，并生成 `validation_status=accepted` 的版本快照。
- 如果生成、编辑或修复后仍未通过验证，系统会保存 `validation_status=rejected` 的 rejected draft，不会假装成功。
- 生成、编辑、修复都会返回校验报告，便于前端展示错误、修复建议与可量化指标。
- 局部编辑使用结构化 YAML patch operations，例如 `patch_project`、`upsert_character`、`upsert_location`、`insert_scene`、`delete_scene`、`reorder_scenes`、`insert_event`、`replace_event`、`reorder_events`、`patch_adaptation_notes`。未知 operation、无变化 patch 或当前 Schema 不支持的 operation 会显式失败，不会保存空成功版本。

生成后的自由对话规则：

- 用户明确要求修改剧本时，Agent 会调用 `edit_script_yaml` 生成结构化编辑操作。
- 用户询问原文剧情、人物动机、伏笔、章节摘要、当前剧本与原文差异或改编依据时，Agent 会调用 `answer_novel_question`，把小说章节、`book_index.json` 和当前 `script.yaml` 当作知识库回答，不会改动剧本版本。
- 首轮上传 TXT 时附带的改编要求会保存为项目 artifact，并进入后续 `book_index.json` 和 `script.yaml` 生成上下文。

YAML Schema 文档：

- 设计文档：[`docs/screenplay-yaml-schema.md`](docs/screenplay-yaml-schema.md)
- 代码模型：`backend/app/schemas/screenplay.py`
- 校验入口：`backend/app/services/validation_service.py`
- 局部编辑操作：`backend/app/schemas/yaml_patch.py` 与 `backend/app/services/yaml_patch_service.py`

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

该命令会读取 `.env` 中的 `DEEPSEEK_API_KEY`，使用临时 SQLite 与临时 artifacts 完成“创建项目 -> 导入三章短文 -> 生成 book_index.json -> 生成 script.yaml -> 本地验证并保存版本”的真实链路。每个模型步骤默认 180 秒超时，可通过 `--timeout-seconds 300` 调整。默认不会保留运行产物；需要保留时可执行 `uv run python -m app.tools.deepseek_smoke --keep-artifacts`，产物会写入已被 git 忽略的 `backend/data/deepseek-smoke/`。

### 前端

前端使用 React、TypeScript、Vite、pnpm、Ant Design X、Ant Design、TanStack Query、React Router、Monaco Editor 与 `yaml`。

```bash
cd frontend
pnpm install
cp .env.example .env
pnpm dev
```

前端默认读取 `VITE_API_BASE_URL=http://127.0.0.1:8000`。当前界面主流程：

1. 打开产品后，左侧显示结构/会话导航，中间显示剧本工作区，右侧显示 AI 对话入口。
2. 用户上传或粘贴 TXT，也可以在第一条消息里附带改编要求；前端通过 POST SSE 调用 `/chat/sessions/{session_id}/runs/stream`。
3. 对话流通过 Ant Design X `Bubble.List` 展示 Agent 消息、分章确认点和默认折叠的工具执行细节。
4. 用户在分章确认面板中查看预览、可编辑标题正则，并确认继续。
5. 确认后前端通过 `/chat/sessions/{session_id}/confirmations/{confirmation_id}/stream` 继续接收导入章节、构建索引、生成 YAML 与验证结果。
6. 中间剧本工作区展示章节、`book_index.json`、剧本可视化表单、YAML 源码、验证报告和版本记录；切换历史版本后，后续局部编辑会基于当前选中版本生成新的版本快照。
7. 剧本生成后，用户可以继续用自然语言要求修改剧本，也可以把小说当知识库询问剧情、人物、伏笔和改编依据。

前端质量检查：

```bash
cd frontend
pnpm lint
pnpm build
```

设计规范：

- `DESIGN.md`：当前 UI 的 Ant Design X 组件映射和设计约束。
- `.impeccable.md`：产品用户、语气和设计原则上下文。

## 依赖说明

当前后端依赖：

- FastAPI：Web API 与自动化 OpenAPI 文档。
- Pydantic / Pydantic Settings：请求、响应、配置与领域模型。
- Pydantic AI：DeepSeek Agent 编排与结构化输出。
- SQLAlchemy async / aiosqlite：SQLite 异步数据访问。
- python-dotenv：本地环境变量管理。
- PyYAML：后续 YAML 解析、校验与导出。
- socksio：支持本地 SOCKS 代理环境下的 DeepSeek HTTP 调用。
- tokenizers：读取项目内置 DeepSeek V4 tokenizer.json，进行本地 token 估算。

当前后端开发依赖：

- pytest / pytest-asyncio：后端自动化测试。
- httpx：FastAPI 测试客户端。
- Ruff：Python lint 与导入检查。
- Pyright：Python 静态类型检查。

当前前端依赖：

- React / TypeScript / Vite：前端开发与构建。
- pnpm：前端依赖管理。
- Ant Design X：AI 对话界面组件，包括 `Bubble.List`、`Sender`、`Attachments`、`Conversations`、`Welcome`、`Prompts`、`ThoughtChain`。
- Ant Design / `@ant-design/icons`：通用产品组件、图标、主题和资产侧边栏。
- TanStack Query：接口请求状态与缓存。
- React Router：前端路由入口。
- Monaco Editor：剧本 YAML 源码查看器。
- `yaml`：前端解析和重新序列化剧本 YAML，用于可视化编辑草稿。

所有第三方依赖会持续在此处列明，并说明原创功能边界。
