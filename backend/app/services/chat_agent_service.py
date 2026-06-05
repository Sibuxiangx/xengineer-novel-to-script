from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.chat_toolbox import ChatToolbox
from app.agent_runtime.events import format_sse_event
from app.agent_runtime.recorder import ChatRunRecorder
from app.agents.deps import AgentDeps
from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.book_index import BookIndexResponse
from app.api.models.chat import (
    ChapterSplitConfirmationPayload,
    ChatConfirmationActionRequest,
    ChatConfirmationResponse,
    ChatMessageResponse,
    ChatRunStreamRequest,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatToolCallResponse,
)
from app.api.models.projects import (
    ChapterListResponse,
)
from app.api.models.scripts import ScriptVersionDetailResponse, ScriptVersionListResponse
from app.core.config import Settings
from app.db.models import (
    ChatConfirmationRecord,
    ChatConfirmationStatus,
    ChatMessageRecord,
    ChatRunRecord,
    ChatSessionRecord,
    ChatSessionStatus,
    ChatToolCallRecord,
)
from app.db.repositories.chat import ChatRepository
from app.db.repositories.script_versions import ScriptVersionRepository
from app.schemas.chapter_split import ChapterSplitRule
from app.services.book_index_service import (
    BookIndexNotFoundError,
    BookIndexService,
    BookIndexServiceProjectNotFoundError,
)
from app.services.project_service import ProjectNotFoundError, ProjectService
from app.services.script_service import (
    ScriptService,
    ScriptServiceProjectNotFoundError,
    ScriptVersionNotFoundError,
)


class ChatSessionNotFoundError(Exception):
    """Raised when a chat session does not exist."""


class ChatConfirmationNotFoundError(Exception):
    """Raised when a confirmation does not exist."""


class ChatConfirmationStateError(Exception):
    """Raised when a confirmation cannot be applied."""


class ChatSessionProjectRequiredError(Exception):
    """Raised when a chat-scoped asset request has no linked project yet."""


class ChatAssetNotFoundError(Exception):
    """Raised when a chat-scoped project artifact is not available yet."""


class ChatScriptVersionNotFoundError(Exception):
    """Raised when a chat-scoped screenplay version cannot be found."""


