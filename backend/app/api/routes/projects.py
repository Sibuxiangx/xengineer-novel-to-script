from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.projects import (
    ChapterListResponse,
    ChapterResponse,
    ChapterUpdateRequest,
    ProjectCreateRequest,
    ProjectResponse,
    TxtEbookImportRequest,
    TxtEbookImportResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.project_service import (
    ChapterNotFoundError,
    EmptyChapterUpdateError,
    ProjectNotFoundError,
    ProjectService,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectService:
    return ProjectService(session=session, settings=settings)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an adaptation project",
    description="Create a local novel-to-script project and initialize its artifact directory.",
)
async def create_project(
    request: ProjectCreateRequest,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    return await service.create_project(request)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project metadata",
    description="Return project metadata and current imported chapter count.",
)
async def get_project(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ProjectResponse:
    try:
        return await service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc


@router.post(
    "/{project_id}/ebook/import-txt",
    response_model=TxtEbookImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a TXT ebook",
    description=(
        "Import TXT ebook content, automatically split chapters, save chapter text files, "
        "and replace existing imported chapters by default."
    ),
)
async def import_txt_ebook(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    request: TxtEbookImportRequest,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> TxtEbookImportResponse:
    try:
        return await service.import_txt_ebook(project_id, request)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc


@router.get(
    "/{project_id}/chapters",
    response_model=ChapterListResponse,
    status_code=status.HTTP_200_OK,
    summary="List imported chapters",
    description="Return editable imported chapter contents in detected order.",
)
async def list_chapters(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ChapterListResponse:
    try:
        return ChapterListResponse(chapters=await service.list_chapters(project_id))
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc


@router.patch(
    "/{project_id}/chapters/{chapter_id}",
    response_model=ChapterResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit an imported chapter",
    description="Update a chapter title, chapter content, or both after automatic TXT splitting.",
)
async def update_chapter(
    project_id: Annotated[str, Path(description="Stable project identifier.")],
    chapter_id: Annotated[str, Path(description="Stable chapter identifier.")],
    request: ChapterUpdateRequest,
    service: Annotated[ProjectService, Depends(get_project_service)],
) -> ChapterResponse:
    try:
        return await service.update_chapter(
            project_id=project_id,
            chapter_id=chapter_id,
            title=request.title,
            content=request.content,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        ) from exc
    except ChapterNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found.",
        ) from exc
    except EmptyChapterUpdateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of title or content must be provided.",
        ) from exc
