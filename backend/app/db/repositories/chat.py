from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ChatConfirmationRecord,
    ChatMessageRecord,
    ChatRunRecord,
    ChatSessionRecord,
    ChatToolCallRecord,
)


class ChatRepository:
    """Persistence helper for chat sessions, runs, tool calls, and confirmations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_session(self, record: ChatSessionRecord) -> ChatSessionRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_sessions(self) -> list[ChatSessionRecord]:
        result = await self.session.execute(
            select(ChatSessionRecord).order_by(ChatSessionRecord.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_session(self, session_id: str) -> ChatSessionRecord | None:
        result = await self.session.execute(
            select(ChatSessionRecord).where(ChatSessionRecord.id == session_id)
        )
        return result.scalar_one_or_none()

    async def add_message(self, record: ChatMessageRecord) -> ChatMessageRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_messages(self, session_id: str) -> list[ChatMessageRecord]:
        result = await self.session.execute(
            select(ChatMessageRecord)
            .where(ChatMessageRecord.session_id == session_id)
            .order_by(ChatMessageRecord.created_at)
        )
        return list(result.scalars().all())

    async def add_run(self, record: ChatRunRecord) -> ChatRunRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def add_tool_call(self, record: ChatToolCallRecord) -> ChatToolCallRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def add_confirmation(self, record: ChatConfirmationRecord) -> ChatConfirmationRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
    ) -> ChatConfirmationRecord | None:
        result = await self.session.execute(
            select(ChatConfirmationRecord).where(
                ChatConfirmationRecord.session_id == session_id,
                ChatConfirmationRecord.id == confirmation_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_confirmations(
        self,
        session_id: str,
    ) -> list[ChatConfirmationRecord]:
        result = await self.session.execute(
            select(ChatConfirmationRecord)
            .where(
                ChatConfirmationRecord.session_id == session_id,
                ChatConfirmationRecord.status == "pending",
            )
            .order_by(ChatConfirmationRecord.created_at)
        )
        return list(result.scalars().all())

    async def touch_session(self, session: ChatSessionRecord) -> None:
        session.updated_at = datetime.now(UTC)
        await self.session.flush()
