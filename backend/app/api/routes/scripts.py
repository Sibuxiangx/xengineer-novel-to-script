from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.common import ApiErrorResponse
from app.api.models.scripts import ScriptValidateRequest, ScriptValidateResponse
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.script_service import ScriptService, ScriptServiceProjectNotFoundError

router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])


def get_script_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScriptService:
    return ScriptService(session=session, settings=settings)


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
    request: ScriptValidateRequest,
    service: Annotated[ScriptService, Depends(get_script_service)],
) -> ScriptValidateResponse:
    try:
        return await service.validate_script(project_id, request.script_yaml)
    except ScriptServiceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "project_not_found", "detail": "Project not found."},
        ) from exc

