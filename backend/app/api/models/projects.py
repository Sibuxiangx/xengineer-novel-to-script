from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Project title shown in the workspace.")
    screenplay_format: str = Field(
        "short_drama",
        description="Target screenplay format, such as short_drama or general.",
    )


class ProjectResponse(BaseModel):
    id: str = Field(..., description="Stable project identifier.")
    title: str = Field(..., description="Project title.")
    screenplay_format: str = Field(..., description="Target screenplay format.")
    artifact_root: str = Field(..., description="Local artifact directory for this project.")
    chapter_count: int = Field(..., description="Number of imported chapters.")
    current_script_version_id: str | None = Field(
        default=None,
        description="Current accepted script version ID, if one exists.",
    )
    created_at: datetime = Field(..., description="Project creation time.")
    updated_at: datetime = Field(..., description="Project last update time.")


class TxtEbookImportRequest(BaseModel):
    file_name: str = Field(..., min_length=1, description="Original TXT file name.")
    content: str = Field(..., min_length=1, description="TXT ebook content.")
    split_strategy: Literal["auto"] = Field(
        "auto",
        description="Chapter splitting strategy. MVP supports automatic splitting.",
    )
    replace_existing: bool = Field(
        True,
        description="Whether to replace existing chapters for the project.",
    )


class ChapterResponse(BaseModel):
    id: str = Field(..., description="Stable chapter identifier.")
    project_id: str = Field(..., description="Project identifier that owns this chapter.")
    title: str = Field(..., description="Chapter title shown to the author.")
    order_index: int = Field(..., description="Zero-based chapter order.")
    content: str = Field(..., description="Current editable chapter content.")
    file_path: str = Field(..., description="Local text file path for this chapter.")
    token_estimate: int | None = Field(default=None, description="Local token estimate.")
    created_at: datetime = Field(..., description="Chapter creation time.")


class TxtEbookImportResponse(BaseModel):
    project: ProjectResponse = Field(..., description="Project metadata after import.")
    chapters: list[ChapterResponse] = Field(..., description="Detected and saved chapters.")
    detected_chapter_count: int = Field(..., description="Number of chapters detected.")
    split_strategy: Literal["auto"] = Field(..., description="Applied splitting strategy.")


class ChapterUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, description="Updated chapter title.")
    content: str | None = Field(default=None, min_length=1, description="Updated chapter content.")


class ChapterListResponse(BaseModel):
    chapters: list[ChapterResponse] = Field(..., description="Project chapters in order.")

