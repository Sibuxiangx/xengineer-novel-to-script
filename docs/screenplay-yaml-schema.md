# 剧本 YAML Schema 设计文档

本文档定义本项目输出的 `script.yaml` 结构，并说明 Schema 的设计原因。代码实现以 `backend/app/schemas/screenplay.py` 中的 Pydantic 模型为准；后端可通过 `/chat/sessions/{session_id}/assets/scripts/versions/{version_id}` 读取生成的 YAML 版本，也可通过 service 层导出 JSON Schema。

## 设计目标

小说转剧本不是把原文改写成另一段散文，而是把故事拆成可追踪、可编辑、可校验的创作资产。因此 Schema 需要同时满足四个目标：

- 可读：作者和评审可以直接阅读 YAML，理解人物、地点、场景、事件和改编意图。
- 可追溯：每个场景必须说明来源章节，避免 AI 生成内容脱离原文。
- 可编辑：人物、地点、场景、事件都使用稳定 ID，方便后续对话式局部修改。
- 可校验：后端 harness 能检查结构、引用、来源、改编说明和基础质量指标。

## 顶层结构

```yaml
schema_version: "1.0"
project: {}
characters: []
locations: []
scenes: []
```

### `schema_version`

类型：`string`

说明：标记当前 YAML Schema 版本。MVP 使用 `"1.0"`。版本号用于后续兼容更多结构，例如幕结构、关系图谱、质量报告等。

设计原因：比赛提交需要清楚定义 Schema。显式版本号可以让生成、校验、导出和未来迁移都有稳定契约。

### `project`

类型：`ProjectMetadata`

字段：

- `title: string`，剧本标题。
- `genre: string[]`，类型标签，例如 `["悬疑", "短剧"]`。
- `format: short_drama | film | series_episode | stage_play | audio_drama | general`，目标剧本格式。
- `logline: string`，一句话说明故事核心冲突。
- `target_audience?: string`，目标观众或读者。
- `tone?: string`，整体风格。

设计原因：`project` 是剧本整体创作意图，帮助评审快速判断改编方向，也帮助后续 agent 编辑时保持风格一致。

### `characters`

类型：`Character[]`

字段：

- `id: string`，稳定人物 ID，例如 `char_lin`。
- `name: string`，人物显示名称。
- `role: string`，人物在故事中的功能，例如 `protagonist`、`supporting`、`antagonist`。
- `description: string`，人物简述。
- `goals: string[]`，人物目标。
- `conflicts: string[]`，人物内外部冲突。
- `speech_style?: string`，人物语言风格。
- `arc?: string`，人物弧光。

设计原因：剧本改编高度依赖人物目标、冲突和语言风格。把人物抽成全局表，能让对白事件通过 `character_id` 引用人物，避免重复描述和名称漂移。

### `locations`

类型：`Location[]`

字段：

- `id: string`，稳定地点 ID，例如 `loc_theater`。
- `name: string`，地点名称。
- `description: string`，地点描述。
- `visual_motifs: string[]`，视觉母题。

设计原因：剧本是可拍摄、可排演的文本。地点表让场景设定可复用，也方便 harness 检查场景是否引用了不存在的地点。

### `scenes`

类型：`Scene[]`

字段：

- `id: string`，稳定场景 ID，例如 `scene_001`。
- `title: string`，场景标题。
- `source_refs: SourceReference[]`，来源引用。
- `setting: SceneSetting`，场景设定。
- `dramatic_purpose: string`，该场景的戏剧目的。
- `conflict: string`，该场景的核心冲突。
- `events: ScriptEvent[]`，结构化剧本事件。
- `turning_point?: string`，场景转折点。
- `emotional_shift?: string`，情绪变化。
- `adaptation_notes?: AdaptationNotes`，改编说明。

设计原因：场景是小说到剧本的核心转换单位。相比直接输出长段剧本正文，结构化场景能表达“为什么这一场存在”“冲突是什么”“来自原文哪里”“哪些内容被删改”，更适合 agent 后续局部编辑和 harness 校验。

## 子结构

### `SourceReference`

```yaml
chapter_id: "chapter_001"
range_hint: "章节开头"
usage: "adapted"
```

字段：

- `chapter_id: string`，来源章节 ID，必须对应已导入章节。
- `range_hint: string`，来源范围提示。
- `usage: adapted | merged | compressed | omitted_context | inferred`，该来源在场景中的使用方式。

设计原因：AI 改编容易产生“看起来合理但无法追溯”的内容。`source_refs` 让每个场景都能回到章节源头，也让评审看到本项目不是一次性泛化生成。

### `SceneSetting`

```yaml
location_id: "loc_theater"
time_of_day: "night"
atmosphere: "潮湿、压迫"
```

字段：

- `location_id: string`，引用 `locations` 中的地点 ID。
- `time_of_day?: string`，发生时段。
- `atmosphere?: string`，场景氛围。

设计原因：剧本需要具备空间和表演提示。`location_id` 使用引用而不是重复名称，是为了让 harness 能检查引用完整性。

### `ScriptEvent`

```yaml
id: "event_001"
type: "dialogue"
character_id: "char_lin"
content: "这封信不该在今天出现。"
emotion: "压抑"
subtext: "他已经认出票根日期。"
beat: "线索触发"
duration_hint: "8s"
```

字段：

- `id: string`，稳定事件 ID。
- `type: action | dialogue | narration | stage_direction | sound | transition`，事件类型。
- `content: string`，事件正文。
- `character_id?: string`，对白事件引用的人物 ID。
- `emotion?: string`，情绪提示。
- `subtext?: string`，潜台词。
- `beat?: string`，戏剧节拍。
- `duration_hint?: string`，时长提示。

