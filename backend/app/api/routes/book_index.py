from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import (
    AgentConfigurationError,
    AgentExecutionError,
    ScreenplayAgent,
)
from app.api.models.book_index import BookIndexBuildRequest, BookIndexResponse
from app.api.models.common import ApiErrorResponse
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.book_index_service import (
    BookIndexNotFoundError,
    BookIndexService,
    BookIndexServiceProjectNotFoundError,
)

router = APIRouter(prefix="/projects/{project_id}/book-index", tags=["book-index"])


def get_screenplay_agent(settings: Annotated[Settings, Depends(get_settings)]) -> ScreenplayAgent:
    return ScreenplayAgent(settings)


def get_book_index_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    agent: Annotated[ScreenplayAgent, Depends(get_screenplay_agent)],
) -> BookIndexService:
    return BookIndexService(session=session, settings=settings, agent=agent)


@router.post(
    "",
    response_model=BookIndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Build the book index",
    description=(
        "Use the configured Pydantic AI DeepSeek agent to build book_index.json from "
        "imported chapters and save it as a project artifact."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ApiErrorResponse},
    },
)
async def build_book_index(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: BookIndexBuildRequest,
    service: Annotated[BookIndexService, Depends(get_book_index_service)],
) -> BookIndexResponse:
    try:
        return await service.build_index(project_id, force_rebuild=request.force_rebuild)
    except BookIndexServiceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "project_not_found", "detail": "Project not found."},
        ) from exc
    except AgentConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_configuration_error", "detail": str(exc)},
        ) from exc
    except AgentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "agent_execution_error", "detail": str(exc)},
        ) from exc


@router.get(
    "",
    response_model=BookIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the book index",
    description="Return the saved book_index.json artifact for a project.",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorResponse},
    },
)
async def get_book_index(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[BookIndexService, Depends(get_book_index_service)],
) -> BookIndexResponse:
    try:
        return await service.get_index(project_id)
    except BookIndexServiceProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "project_not_found", "detail": "Project not found."},
        ) from exc
    except BookIndexNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "book_index_not_found", "detail": "Book index not found."},
        ) from exc
