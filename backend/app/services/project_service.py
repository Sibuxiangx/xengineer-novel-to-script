from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.projects import (
    ChapterResponse,
    ProjectCreateRequest,
    ProjectResponse,
    TxtEbookImportRequest,
    TxtEbookImportResponse,
)
from app.core.config import Settings
from app.db.models import ChapterRecord, ProjectRecord
from app.db.repositories.chapters import ChapterRepository
from app.db.repositories.projects import ProjectRepository
from app.services.chapter_splitter import ChapterSplitter
from app.services.token_counter import TokenCounter
from app.storage.project_store import ProjectStore


class ProjectNotFoundError(Exception):
    """Raised when a project does not exist."""


class ChapterNotFoundError(Exception):
    """Raised when a chapter does not exist."""


class EmptyChapterUpdateError(Exception):
    """Raised when a chapter update request contains no editable fields."""


class ProjectService:
    """Application service for project and chapter workflows."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.projects = ProjectRepository(session)
        self.chapters = ChapterRepository(session)
        self.store = ProjectStore(settings.local_artifact_root)
        self.splitter = ChapterSplitter()
        self.token_counter = TokenCounter()

    async def create_project(self, request: ProjectCreateRequest) -> ProjectResponse:
        project_id = f"proj_{uuid4().hex[:12]}"
        artifact_root = self.store.ensure_project_root(project_id)
        record = ProjectRecord(
            id=project_id,
            title=request.title,
            screenplay_format=request.screenplay_format,
            artifact_root=str(artifact_root),
        )
        await self.projects.add(record)
        await self.session.commit()
        return await self.get_project(project_id)

    async def get_project(self, project_id: str) -> ProjectResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        chapters = await self.chapters.list_by_project(project_id)
        return self._project_response(project, chapter_count=len(chapters))

    async def import_txt_ebook(
        self,
        project_id: str,
        request: TxtEbookImportRequest,
    ) -> TxtEbookImportResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        split_rule = request.chapter_split_rule if request.split_strategy == "custom_rule" else None
        detected = self.splitter.split(request.content, rule=split_rule)
        if request.replace_existing:
            await self.chapters.delete_by_project(project_id)
            self.store.clear_chapters(project_id)

        chapter_records: list[ChapterRecord] = []
        for order_index, chapter in enumerate(detected):
            chapter_id = f"{project_id}_chapter_{order_index + 1:03d}"
            path = self.store.write_chapter(
                project_id=project_id,
                order_index=order_index,
                chapter_id=chapter_id,
                content=chapter.content,
            )
            estimate = self.token_counter.estimate(chapter.content)
            chapter_records.append(
                ChapterRecord(
                    id=chapter_id,
                    project_id=project_id,
                    title=chapter.title,
                    order_index=order_index,
                    file_path=str(path),
                    token_estimate=estimate.estimated_tokens,
                )
            )

        await self.chapters.add_many(chapter_records)
        project.updated_at = datetime.now(UTC)
        await self.session.commit()
        refreshed_project = await self.get_project(project_id)
        saved_chapters = await self.list_chapters(project_id)
        return TxtEbookImportResponse(
            project=refreshed_project,
            chapters=saved_chapters,
            detected_chapter_count=len(saved_chapters),
            split_strategy=request.split_strategy,
        )

    async def list_chapters(self, project_id: str) -> list[ChapterResponse]:
        project = await self.projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        records = await self.chapters.list_by_project(project_id)
        return [self._chapter_response(record) for record in records]

    async def update_chapter(
        self,
        project_id: str,
        chapter_id: str,
        title: str | None,
        content: str | None,
    ) -> ChapterResponse:
        if title is None and content is None:
            raise EmptyChapterUpdateError(chapter_id)

        project = await self.projects.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)

        chapter = await self.chapters.get(project_id, chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(chapter_id)

        if title is not None:
            chapter.title = title
        if content is not None:
            self.store.write_text(chapter.file_path, content)
            chapter.token_estimate = self.token_counter.estimate(content).estimated_tokens

        project.updated_at = datetime.now(UTC)
        await self.session.commit()
        return self._chapter_response(chapter)

    def _project_response(self, project: ProjectRecord, chapter_count: int) -> ProjectResponse:
        return ProjectResponse(
            id=project.id,
            title=project.title,
            screenplay_format=project.screenplay_format,
            artifact_root=project.artifact_root,
            chapter_count=chapter_count,
            current_script_version_id=project.current_script_version_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _chapter_response(self, chapter: ChapterRecord) -> ChapterResponse:
        return ChapterResponse(
            id=chapter.id,
            project_id=chapter.project_id,
            title=chapter.title,
            order_index=chapter.order_index,
            content=self.store.read_text(Path(chapter.file_path)),
            file_path=chapter.file_path,
            token_estimate=chapter.token_estimate,
            created_at=chapter.created_at,
        )
