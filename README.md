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

仓库创建于第三批次题目开放后。当前仅完成项目初始化与选题确认，正式开发将在后续 PR 中持续推进。

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
3. `GET /projects/{project_id}/chapters` 查看导入后的章节。
4. `PATCH /projects/{project_id}/chapters/{chapter_id}` 手动编辑章节标题或正文。
5. `POST /projects/{project_id}/book-index` 调用 DeepSeek Agent 生成 `book_index.json`。
6. `GET /projects/{project_id}/book-index` 读取已生成的剧情索引。
7. `POST /projects/{project_id}/scripts/validate` 使用 harness 校验剧本 YAML。

分章规则：

- 能识别类似 `第一章 标题`、`第1章 标题`、`Chapter 1` 的章节标题。
- 如果短篇文本没有分章标题，会保存为单章 `全文`，用户后续仍可手动编辑。

AI 能力说明：

- 生产路径不会使用静态兜底内容冒充模型结果。
- 如果缺少 `DEEPSEEK_API_KEY` 或模型服务异常，接口会返回明确错误。
- 测试通过依赖注入 mock 模型边界，不影响生产路径真实调用。

运行测试：

```bash
cd backend
uv run pytest
```

## 依赖说明

当前后端依赖：

- FastAPI：Web API 与自动化 OpenAPI 文档。
- Pydantic / Pydantic Settings：请求、响应、配置与领域模型。
- Pydantic AI：后续 Agent 编排核心。
- SQLAlchemy async / aiosqlite：SQLite 异步数据访问。
- python-dotenv：本地环境变量管理。
- PyYAML：后续 YAML 解析、校验与导出。

所有第三方依赖会持续在此处列明，并说明原创功能边界。