设计原因：事件是局部编辑最小单位。给事件加稳定 ID 后，用户可以说“把第二场最后一句对白改得更克制”，agent 能定位到具体 `scene.events.event_id`，而不是重写整份 YAML。

### `AdaptationNotes`

```yaml
intent: "把小说线索转换为可表演场景。"
omitted_or_changed:
  - "压缩了原文中连续三段内心独白。"
risks:
  - "线索节奏变快，可能削弱人物犹豫感。"
```

字段：

- `intent: string`，本场改编意图。
- `omitted_or_changed: string[]`，删改说明。
- `risks: string[]`，可能损失或需要复核的内容。

设计原因：小说改编必须做取舍。`adaptation_notes` 要求 agent 明确说明删改意图和风险，方便作者接管，也体现“产品架构师”视角里的可解释交付。

实现说明：Pydantic 模型中 `adaptation_notes` 允许为空，方便保存 rejected draft；但 harness 对 accepted 版本要求每个 scene 必须包含 `adaptation_notes`。这能让失败产物可保存，同时保证最终版本有改编解释。

## 最小示例

```yaml
schema_version: "1.0"
project:
  title: "雾港来信"
  genre:
    - "悬疑"
  format: "short_drama"
  logline: "编剧追查旧信背后的剧场秘密。"
  target_audience: "悬疑短剧观众"
  tone: "冷峻、克制"
characters:
  - id: "char_lin"
    name: "林栩"
    role: "protagonist"
    description: "追查旧信来源的编剧。"
    goals:
      - "确认导师失踪真相。"
    conflicts:
      - "害怕重新面对失败的剧本。"
    speech_style: "短句多，情绪压住不外露。"
locations:
  - id: "loc_theater"
    name: "雾港剧场"
    description: "被雨声包围的旧剧场。"
    visual_motifs:
      - "蓝色工作灯"
      - "潮湿旧海报"
scenes:
  - id: "scene_001"
    title: "旧信抵达"
    source_refs:
      - chapter_id: "chapter_001"
        range_hint: "章节开头"
        usage: "adapted"
    setting:
      location_id: "loc_theater"
      time_of_day: "night"
      atmosphere: "潮湿、压迫"
    dramatic_purpose: "建立主角目标与旧剧场线索。"
    conflict: "林栩必须判断旧信是否是陷阱。"
    events:
      - id: "event_001"
        type: "action"
        content: "林栩拆开旧信，取出一张旧剧场票根。"
      - id: "event_002"
        type: "dialogue"
        character_id: "char_lin"
        content: "这封信不该在今天出现。"
        emotion: "压抑"
        subtext: "他已经认出票根日期。"
    turning_point: "林栩发现票根日期与导师失踪日一致。"
    emotional_shift: "从抗拒到被迫行动。"
    adaptation_notes:
      intent: "把小说中的内心震动转成可表演动作和对白。"
      omitted_or_changed:
        - "压缩了原文中对雨夜环境的重复描写。"
      risks:
        - "开场节奏加快，需在后续场景补足人物犹豫。"
```

## Harness 校验规则

后端 `ValidationService` 会在生成、编辑、修复和导出前校验 YAML。

主要错误：

- YAML 无法解析。
- 根节点不是对象。
- Pydantic Schema 校验失败。
- `characters`、`locations`、`scenes`、`events` 存在重复 ID。
- 场景引用了未定义地点。
- 对白事件缺少 `character_id`。
- 事件引用了未定义人物。
- `source_refs.chapter_id` 不存在于导入章节。
- 场景为空。
- accepted 版本缺少 `adaptation_notes`。

主要警告：

- 场景数量少于章节数量，可能存在压缩或遗漏。
- `book_index.json` 中重要人物未出现在剧本人物表。
- 来源覆盖、改编说明或章节压缩需要作者复核。

状态语义：

- `accepted`：通过 harness，可写入当前 `script.yaml` 并成为可导出版本。
- `rejected`：生成了可接管草稿，但未通过 harness。系统会保存 rejected draft、validation report 和上下文报告，方便后续修复。

## 编辑操作设计

本项目不会要求 agent 每次重写整份 YAML，而是使用结构化 patch operation：

- `patch_project`
- `upsert_character` / `delete_character`
- `upsert_location` / `delete_location`
- `insert_scene` / `replace_scene` / `patch_scene` / `delete_scene` / `reorder_scenes`
- `insert_event` / `replace_event` / `patch_event` / `delete_event` / `reorder_events`
- `patch_adaptation_notes`
- `create_script` / `replace_script`

设计原因：

- 局部操作更可审查，PR 和 commit 也更容易解释。
- 稳定 ID 能让前端资产栏、YAML 编辑器和 agent 对话定位同一个节点。
- patch 后会重新运行 harness；无变化 patch、未知 operation 或当前 Schema 不支持的 operation 会显式失败，不会假装成功。

## 为什么暂不加入更复杂结构

计划文档中讨论过 `acts`、人物关系图谱、顶层质量报告等结构。本次 MVP 没有全部放入顶层 Schema，原因是：

- 72 小时挑战优先保证完整核心闭环：导入、分章、索引、生成、校验、编辑、修复、版本。
- 现有 `book_index.json` 已承担关系、时间线、线索等长期记忆职责，`script.yaml` 只保留剧本交付所需的核心结构。
- 顶层结构越复杂，模型生成失败和用户手工编辑成本越高。

后续扩展时，建议在 `schema_version: "1.1"` 中增加：

- `acts`：幕结构和场景分组。
- `quality_report`：覆盖率、对白比例、场景数量、风险摘要。
- `relationships`：直接写入剧本侧的人物关系变化。
- `source`：顶层来源章节清单和源文本哈希。
