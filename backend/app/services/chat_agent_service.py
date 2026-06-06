from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
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
    ChatRunResponse,
    ChatRunStreamRequest,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    ChatTimelineItemResponse,
    ChatToolCallResponse,
)
from app.api.models.projects import (
    ChapterListResponse,
)
from app.api.models.scripts import (
    ScriptUserEditResponse,
    ScriptVersionDetailResponse,
    ScriptVersionListResponse,
)
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


@dataclass(slots=True)
class ObservedResult:
    value: Any


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

    _TIMELINE_HIDDEN_TOOL_NAMES = frozenset({"request_chapter_split_confirmation"})

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

    async def list_sessions(self, *, include_archived: bool = False) -> list[ChatSessionResponse]:
        sessions = await self.chat.list_sessions(include_archived=include_archived)
        return [await self._session_response(session) for session in sessions]

    async def archive_session(self, session_id: str) -> ChatSessionResponse:
        session = await self._require_session(session_id)
        await self.chat.archive_session(session)
        await self.session.commit()
        return await self._session_response(session)

    async def restore_session(self, session_id: str) -> ChatSessionResponse:
        session = await self._require_session(session_id)
        await self.chat.restore_session(session)
        await self.session.commit()
        return await self._session_response(session)

    async def get_session_detail(self, session_id: str) -> ChatSessionDetailResponse:
        session = await self._require_session(session_id)
        messages = await self.chat.list_messages(session_id)
        pending_confirmations = await self.chat.list_pending_confirmations(session_id)
        confirmations = await self.chat.list_confirmations(session_id)
        runs = await self.chat.list_runs(session_id)
        tool_calls = await self.chat.list_tool_calls(session_id)
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
                self._confirmation_response(confirmation) for confirmation in pending_confirmations
            ],
            runs=[self._run_response(run) for run in runs],
            tool_calls=[self._tool_response(call) for call in tool_calls],
            timeline=self._build_timeline(
                messages=messages,
                runs=runs,
                tool_calls=tool_calls,
                confirmations=confirmations,
            ),
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

    async def save_session_script_yaml(
        self,
        session_id: str,
        script_yaml: str,
        reason: str | None,
    ) -> ScriptUserEditResponse:
        project_id = await self._require_session_project_id(session_id)
        try:
            return await ScriptService(
                self.session,
                self.settings,
                self.agent,
            ).save_user_edit(project_id, script_yaml, reason)
        except ScriptServiceProjectNotFoundError as exc:
            raise ChatSessionProjectRequiredError(session_id) from exc

    async def stream_user_message(
        self,
        session_id: str,
        request: ChatRunStreamRequest,
    ) -> AsyncIterator[str]:
        session = await self._require_session(session_id)
        run, user_message = await self.recorder.start_run(
            session,
            request.message,
            user_metadata=self._source_attachment_metadata(request),
        )
        yield self._event(
            "run.started",
            {
                "run_id": run.id,
                "session_id": session.id,
                "user_message_id": user_message.id,
                "user_message": self._message_response(user_message).model_dump(mode="json"),
            },
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
            {
                "run_id": run.id,
                "session_id": session.id,
                "user_message_id": user_message.id,
                "user_message": self._message_response(user_message).model_dump(mode="json"),
                "confirmation_id": confirmation.id,
                "confirmation_action": request.action,
            },
        )

        try:
            if request.action == "cancel":
                confirmation.status = ChatConfirmationStatus.cancelled.value
                confirmation.resolved_at = datetime.now(UTC)
                assistant = await self.recorder.complete_run(
                    run=run,
                    chat_session=session,
                    content="已取消这次分章确认。你可以重新上传文本，或继续说明希望怎样调整。",
                )
                yield self._message_created_event(assistant, run.id)
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
            async for observed in self._observe_awaitable(
                self.agent.run_source_ingestion_tools(
                    self._source_ingestion_prompt(request),
                    deps=deps,
                ),
                run_id=run.id,
                stage="source_ingestion_agent",
                toolbox=toolbox,
            ):
                if isinstance(observed, ObservedResult):
                    continue
                yield observed
        except Exception:
            async for event in self._drain_toolbox_events(toolbox):
                yield event
            raise
        if toolbox.pending_confirmation_id is None:
            raise RuntimeError("Agent did not create the required chapter split confirmation.")
        async for event in self._drain_toolbox_events(toolbox):
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
            assistant = await self.recorder.complete_run(
                run=run,
                chat_session=session,
                content=content,
            )
            yield self._event(
                "tool.confirm.required",
                self._confirmation_response(confirmation).model_dump(mode="json"),
            )
            yield self._message_created_event(assistant, run.id)
            yield self._event("run.completed", {"run_id": run.id})
            return

        if session.project_id is None:
            content = "请先上传或粘贴小说 TXT，我会从文本开始建立改编项目。"
            assistant = await self.recorder.complete_run(
                run=run,
                chat_session=session,
                content=content,
            )
            yield self._message_created_event(assistant, run.id)
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
            response = "已根据你的说明处理当前项目。"
            async for observed in self._observe_awaitable(
                self.agent.run_chat_instruction_tools(
                    self._chat_instruction_prompt(message, session.project_id),
                    deps=deps,
                ),
                run_id=run.id,
                stage="chat_instruction_agent",
                toolbox=toolbox,
            ):
                if isinstance(observed, ObservedResult):
                    response = cast(str, observed.value)
                    continue
                yield observed
        except Exception:
            async for event in self._drain_toolbox_events(toolbox):
                yield event
            raise
        async for event in self._drain_toolbox_events(toolbox):
            yield event
        if toolbox.completed_with_errors:
            content = toolbox.last_validation_error_message or (
                "操作已执行，但剧本 YAML 未通过验证，当前结果已保存为 rejected draft。"
            )
            assistant = await self.recorder.complete_run_with_errors(
                run=run,
                chat_session=session,
                content=content,
                error_message=content,
            )
            yield self._message_created_event(assistant, run.id)
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
        assistant = await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content=response or "已根据你的说明处理当前项目。",
        )
        yield self._message_created_event(assistant, run.id)
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
            async for observed in self._observe_awaitable(
                toolbox.import_chapters(confirmation=confirmation, rule=rule),
                run_id=run.id,
                stage="import_chapters",
                toolbox=toolbox,
            ):
                if isinstance(observed, ObservedResult):
                    continue
                yield observed
        except Exception:
            async for event in self._drain_toolbox_events(toolbox):
                yield event
            raise
        async for event in self._drain_toolbox_events(toolbox):
            yield event

        try:
            async for observed in self._observe_awaitable(
                toolbox.build_book_index(project_id, force_rebuild=True),
                run_id=run.id,
                stage="build_book_index",
                toolbox=toolbox,
            ):
                if isinstance(observed, ObservedResult):
                    continue
                yield observed
        except Exception:
            async for event in self._drain_toolbox_events(toolbox):
                yield event
            raise
        async for event in self._drain_toolbox_events(toolbox):
            yield event

        try:
            async for observed in self._observe_awaitable(
                toolbox.generate_script_yaml(project_id, force_regenerate=True),
                run_id=run.id,
                stage="generate_script_yaml",
                toolbox=toolbox,
            ):
                if isinstance(observed, ObservedResult):
                    continue
                yield observed
        except Exception:
            async for event in self._drain_toolbox_events(toolbox):
                yield event
            raise
        async for event in self._drain_toolbox_events(toolbox):
            yield event
        if toolbox.completed_with_errors:
            content = toolbox.last_validation_error_message or (
                "分章已确认，剧情索引已生成，但剧本 YAML 未通过验证，"
                "当前结果已保存为 rejected draft。"
            )
            assistant = await self.recorder.complete_run_with_errors(
                run=run,
                chat_session=session,
                content=content,
                error_message=content,
            )
            yield self._message_created_event(assistant, run.id)
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
        assistant = await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content=(
                "分章已确认，剧情索引和剧本 YAML 已生成。"
                "你现在可以直接用自然语言继续要求我修改剧本。"
            ),
        )
        yield self._message_created_event(assistant, run.id)
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

    def _run_response(self, record: ChatRunRecord) -> ChatRunResponse:
        return ChatRunResponse(
            id=record.id,
            session_id=record.session_id,
            status=cast(
                Literal[
                    "running",
                    "waiting_confirmation",
                    "completed",
                    "completed_with_errors",
                    "failed",
                ],
                record.status,
            ),
            user_message_id=record.user_message_id,
            assistant_message_id=record.assistant_message_id,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _tool_response(self, record: ChatToolCallRecord) -> ChatToolCallResponse:
        duration_ms = int((record.updated_at - record.created_at).total_seconds() * 1000)
        return ChatToolCallResponse(
            id=record.id,
            session_id=record.session_id,
            run_id=record.run_id,
            name=record.name,
            status=cast(Literal["running", "completed", "failed"], record.status),
            input=record.input_json,
            output=record.output_json,
            error_message=record.error_message,
            duration_ms=duration_ms,
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

    def _build_timeline(
        self,
        *,
        messages: list[ChatMessageRecord],
        runs: list[ChatRunRecord],
        tool_calls: list[ChatToolCallRecord],
        confirmations: list[ChatConfirmationRecord],
    ) -> list[ChatTimelineItemResponse]:
        messages_by_id = {message.id: message for message in messages}
        confirmations_by_id = {confirmation.id: confirmation for confirmation in confirmations}
        tools_by_run_id: dict[str, list[ChatToolCallRecord]] = {}
        for tool in tool_calls:
            tools_by_run_id.setdefault(tool.run_id, []).append(tool)

        items: list[ChatTimelineItemResponse] = []
        consumed_message_ids: set[str] = set()
        consumed_tool_ids: set[str] = set()
        consumed_confirmation_ids: set[str] = set()

        def append_message(message: ChatMessageRecord, run_id: str | None) -> None:
            if message.id in consumed_message_ids:
                return
            consumed_message_ids.add(message.id)
            items.append(
                ChatTimelineItemResponse(
                    id=f"message:{message.id}",
                    kind="message",
                    session_id=message.session_id,
                    run_id=run_id,
                    message=self._message_response(message),
                    created_at=message.created_at,
                )
            )

        def append_tool(tool: ChatToolCallRecord) -> None:
            if tool.id in consumed_tool_ids:
                return
            if tool.name in self._TIMELINE_HIDDEN_TOOL_NAMES:
                consumed_tool_ids.add(tool.id)
                return
            consumed_tool_ids.add(tool.id)
            items.append(
                ChatTimelineItemResponse(
                    id=f"tool:{tool.id}",
                    kind="tool_call",
                    session_id=tool.session_id,
                    run_id=tool.run_id,
                    tool_call=self._tool_response(tool),
                    created_at=tool.created_at,
                )
            )

        def append_confirmation(
            confirmation: ChatConfirmationRecord,
            run_id: str | None,
        ) -> None:
            if confirmation.id in consumed_confirmation_ids:
                return
            if confirmation.status != ChatConfirmationStatus.pending.value:
                consumed_confirmation_ids.add(confirmation.id)
                return
            consumed_confirmation_ids.add(confirmation.id)
            items.append(
                ChatTimelineItemResponse(
                    id=f"confirmation:{confirmation.id}",
                    kind="confirmation",
                    session_id=confirmation.session_id,
                    run_id=run_id,
                    confirmation=self._confirmation_response(confirmation),
                    created_at=confirmation.created_at,
                )
            )

        for run in runs:
            if run.user_message_id is not None:
                user_message = messages_by_id.get(run.user_message_id)
                if user_message is not None:
                    append_message(user_message, run.id)

            for tool in tools_by_run_id.get(run.id, []):
                append_tool(tool)

            assistant_message: ChatMessageRecord | None = None
            if run.assistant_message_id is not None:
                assistant_message = messages_by_id.get(run.assistant_message_id)
                if assistant_message is not None:
                    append_message(assistant_message, run.id)

            confirmation_id = self._confirmation_id_from_message(assistant_message)
            if confirmation_id is not None:
                confirmation = confirmations_by_id.get(confirmation_id)
                if confirmation is not None:
                    append_confirmation(confirmation, run.id)

        for message in messages:
            if message.id not in consumed_message_ids:
                append_message(message, None)

        for tool in tool_calls:
            if tool.id not in consumed_tool_ids:
                append_tool(tool)

        for confirmation in confirmations:
            if confirmation.id not in consumed_confirmation_ids:
                append_confirmation(confirmation, None)

        return items

    @staticmethod
    def _confirmation_id_from_message(message: ChatMessageRecord | None) -> str | None:
        if message is None or message.metadata_json is None:
            return None
        value = message.metadata_json.get("confirmation_id")
        return value if isinstance(value, str) else None

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

    @staticmethod
    def _source_attachment_metadata(request: ChatRunStreamRequest) -> dict[str, Any] | None:
        if not request.source_text:
            return None
        return {
            "source_attachment": {
                "file_name": request.source_file_name or "novel.txt",
                "text_length": len(request.source_text),
                "media_type": "text/plain",
            }
        }

    async def _observe_awaitable(
        self,
        awaitable: Awaitable[Any],
        *,
        run_id: str,
        stage: str,
        toolbox: ChatToolbox | None = None,
    ) -> AsyncIterator[str | ObservedResult]:
        started_at = datetime.now(UTC)
        yield self._event(
            "run.progress",
            {
                "run_id": run_id,
                "stage": stage,
                "status": "started",
                "started_at": started_at,
            },
        )
        task = asyncio.ensure_future(awaitable)
        started = monotonic()
        last_heartbeat = started
        poll_interval = (
            min(0.25, self.settings.sse_heartbeat_interval_seconds)
            if toolbox is not None
            else self.settings.sse_heartbeat_interval_seconds
        )
        try:
            while not task.done():
                if toolbox is not None:
                    async for event in self._drain_toolbox_events(toolbox):
                        yield event
                done, _ = await asyncio.wait(
                    {task},
                    timeout=poll_interval,
                )
                if toolbox is not None:
                    async for event in self._drain_toolbox_events(toolbox):
                        yield event
                now = monotonic()
                if (
                    not done
                    and now - last_heartbeat >= self.settings.sse_heartbeat_interval_seconds
                ):
                    last_heartbeat = now
                    yield self._event(
                        "heartbeat",
                        {
                            "run_id": run_id,
                            "stage": stage,
                            "created_at": datetime.now(UTC),
                        },
                    )
            value = task.result()
            if toolbox is not None:
                async for event in self._drain_toolbox_events(toolbox):
                    yield event
        except Exception as exc:
            if toolbox is not None:
                async for event in self._drain_toolbox_events(toolbox):
                    yield event
            duration_ms = int((monotonic() - started) * 1000)
            yield self._event(
                "run.progress",
                {
                    "run_id": run_id,
                    "stage": stage,
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "message": str(exc),
                },
            )
            raise
        duration_ms = int((monotonic() - started) * 1000)
        yield self._event(
            "run.progress",
            {
                "run_id": run_id,
                "stage": stage,
                "status": "completed",
                "duration_ms": duration_ms,
            },
        )
        yield ObservedResult(value)

    async def _drain_toolbox_events(self, toolbox: ChatToolbox) -> AsyncIterator[str]:
        while not toolbox.live_events.empty():
            yield toolbox.live_events.get_nowait()

    def _event(self, name: str, data: dict[str, Any]) -> str:
        return format_sse_event(name, data)

    def _message_created_event(self, message: ChatMessageRecord, run_id: str | None) -> str:
        payload = self._message_response(message).model_dump(mode="json")
        payload["run_id"] = run_id
        return self._event("message.created", payload)
