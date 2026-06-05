from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectRecord


class ProjectRepository:
    """Persistence helper for adaptation project metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, project_id: str) -> ProjectRecord | None:
        result = await self.session.execute(
            select(ProjectRecord).where(ProjectRecord.id == project_id)
        )
        return result.scalar_one_or_none()

    async def add(self, project: ProjectRecord) -> ProjectRecord:
        self.session.add(project)
        await self.session.flush()
        return project

