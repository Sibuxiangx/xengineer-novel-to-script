from pydantic import BaseModel, Field


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


class BookIndex(BaseModel):
    schema_version: str = Field("1.0", description="索引 JSON Schema 版本。")
    book_id: str = Field(..., description="书籍或项目 ID。")
    title: str = Field(..., description="小说标题。")
    language: str = Field("zh-CN", description="小说语言。")
    chapter_count: int = Field(..., description="章节数量。")
    chapters: list[IndexedChapter] = Field(..., description="章节索引。")

