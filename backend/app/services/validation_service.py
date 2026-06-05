from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    code: str = Field(..., description="Stable validation issue code.")
    severity: str = Field(..., description="Issue severity.")
    path: str = Field(..., description="YAML path associated with the issue.")
    message: str = Field(..., description="Human-readable validation message.")
    repair_hint: str | None = Field(default=None, description="Optional repair guidance.")


class ValidationReport(BaseModel):
    accepted: bool = Field(..., description="Whether the YAML can be accepted.")
    errors: list[ValidationIssue] = Field(default_factory=list, description="Blocking issues.")
    warnings: list[ValidationIssue] = Field(
        default_factory=list,
        description="Non-blocking issues.",
    )


class ValidationService:
    """Harness boundary for script YAML validation."""

    async def accept_empty_scaffold(self) -> ValidationReport:
        return ValidationReport(accepted=True)
