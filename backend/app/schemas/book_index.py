from pydantic import BaseModel, Field


class IndexedCharacter(BaseModel):
    id: str = Field(..., description="稳定人物 ID。")
    names: list[str] = Field(..., description="人物姓名与别名。")
    role: str = Field(..., description="人物在故事中的功能。")
    description: str = Field(..., description="人物简述。")
    goals: list[str] = Field(default_factory=list, description="人物目标。")
    secrets: list[str] = Field(default_factory=list, description="人物秘密。")
    speech_style: str | None = Field(default=None, description="人物说话风格。")
    first_appearance: str | None = Field(default=None, description="首次出现章节 ID。")
    last_known_state: str | None = Field(default=None, description="最新状态。")


class IndexedLocation(BaseModel):
    id: str = Field(..., description="稳定地点 ID。")
    name: str = Field(..., description="地点名称。")
    description: str = Field(..., description="地点描述。")
    appearances: list[str] = Field(default_factory=list, description="出现章节 ID 列表。")


class IndexedEvent(BaseModel):
    id: str = Field(..., description="稳定剧情事件 ID。")
    summary: str = Field(..., description="剧情事件摘要。")
    characters: list[str] = Field(default_factory=list, description="事件涉及人物 ID。")
    locations: list[str] = Field(default_factory=list, description="事件涉及地点 ID。")
    importance: str = Field("minor", description="事件重要程度。")


class IndexedChapter(BaseModel):
    id: str = Field(..., description="稳定章节 ID。")
    title: str = Field(..., description="章节标题。")
    order: int = Field(..., description="章节顺序。")
    summary: str = Field(..., description="章节摘要。")
    token_estimate: int | None = Field(default=None, description="章节 token 估算。")
    events: list[IndexedEvent] = Field(default_factory=list, description="章节关键事件。")


class IndexedRelationship(BaseModel):
    from_character: str = Field(..., description="关系发起方人物 ID。")
    to_character: str = Field(..., description="关系指向方人物 ID。")
    type: str = Field(..., description="关系类型。")
    development: str | None = Field(default=None, description="关系变化。")


class PlotThread(BaseModel):
    id: str = Field(..., description="稳定剧情线索 ID。")
    name: str = Field(..., description="剧情线索名称。")
    status: str = Field(..., description="线索状态，例如 open 或 closed。")
    introduced_in: str | None = Field(default=None, description="引入章节 ID。")
    payoff: str | None = Field(default=None, description="回收说明。")


class BookIndex(BaseModel):
    schema_version: str = Field("1.0", description="索引 JSON Schema 版本。")
    book_id: str = Field(..., description="书籍或项目 ID。")
    title: str = Field(..., description="小说标题。")
    language: str = Field("zh-CN", description="小说语言。")
    chapter_count: int = Field(..., description="章节数量。")
    chapters: list[IndexedChapter] = Field(..., description="章节索引。")
    characters: list[IndexedCharacter] = Field(default_factory=list, description="人物索引。")
    relationships: list[IndexedRelationship] = Field(
        default_factory=list,
        description="人物关系索引。",
    )
    locations: list[IndexedLocation] = Field(default_factory=list, description="地点索引。")
    timeline: list[str] = Field(default_factory=list, description="剧情时间线摘要。")
    plot_threads: list[PlotThread] = Field(default_factory=list, description="剧情线索。")
