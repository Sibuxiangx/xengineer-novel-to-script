from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.models.common import ValidationReportResponse
from app.schemas.yaml_patch import YamlPatchOperation
from app.services.context_packer import ContextPackingReport


class ScriptValidateRequest(BaseModel):
    script_yaml: str = Field(..., min_length=1, description="Screenplay YAML content to validate.")


class ScriptValidateResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    validation_report: ValidationReportResponse = Field(
        ...,
        description="Harness validation report.",
    )


class ScriptGenerateRequest(BaseModel):
    force_regenerate: bool = Field(
        False,
        description="Whether to regenerate even when a current script already exists.",
    )


class ScriptGenerateResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    script_yaml: str = Field(..., description="Generated screenplay YAML content.")
    validation_report: ValidationReportResponse = Field(
        ...,
        description="Harness validation report.",
    )
    accepted_version_id: str | None = Field(
        default=None,
        description="Accepted version ID if validation passed.",
    )
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID if validation failed after repairs.",
    )
    repair_attempt_count: int = Field(
        0,
        description="Automatic repair attempts performed before returning this result.",
    )
    validation_status: Literal["accepted", "rejected"] = Field(
        "accepted",
        description="Final persisted validation status for the YAML result.",
    )
    context_report: ContextPackingReport | None = Field(
        default=None,
        description="Context packing diagnostics for the primary model prompt.",
    )


class ScriptEditRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Chinese edit instruction.")
    target_path: str | None = Field(default=None, description="Optional explicit YAML path target.")


class ScriptEditResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    operations: list[YamlPatchOperation] = Field(..., description="Applied patch operations.")
    script_yaml: str = Field(..., description="Patched screenplay YAML content.")
    validation_report: ValidationReportResponse = Field(
        ...,
        description="Harness validation report.",
    )
    accepted_version_id: str | None = Field(default=None, description="Accepted version ID.")
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID if validation failed after repairs.",
    )
    repair_attempt_count: int = Field(
        0,
        description="Automatic repair attempts performed before returning this result.",
    )
    validation_status: Literal["accepted", "rejected"] = Field(
        "accepted",
        description="Final persisted validation status for the YAML result.",
    )
    context_report: ContextPackingReport | None = Field(
        default=None,
        description="Context packing diagnostics for the edit planning prompt.",
    )


class ScriptRepairRequest(BaseModel):
    script_yaml: str = Field(..., min_length=1, description="Rejected screenplay YAML content.")
    validation_report: ValidationReportResponse = Field(
        ...,
        description="Harness errors to repair.",
    )


class ScriptVersionResponse(BaseModel):
    id: str = Field(..., description="Script version identifier.")
    project_id: str = Field(..., description="Project identifier.")
    file_path: str = Field(..., description="Local YAML snapshot path.")
    created_by: str = Field(..., description="Version creator, such as agent or user.")
    reason: str = Field(..., description="Version creation reason.")
    operation_count: int = Field(..., description="Number of operations applied.")
    validation_status: str = Field(..., description="Validation status.")
    created_at: datetime = Field(..., description="Version creation time.")


class ScriptVersionListResponse(BaseModel):
    versions: list[ScriptVersionResponse] = Field(
        ...,
        description="Screenplay YAML versions, including accepted versions and rejected drafts.",
    )


class ScriptVersionDetailResponse(BaseModel):
    version: ScriptVersionResponse = Field(..., description="Script version metadata.")
    script_yaml: str = Field(..., description="Version YAML content.")


class ScriptRestoreResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    current_version_id: str = Field(..., description="Restored script version ID.")
    script_yaml: str = Field(..., description="Restored YAML content.")


class ScriptExportResponse(BaseModel):
    project_id: str = Field(..., description="Project identifier.")
    file_name: str = Field(..., description="Suggested export file name.")
    media_type: str = Field(..., description="Export media type.")
    content: str = Field(..., description="Export content.")