class ChatAgentService:
    """Agentic chat orchestration for the novel-to-screenplay product."""

    def __init__(self, session: AsyncSession, settings: Settings, agent: ScreenplayAgent) -> None:
        self.session = session
        self.settings = settings
        self.agent = agent
        self.chat = ChatRepository(session)
        self.recorder = ChatRunRecorder(session=session, chat=self.chat)
        self.versions = ScriptVersionRepository(session)

    async def create_session(self, request: ChatSessionCreateRequest) -> ChatSessionResponse:
        record = ChatSessionRecord(
            id=f"chat_{uuid4().hex[:12]}",
            title=request.title or "新的改编对话",
            status=ChatSessionStatus.active.value,
        )
        await self.chat.add_session(record)
        await self.session.commit()
        return await self._session_response(record)

    async def list_sessions(self) -> list[ChatSessionResponse]:
        sessions = await self.chat.list_sessions()
        return [await self._session_response(session) for session in sessions]

    async def get_session_detail(self, session_id: str) -> ChatSessionDetailResponse:
        session = await self._require_session(session_id)
        messages = await self.chat.list_messages(session_id)
        confirmations = await self.chat.list_pending_confirmations(session_id)
        latest_versions = []
        if session.project_id is not None:
            latest_versions = [
                ScriptService(
                    session=self.session,
                    settings=self.settings,
                    agent=self.agent,
                )._version_response(version)
                for version in await self.versions.list_by_project(session.project_id)
            ]
        return ChatSessionDetailResponse(
            session=await self._session_response(session),
            messages=[self._message_response(message) for message in messages],
            pending_confirmations=[
                self._confirmation_response(confirmation) for confirmation in confirmations
            ],
            latest_versions=latest_versions[-5:],
        )

    async def list_session_chapters(self, session_id: str) -> ChapterListResponse:
        project_id = await self._require_session_project_id(session_id)
        try:
            chapters = await ProjectService(self.session, self.settings).list_chapters(project_id)
        except ProjectNotFoundError as exc:
            raise ChatSessionProjectRequiredError(session_id) from exc
        return ChapterListResponse(chapters=chapters)

    async def get_session_book_index(self, session_id: str) -> BookIndexResponse:
        project_id = await self._require_session_project_id(session_id)
        try:
            return await BookIndexService(
                self.session,
                self.settings,
                self.agent,
            ).get_index(project_id)
        except BookIndexServiceProjectNotFoundError as exc:
            raise ChatSessionProjectRequiredError(session_id) from exc
        except BookIndexNotFoundError as exc:
            raise ChatAssetNotFoundError(session_id) from exc

    async def list_session_script_versions(self, session_id: str) -> ScriptVersionListResponse:
        project_id = await self._require_session_project_id(session_id)
        try:
            return await ScriptService(
                self.session,
                self.settings,
                self.agent,
            ).list_versions(project_id)
        except ScriptServiceProjectNotFoundError as exc:
            raise ChatSessionProjectRequiredError(session_id) from exc

    async def get_session_script_version(
        self,
        session_id: str,
        version_id: str,
    ) -> ScriptVersionDetailResponse:
        project_id = await self._require_session_project_id(session_id)
        try:
            return await ScriptService(
                self.session,
                self.settings,
                self.agent,
            ).get_version(project_id, version_id)
        except ScriptServiceProjectNotFoundError as exc:
            raise ChatSessionProjectRequiredError(session_id) from exc
        except ScriptVersionNotFoundError as exc:
            raise ChatScriptVersionNotFoundError(version_id) from exc

    async def stream_user_message(
        self,
        session_id: str,
        request: ChatRunStreamRequest,
    ) -> AsyncIterator[str]:
        session = await self._require_session(session_id)
        run, user_message = await self.recorder.start_run(session, request.message)
        yield self._event(
            "run.started",
            {"run_id": run.id, "session_id": session.id, "user_message_id": user_message.id},
        )

        try:
            if request.source_text:
                async for event in self._stream_source_ingestion(session, run, request):
                    yield event
            else:
                async for event in self._stream_chat_instruction(session, run, request.message):
                    yield event
        except Exception as exc:
            await self.recorder.fail_run(run, str(exc))
            yield self._event(
                "error",
                {
                    "run_id": run.id,
                    "message": str(exc),
                },
            )

    async def stream_confirmation_action(
        self,
        session_id: str,
        confirmation_id: str,
        request: ChatConfirmationActionRequest,
    ) -> AsyncIterator[str]:
        session = await self._require_session(session_id)
        confirmation = await self.chat.get_confirmation(session_id, confirmation_id)
        if confirmation is None:
            raise ChatConfirmationNotFoundError(confirmation_id)
        if confirmation.status != ChatConfirmationStatus.pending.value:
            raise ChatConfirmationStateError("Confirmation is not pending.")

        run, user_message = await self.recorder.start_run(
            session,
            request.message or ("确认分章" if request.action == "confirm" else "取消分章"),
        )
        yield self._event(
            "run.started",
            {"run_id": run.id, "session_id": session.id, "user_message_id": user_message.id},
        )

        try:
            if request.action == "cancel":
                confirmation.status = ChatConfirmationStatus.cancelled.value
                confirmation.resolved_at = datetime.now(UTC)
                await self.recorder.complete_run(
                    run=run,
                    chat_session=session,
                    content="已取消这次分章确认。你可以重新上传文本，或继续说明希望怎样调整。",
                )
                yield self._event(
                    "tool.confirm.cancelled",
                    {"confirmation_id": confirmation.id, "kind": confirmation.kind},
                )
                yield self._event("run.completed", {"run_id": run.id})
                return

            async for event in self._stream_chapter_split_confirmation(
                session=session,
                run=run,
                confirmation=confirmation,
                edited_rule=request.chapter_split_rule,
            ):
                yield event
        except Exception as exc:
            await self.recorder.fail_run(run, str(exc))
            yield self._event("error", {"run_id": run.id, "message": str(exc)})

    async def _stream_source_ingestion(
        self,
        session: ChatSessionRecord,
        run: ChatRunRecord,
        request: ChatRunStreamRequest,
    ) -> AsyncIterator[str]:
        yield self._event("message.delta", {"content": "已收到小说文本，开始识别项目与分章方式。"})
        toolbox = self._create_toolbox(
            session=session,
            run=run,
            source_file_name=request.source_file_name,
            source_text=request.source_text,
            screenplay_format=request.screenplay_format,
        )
        deps = AgentDeps(
            settings=self.settings,
            session_id=session.id,
            project_id=session.project_id,
            toolbox=toolbox,
        )
        try:
            await self.agent.run_source_ingestion_tools(
                self._source_ingestion_prompt(request),
                deps=deps,
            )
        except Exception:
            for event in toolbox.events:
                yield event
            raise
        if toolbox.pending_confirmation_id is None:
            raise RuntimeError("Agent did not create the required chapter split confirmation.")
        for event in toolbox.events:
            yield event

    async def _stream_chat_instruction(
        self,
        session: ChatSessionRecord,
        run: ChatRunRecord,
        message: str,
    ) -> AsyncIterator[str]:
        pending = await self.chat.list_pending_confirmations(session.id)
        if pending:
            confirmation = pending[-1]
            content = "当前正在等待你确认分章。你可以确认、取消，或在确认前手动调整分章规则。"
            await self.recorder.complete_run(run=run, chat_session=session, content=content)
            yield self._event(
                "tool.confirm.required",
                self._confirmation_response(confirmation).model_dump(mode="json"),
            )
            yield self._event("message.delta", {"content": content})
            yield self._event("run.completed", {"run_id": run.id})
            return

        if session.project_id is None:
            content = "请先上传或粘贴小说 TXT，我会从文本开始建立改编项目。"
            await self.recorder.complete_run(run=run, chat_session=session, content=content)
            yield self._event("message.delta", {"content": content})
            yield self._event("run.completed", {"run_id": run.id})
            return

        toolbox = self._create_toolbox(session=session, run=run)
        deps = AgentDeps(
            settings=self.settings,
            session_id=session.id,
            project_id=session.project_id,
            toolbox=toolbox,
        )
        try:
            response = await self.agent.run_chat_instruction_tools(
                self._chat_instruction_prompt(message, session.project_id),
                deps=deps,
            )
        except Exception:
            for event in toolbox.events:
                yield event
            raise
        for event in toolbox.events:
            yield event
        if toolbox.completed_with_errors:
            content = toolbox.last_validation_error_message or (
                "操作已执行，但剧本 YAML 未通过 harness，当前结果已保存为 rejected draft。"
            )
            await self.recorder.complete_run_with_errors(
                run=run,
                chat_session=session,
                content=content,
                error_message=content,
            )
            yield self._event("message.delta", {"content": content})
            yield self._event(
                "run.completed_with_errors",
                {
                    "run_id": run.id,
                    "message": content,
                    "rejected_version_id": toolbox.last_rejected_version_id,
                    "repair_attempt_count": toolbox.last_repair_attempt_count,
                },
            )
            return
        await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content=response or "已根据你的说明处理当前项目。",
        )
        yield self._event("run.completed", {"run_id": run.id})

    async def _stream_chapter_split_confirmation(
        self,
        session: ChatSessionRecord,
        run: ChatRunRecord,
        confirmation: ChatConfirmationRecord,
        edited_rule: ChapterSplitRule | None,
    ) -> AsyncIterator[str]:
        payload = ChapterSplitConfirmationPayload.model_validate(confirmation.payload_json)
        rule = edited_rule or payload.rule
        project_id = confirmation.project_id
        if project_id is None:
            raise ChatConfirmationStateError("Chapter split confirmation has no project_id.")

        toolbox = self._create_toolbox(session=session, run=run)
        try:
            await toolbox.import_chapters(confirmation=confirmation, rule=rule)
        except Exception:
            for event in toolbox.events:
                yield event
            raise
        for event in toolbox.events:
            yield event
        event_offset = len(toolbox.events)

        try:
            await toolbox.build_book_index(project_id, force_rebuild=True)
        except Exception:
            for event in toolbox.events[event_offset:]:
                yield event
            raise
        for event in toolbox.events[event_offset:]:
            yield event
        event_offset = len(toolbox.events)

        try:
            await toolbox.generate_script_yaml(project_id, force_regenerate=True)
        except Exception:
            for event in toolbox.events[event_offset:]:
                yield event
            raise
        for event in toolbox.events[event_offset:]:
            yield event
        if toolbox.completed_with_errors:
            content = toolbox.last_validation_error_message or (
                "分章已确认，剧情索引已生成，但剧本 YAML 未通过 harness，"
                "当前结果已保存为 rejected draft。"
            )
            await self.recorder.complete_run_with_errors(
                run=run,
                chat_session=session,
                content=content,
                error_message=content,
            )
            yield self._event("message.delta", {"content": content})
            yield self._event(
                "run.completed_with_errors",
                {
                    "run_id": run.id,
                    "message": content,
                    "rejected_version_id": toolbox.last_rejected_version_id,
                    "repair_attempt_count": toolbox.last_repair_attempt_count,
                },
            )
            return
        await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content=(
                "分章已确认，剧情索引和剧本 YAML 已生成。"
                "你现在可以直接用自然语言继续要求我修改剧本。"
            ),
        )
        yield self._event("run.completed", {"run_id": run.id})

    async def _require_session(self, session_id: str) -> ChatSessionRecord:
        session = await self.chat.get_session(session_id)
        if session is None:
            raise ChatSessionNotFoundError(session_id)
        return session

    async def _require_session_project_id(self, session_id: str) -> str:
        session = await self._require_session(session_id)
        if session.project_id is None:
            raise ChatSessionProjectRequiredError(session_id)
        return session.project_id

    async def _session_response(self, record: ChatSessionRecord) -> ChatSessionResponse:
        pending = await self.chat.list_pending_confirmations(record.id)
        return ChatSessionResponse(
            id=record.id,
            project_id=record.project_id,
            title=record.title,
            status=cast(Literal["active", "archived"], record.status),
            pending_confirmation_count=len(pending),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _message_response(self, record: ChatMessageRecord) -> ChatMessageResponse:
        return ChatMessageResponse(
            id=record.id,
            session_id=record.session_id,
            role=cast(Literal["user", "assistant", "system", "tool"], record.role),
            content=record.content,
            metadata=record.metadata_json,
            created_at=record.created_at,
        )

    def _tool_response(self, record: ChatToolCallRecord) -> ChatToolCallResponse:
        return ChatToolCallResponse(
            id=record.id,
            session_id=record.session_id,
            run_id=record.run_id,
            name=record.name,
            status=cast(Literal["running", "completed", "failed"], record.status),
            input=record.input_json,
            output=record.output_json,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _confirmation_response(
        self,
        record: ChatConfirmationRecord,
    ) -> ChatConfirmationResponse:
        return ChatConfirmationResponse(
            id=record.id,
            session_id=record.session_id,
            project_id=record.project_id,
            kind=cast(Literal["chapter_split"], record.kind),
            status=cast(Literal["pending", "confirmed", "cancelled"], record.status),
            prompt=record.prompt,
            payload=ChapterSplitConfirmationPayload.model_validate(record.payload_json),
            created_at=record.created_at,
            resolved_at=record.resolved_at,
        )

    def _create_toolbox(
        self,
        session: ChatSessionRecord,
        run: ChatRunRecord,
        source_file_name: str | None = None,
        source_text: str | None = None,
        screenplay_format: str = "short_drama",
    ) -> ChatToolbox:
        return ChatToolbox(
            db_session=self.session,
            settings=self.settings,
            agent=self.agent,
            chat=self.chat,
            recorder=self.recorder,
            chat_session=session,
            run=run,
            source_file_name=source_file_name,
            source_text=source_text,
            screenplay_format=screenplay_format,
        )

    def _source_ingestion_prompt(self, request: ChatRunStreamRequest) -> str:
        file_name = request.source_file_name or "novel.txt"
        source_text = request.source_text or ""
        return "\n".join(
            [
                "用户上传了小说 TXT 原文，请按工具编排要求完成项目创建和分章确认。",
                f"用户消息：{request.message}",
                f"文件名：{file_name}",
                f"全文字符数：{len(source_text)}",
                f"目标剧本格式：{request.screenplay_format}",
            ]
        )

    def _chat_instruction_prompt(self, message: str, project_id: str) -> str:
        return "\n".join(
            [
                "用户正在和已有小说改编项目对话，请根据意图选择合适工具。",
                f"项目 ID：{project_id}",
                f"用户消息：{message}",
            ]
        )

    def _event(self, name: str, data: dict[str, Any]) -> str:
        return format_sse_event(name, data)
