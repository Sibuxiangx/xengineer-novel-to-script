from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChapterRecord


class ChapterRepository:
    """Persistence helper for imported chapter metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_project(self, project_id: str) -> list[ChapterRecord]:
        result = await self.session.execute(
            select(ChapterRecord)
            .where(ChapterRecord.project_id == project_id)
            .order_by(ChapterRecord.order_index)
        )
        return list(result.scalars().all())

    async def get(self, project_id: str, chapter_id: str) -> ChapterRecord | None:
        result = await self.session.execute(
            select(ChapterRecord).where(
                ChapterRecord.project_id == project_id,
                ChapterRecord.id == chapter_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_project(self, project_id: str) -> None:
        await self.session.execute(
            delete(ChapterRecord).where(ChapterRecord.project_id == project_id)
        )

    async def add_many(self, chapters: list[ChapterRecord]) -> list[ChapterRecord]:
        self.session.add_all(chapters)
        await self.session.flush()
        return chapters
