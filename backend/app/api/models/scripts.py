from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.models.common import ValidationReportResponse


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


class YamlPatchOperation(BaseModel):
    type: Literal[
        "replace_script",
        "patch_scene",
        "replace_scene",
        "insert_event",
        "patch_event",
        "delete_event",
        "repair_validation_errors",
    ] = Field(..., description="Structured YAML operation type.")
    target_path: str = Field(..., description="Stable target path such as scenes.scene_001.")
    reason: str = Field(..., description="Chinese explanation for why this operation is needed.")
    payload: dict = Field(default_factory=dict, description="Operation payload.")


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
    versions: list[ScriptVersionResponse] = Field(..., description="Accepted script versions.")
