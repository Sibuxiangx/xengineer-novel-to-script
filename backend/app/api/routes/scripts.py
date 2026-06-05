from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import (
    AgentConfigurationError,
    AgentExecutionError,
    ScreenplayAgent,
)
from app.api.models.common import ApiErrorResponse
from app.api.models.scripts import (
    ScriptEditRequest,
    ScriptEditResponse,
    ScriptExportResponse,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
    ScriptRepairRequest,
    ScriptRestoreResponse,
    ScriptValidateRequest,
    ScriptValidateResponse,
    ScriptVersionDetailResponse,
    ScriptVersionListResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.script_service import (
    BookIndexRequiredError,
    CurrentScriptNotFoundError,
    ScriptService,
    ScriptServiceProjectNotFoundError,
    ScriptValidationRejectedError,
    ScriptVersionNotFoundError,
)

router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])


def get_script_agent(settings: Annotated[Settings, Depends(get_settings)]) -> ScreenplayAgent:
    return ScreenplayAgent(settings)


def get_script_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agent: Annotated[ScreenplayAgent, Depends(get_script_agent)],
) -> ScriptService:
    return ScriptService(session=session, settings=settings, agent=agent)


def _project_not_found(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "project_not_found", "detail": "Project not found."},
    )


def _agent_configuration_error(exc: AgentConfigurationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "agent_configuration_error", "detail": str(exc)},
    )


def _agent_execution_error(exc: AgentExecutionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": "agent_execution_error", "detail": str(exc)},
    )


@router.post(
    "/generate",
    response_model=ScriptGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate screenplay YAML",
    description=(
        "Generate script.yaml from imported chapters and the saved book_index.json, "
        "then run the validation harness before saving an accepted version."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def generate_script(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: Annotated[
        ScriptGenerateRequest,
        Body(description="Script generation request options."),
    ],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptGenerateResponse:
    try:
        return await service.generate_script(project_id, force_regenerate=request.force_regenerate)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except BookIndexRequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "book_index_required",
                "detail": "Build book_index.json before generating script.yaml.",
            },
        ) from exc
    except AgentConfigurationError as exc:
        raise _agent_configuration_error(exc) from exc
    except AgentExecutionError as exc:
        raise _agent_execution_error(exc) from exc


@router.post(
    "/validate",
    response_model=ScriptValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate screenplay YAML",
    description=(
        "Run the screenplay validation harness against submitted YAML using the project chapters "
        "and saved book_index.json when available."
    ),
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def validate_script(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: Annotated[
        ScriptValidateRequest,
        Body(description="Screenplay YAML validation request."),
    ],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptValidateResponse:
    try:
        return await service.validate_script(project_id, request.script_yaml)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc


@router.post(
    "/edit",
    response_model=ScriptEditResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit screenplay YAML",
    description=(
        "Ask the agent to create structured YAML edit operations, apply them to the current "
        "script.yaml, and save a new version only when the validation harness accepts it."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def edit_script(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: Annotated[
        ScriptEditRequest,
        Body(description="Natural-language edit instruction and optional YAML target path."),
    ],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptEditResponse:
    try:
        return await service.edit_script(
            project_id=project_id,
            instruction=request.instruction,
            target_path=request.target_path,
        )
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except CurrentScriptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "current_script_not_found", "detail": "Current script.yaml not found."},
        ) from exc
    except ScriptValidationRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "script_patch_rejected", "detail": str(exc)},
        ) from exc
    except AgentConfigurationError as exc:
        raise _agent_configuration_error(exc) from exc
    except AgentExecutionError as exc:
        raise _agent_execution_error(exc) from exc


@router.post(
    "/repair",
    response_model=ScriptGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="Repair rejected screenplay YAML",
    description=(
        "Repair a rejected screenplay YAML document from a validation report, run the harness "
        "again, and save a new accepted version only when validation passes."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def repair_script(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: Annotated[
        ScriptRepairRequest,
        Body(description="Rejected YAML and validation report used by the repair agent."),
    ],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptGenerateResponse:
    try:
        return await service.repair_script(
            project_id=project_id,
            script_yaml=request.script_yaml,
            validation_report_json=request.validation_report.model_dump(mode="json"),
        )
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except AgentConfigurationError as exc:
        raise _agent_configuration_error(exc) from exc
    except AgentExecutionError as exc:
        raise _agent_execution_error(exc) from exc


@router.get(
    "/versions",
    response_model=ScriptVersionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List accepted screenplay versions",
    description="List accepted script.yaml snapshots for a project.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def list_script_versions(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptVersionListResponse:
    try:
        return await service.list_versions(project_id)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc


@router.get(
    "/versions/{version_id}",
    response_model=ScriptVersionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an accepted screenplay version",
    description="Return metadata and YAML content for one accepted script.yaml snapshot.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def get_script_version(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    version_id: Annotated[str, Path(description="Stable script version identifier.")],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptVersionDetailResponse:
    try:
        return await service.get_version(project_id, version_id)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "script_version_not_found", "detail": "Script version not found."},
        ) from exc


@router.post(
    "/versions/{version_id}/restore",
    response_model=ScriptRestoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore an accepted screenplay version",
    description="Restore one accepted script.yaml snapshot as the project's current script.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def restore_script_version(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    version_id: Annotated[str, Path(description="Stable script version identifier.")],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptRestoreResponse:
    try:
        return await service.restore_version(project_id, version_id)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except ScriptVersionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "script_version_not_found", "detail": "Script version not found."},
        ) from exc


@router.get(
    "/exports/script.yaml",
    response_model=ScriptExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export the current screenplay YAML",
    description="Return the current accepted script.yaml content as an export payload.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def export_script_yaml(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptExportResponse:
    try:
        return await service.export_script_yaml(project_id)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
    except CurrentScriptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "current_script_not_found", "detail": "Current script.yaml not found."},
        ) from exc


@router.get(
    "/exports/screenplay-schema.json",
    response_model=ScriptExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export the screenplay JSON Schema",
    description="Return the JSON Schema behind script.yaml for README and evaluator reference.",
    responses={status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse}},
)
async def export_schema_json(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptExportResponse:
    try:
        return await service.export_schema_json(project_id)
    except ScriptServiceProjectNotFoundError as exc:
        raise _project_not_found(exc) from exc
