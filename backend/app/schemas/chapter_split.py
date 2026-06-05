from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChapterSplitRule(BaseModel):
    strategy: Literal["line_regex", "no_chapters"] = Field(
        ...,
        description="Chapter splitting strategy inferred from text samples.",
    )
    heading_regex: str | None = Field(
        default=None,
        max_length=300,
        description="Line-based regular expression that matches chapter heading lines.",
    )
    title_source: Literal["full_line"] = Field(
        "full_line",
        description="How to derive chapter titles from matched heading lines.",
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Model confidence for this rule.",
    )
    reason: str = Field(..., min_length=1, description="Chinese explanation of the rule.")
    examples: list[str] = Field(
        default_factory=list,
        description="Observed heading examples that support this rule.",
    )

    @model_validator(mode="after")
    def require_regex_for_line_strategy(self) -> "ChapterSplitRule":
        if self.strategy == "line_regex" and not self.heading_regex:
            raise ValueError("heading_regex is required for line_regex strategy.")
        return self


class TextPeekSample(BaseModel):
    label: Literal["head", "middle", "tail"] = Field(..., description="Sample position label.")
    start_char: int = Field(..., ge=0, description="Inclusive start character offset.")
    end_char: int = Field(..., ge=0, description="Exclusive end character offset.")
    text: str = Field(..., description="Sampled text content.")


class ChapterSplitContextRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Chinese reason for requesting context.")
    start_char: int = Field(..., ge=0, description="Requested inclusive start character offset.")
    end_char: int = Field(..., ge=0, description="Requested exclusive end character offset.")

    @model_validator(mode="after")
    def ensure_valid_range(self) -> "ChapterSplitContextRequest":
        if self.end_char <= self.start_char:
            raise ValueError("end_char must be greater than start_char.")
        return self


class ChapterSplitReview(BaseModel):
    accepted: bool = Field(..., description="Whether the local split result is acceptable.")
    diagnosis: str = Field(..., min_length=1, description="Chinese review diagnosis.")
    confidence: float = Field(..., ge=0, le=1, description="Review confidence.")
    context_requests: list[ChapterSplitContextRequest] = Field(
        default_factory=list,
        description="Additional text ranges needed before revising the rule.",
    )

    @model_validator(mode="after")
    def require_context_when_rejected(self) -> "ChapterSplitReview":
        if not self.accepted and not self.context_requests:
            raise ValueError("context_requests are required when the split is not accepted.")
        return self


class RequestedContextSample(BaseModel):
    request: ChapterSplitContextRequest = Field(..., description="Original context request.")
    start_char: int = Field(..., ge=0, description="Expanded inclusive start character offset.")
    end_char: int = Field(..., ge=0, description="Expanded exclusive end character offset.")
    text: str = Field(..., description="Expanded requested text content.")
    truncated: bool = Field(
        False,
        description="Whether the requested range was clipped to stay within the context budget.",
    )


class HeadingCandidate(BaseModel):
    line_number: int = Field(..., ge=1, description="One-based line number.")
    start_char: int = Field(..., ge=0, description="Line start character offset.")
    text: str = Field(..., description="Candidate heading line text.")
