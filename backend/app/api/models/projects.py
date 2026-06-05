from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.chapter_split import (
    ChapterSplitReview,
    ChapterSplitRule,
    HeadingCandidate,
    RequestedContextSample,
    TextPeekSample,
)


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
    split_strategy: Literal["auto", "custom_rule"] = Field(
        "auto",
        description="Chapter splitting strategy. Use custom_rule with a supplied rule.",
    )
    chapter_split_rule: ChapterSplitRule | None = Field(
        default=None,
        description="Optional inferred or user-provided rule for custom chapter splitting.",
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
    split_strategy: Literal["auto", "custom_rule"] = Field(
        ...,
        description="Applied splitting strategy.",
    )


class ChapterUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, description="Updated chapter title.")
    content: str | None = Field(default=None, min_length=1, description="Updated chapter content.")


class ChapterListResponse(BaseModel):
    chapters: list[ChapterResponse] = Field(..., description="Project chapters in order.")


class ChapterSplitInferenceRequest(BaseModel):
    file_name: str = Field(..., min_length=1, description="Original TXT file name.")
    content: str = Field(..., min_length=1, description="TXT ebook content.")
    max_sample_chars: int = Field(
        5000,
        ge=1000,
        le=12000,
        description="Maximum characters per head/middle/tail sample sent to the agent.",
    )
    max_review_rounds: int = Field(
        2,
        ge=0,
        le=3,
        description="Maximum review-and-revise rounds after initial rule inference.",
    )
    context_window_chars: int = Field(
        1200,
        ge=300,
        le=5000,
        description="Characters added around every agent-requested context range.",
    )


class ChapterSplitInferencePreview(BaseModel):
    chapter_count: int = Field(..., description="Preview chapter count after applying the rule.")
    titles: list[str] = Field(..., description="First detected chapter titles for preview.")
    last_titles: list[str] = Field(..., description="Last detected chapter titles for preview.")
    candidate_heading_count: int = Field(
        ...,
        description="Loose local candidate heading count.",
    )
    unmatched_candidate_count: int = Field(
        ...,
        description="Loose candidate headings not matched by the current rule.",
    )
    unmatched_candidates: list[HeadingCandidate] = Field(
        default_factory=list,
        description="First unmatched candidate headings.",
    )


class ChapterSplitInferenceIteration(BaseModel):
    round_index: int = Field(..., ge=0, description="Zero-based inference/review round.")
    rule: ChapterSplitRule = Field(..., description="Rule used in this round.")
    preview: ChapterSplitInferencePreview = Field(
        ...,
        description="Local split preview for this round.",
    )
    review: ChapterSplitReview = Field(..., description="Agent review for this round.")
    requested_contexts: list[RequestedContextSample] = Field(
        default_factory=list,
        description="Context samples requested by the review and used for the next revision.",
    )


class ChapterSplitInferenceResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    file_name: str = Field(..., description="Original TXT file name.")
    text_length: int = Field(..., description="Input text length in characters.")
    samples: list[TextPeekSample] = Field(..., description="Peek samples sent to the agent.")
    rule: ChapterSplitRule = Field(..., description="Inferred chapter split rule.")
    preview: ChapterSplitInferencePreview = Field(
        ...,
        description="Local splitting preview using the inferred rule.",
    )
    iterations: list[ChapterSplitInferenceIteration] = Field(
        default_factory=list,
        description="Agentic infer-execute-review-revise trace.",
    )
