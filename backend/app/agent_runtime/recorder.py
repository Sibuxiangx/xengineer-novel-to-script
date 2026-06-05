from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ChatMessageRecord,
    ChatMessageRole,
    ChatRunRecord,
    ChatRunStatus,
    ChatSessionRecord,
    ChatToolCallRecord,
    ChatToolCallStatus,
)
from app.db.repositories.chat import ChatRepository


class ChatRunRecorder:
    """Persist chat run, message, and tool-call timeline records."""

    def __init__(self, session: AsyncSession, chat: ChatRepository) -> None:
        self.session = session
        self.chat = chat

    async def start_run(
        self,
        chat_session: ChatSessionRecord,
        user_content: str,
    ) -> tuple[ChatRunRecord, ChatMessageRecord]:
        user_message = await self.add_message(
            session_id=chat_session.id,
            role=ChatMessageRole.user,
            content=user_content,
            metadata=None,
        )
        run = ChatRunRecord(
            id=f"run_{uuid4().hex[:12]}",
            session_id=chat_session.id,
            status=ChatRunStatus.running.value,
            user_message_id=user_message.id,
        )
        await self.chat.add_run(run)
        await self.chat.touch_session(chat_session)
        await self.session.commit()
        return run, user_message

    async def complete_run(
        self,
        run: ChatRunRecord,
        chat_session: ChatSessionRecord,
        content: str,
    ) -> None:
        assistant = await self.add_message(
            session_id=chat_session.id,
            role=ChatMessageRole.assistant,
            content=content,
            metadata=None,
        )
        run.assistant_message_id = assistant.id
        run.status = ChatRunStatus.completed.value
        await self.chat.touch_session(chat_session)
        await self.session.commit()

    async def fail_run(self, run: ChatRunRecord, error_message: str) -> None:
        run.status = ChatRunStatus.failed.value
        run.error_message = error_message
        await self.session.commit()

    async def start_tool(
        self,
        chat_session: ChatSessionRecord,
        run: ChatRunRecord,
        name: str,
        input_json: dict[str, Any],
    ) -> ChatToolCallRecord:
        tool = ChatToolCallRecord(
            id=f"tool_{uuid4().hex[:12]}",
            session_id=chat_session.id,
            run_id=run.id,
            name=name,
            status=ChatToolCallStatus.running.value,
            input_json=input_json,
        )
        await self.chat.add_tool_call(tool)
        await self.session.commit()
        return tool

    async def complete_tool(
        self,
        tool: ChatToolCallRecord,
        output_json: dict[str, Any],
    ) -> None:
        tool.status = ChatToolCallStatus.completed.value
        tool.output_json = output_json
        await self.session.commit()

    async def fail_tool(
        self,
        tool: ChatToolCallRecord,
        error_message: str,
    ) -> None:
        tool.status = ChatToolCallStatus.failed.value
        tool.error_message = error_message
        await self.session.commit()

    async def add_message(
        self,
        session_id: str,
        role: ChatMessageRole,
        content: str,
        metadata: dict[str, Any] | None,
    ) -> ChatMessageRecord:
        message = ChatMessageRecord(
            id=f"msg_{uuid4().hex[:12]}",
            session_id=session_id,
            role=role.value,
            content=content,
            metadata_json=metadata,
        )
        await self.chat.add_message(message)
        return message
