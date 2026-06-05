from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScriptVersionRecord


class ScriptVersionRepository:
    """Persistence helper for accepted screenplay YAML versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, version: ScriptVersionRecord) -> ScriptVersionRecord:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get(self, project_id: str, version_id: str) -> ScriptVersionRecord | None:
        result = await self.session.execute(
            select(ScriptVersionRecord).where(
                ScriptVersionRecord.project_id == project_id,
                ScriptVersionRecord.id == version_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: str) -> list[ScriptVersionRecord]:
        result = await self.session.execute(
            select(ScriptVersionRecord)
            .where(ScriptVersionRecord.project_id == project_id)
            .order_by(ScriptVersionRecord.created_at.desc())
        )
        return list(result.scalars().all())

