from typing import Literal

from pydantic import BaseModel, Field


class ApiErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")
    code: str = Field(..., description="Stable application error code.")


class ValidationIssueResponse(BaseModel):
    code: str = Field(..., description="Stable validation issue code.")
    severity: Literal["info", "warning", "error", "blocking"] = Field(
        ...,
        description="Validation severity.",
    )
    path: str = Field(..., description="YAML or object path associated with this issue.")
    message: str = Field(..., description="Human-readable validation message.")
    repair_hint: str | None = Field(default=None, description="Optional repair guidance.")
    source: Literal["yaml_parse", "schema", "reference", "book_index", "policy", "export"] = Field(
        ...,
        description="Validation source category.",
    )


class ValidationReportResponse(BaseModel):
    accepted: bool = Field(..., description="Whether the script can be accepted.")
    severity: Literal["info", "warning", "error", "blocking"] = Field(
        ...,
        description="Highest validation severity.",
    )
    errors: list[ValidationIssueResponse] = Field(
        default_factory=list,
        description="Blocking or error-level validation issues.",
    )
    warnings: list[ValidationIssueResponse] = Field(
        default_factory=list,
        description="Warning-level validation issues.",
    )
    metrics: dict[str, int | float | str] = Field(
        default_factory=dict,
        description="Validation metrics for UI and diagnostics.",
    )

