from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.book_index import BookIndexResponse
from app.core.config import Settings
from app.db.repositories.chapters import ChapterRepository
from app.db.repositories.projects import ProjectRepository
from app.schemas.book_index import BookIndex
from app.services.context_prompt_builder import ContextPromptBuilder, PackedPrompt
from app.storage.project_store import ProjectStore

StreamDeltaCallback = Callable[[dict[str, Any]], Awaitable[None]]


class BookIndexNotFoundError(Exception):
    """Raised when a project has no generated book index."""


class BookIndexServiceProjectNotFoundError(Exception):
    """Raised when a project does not exist for book-index operations."""


class BookIndexService:
    """Service boundary for creating and reading book index artifacts."""

    def __init__(self, session: AsyncSession, settings: Settings, agent: ScreenplayAgent) -> None:
        self.session = session
        self.settings = settings
        self.agent = agent
        self.projects = ProjectRepository(session)
        self.chapters = ChapterRepository(session)
        self.store = ProjectStore(settings.local_artifact_root)
        self.context_prompts = ContextPromptBuilder(settings)

    async def build_index(
        self,
        project_id: str,
        force_rebuild: bool,
        stream_callback: StreamDeltaCallback | None = None,
    ) -> BookIndexResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise BookIndexServiceProjectNotFoundError(project_id)

        path = self.store.book_index_path(project_id)
        if path.exists() and not force_rebuild:
            book_index = BookIndex.model_validate(self.store.read_json(path))
            return self._response(project_id, path, book_index)

        chapters = await self.chapters.list_by_project(project_id)
        packed_prompt = self._build_prompt(
            project_title=project.title,
            project_id=project_id,
            chapters=[
                {
                    "id": chapter.id,
                    "title": chapter.title,
                    "order": chapter.order_index + 1,
                    "content": self.store.read_text(chapter.file_path),
                    "token_estimate": chapter.token_estimate,
                }
                for chapter in chapters
            ],
        )
        book_index = await self.agent.build_book_index(
            packed_prompt.prompt,
            stream_callback=stream_callback,
        )
        self.store.write_json(path, book_index.model_dump(mode="json"))
        return self._response(project_id, path, book_index, packed_prompt)

    async def get_index(self, project_id: str) -> BookIndexResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise BookIndexServiceProjectNotFoundError(project_id)

        path = self.store.book_index_path(project_id)
        if not path.exists():
            raise BookIndexNotFoundError(project_id)
        book_index = BookIndex.model_validate(self.store.read_json(path))
        return self._response(project_id, path, book_index)

    def _response(
        self,
        project_id: str,
        path: Path,
        book_index: BookIndex,
        packed_prompt: PackedPrompt | None = None,
    ) -> BookIndexResponse:
        return BookIndexResponse(
            project_id=project_id,
            book_index=book_index,
            file_path=str(path),
            context_report=packed_prompt.report if packed_prompt is not None else None,
        )

    def _build_prompt(
        self,
        project_title: str,
        project_id: str,
        chapters: list[dict],
    ) -> PackedPrompt:
        return self.context_prompts.build_book_index_prompt(
            project_title=project_title,
            project_id=project_id,
            chapters=chapters,
        )
