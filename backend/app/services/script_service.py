from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.scripts import ScriptValidateResponse
from app.core.config import Settings
from app.db.repositories.chapters import ChapterRepository
from app.db.repositories.projects import ProjectRepository
from app.schemas.book_index import BookIndex
from app.services.validation_service import ValidationService
from app.storage.project_store import ProjectStore


class ScriptServiceProjectNotFoundError(Exception):
    """Raised when a project does not exist for script operations."""


class ScriptService:
    """Application service for screenplay YAML validation and lifecycle operations."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.projects = ProjectRepository(session)
        self.chapters = ChapterRepository(session)
        self.store = ProjectStore(settings.local_artifact_root)
        self.validation = ValidationService()

    async def validate_script(self, project_id: str, script_yaml: str) -> ScriptValidateResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)

        chapters = await self.chapters.list_by_project(project_id)
        chapter_ids = {chapter.id for chapter in chapters}
        book_index = self._load_book_index(project_id)
        report = self.validation.validate_script_yaml(
            script_yaml=script_yaml,
            chapter_ids=chapter_ids,
            book_index=book_index,
        )
        return ScriptValidateResponse(
            project_id=project_id,
            validation_report=report.to_response(),
        )

    def _load_book_index(self, project_id: str) -> BookIndex | None:
        path = self.store.book_index_path(project_id)
        if not path.exists():
            return None
        return BookIndex.model_validate(self.store.read_json(path))

