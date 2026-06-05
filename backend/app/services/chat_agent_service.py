from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.events import format_sse_event
from app.agent_runtime.recorder import ChatRunRecorder
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
    ChapterSplitInferencePreview,
    ChapterSplitInferenceRequest,
    ProjectCreateRequest,
    TxtEbookImportRequest,
)
from app.api.models.scripts import ScriptVersionDetailResponse, ScriptVersionListResponse
from app.core.config import Settings
from app.db.models import (
    ChatConfirmationRecord,
    ChatConfirmationStatus,
    ChatMessageRecord,
    ChatMessageRole,
    ChatRunRecord,
    ChatRunStatus,
    ChatSessionRecord,
    ChatSessionStatus,
    ChatToolCallRecord,
)
from app.db.repositories.chat import ChatRepository
from app.db.repositories.script_versions import ScriptVersionRepository
from app.schemas.chapter_split import ChapterSplitRule
from app.schemas.chat import ProjectTitleSuggestion
from app.services.book_index_service import (
    BookIndexNotFoundError,
    BookIndexService,
    BookIndexServiceProjectNotFoundError,
)
from app.services.chapter_split_inference_service import ChapterSplitInferenceService
from app.services.project_service import ProjectNotFoundError, ProjectService
from app.services.script_service import (
    ScriptService,
    ScriptServiceProjectNotFoundError,
    ScriptVersionNotFoundError,
)
from app.storage.project_store import ProjectStore


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
        self.store = ProjectStore(settings.local_artifact_root)

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
        file_name = request.source_file_name or "novel.txt"
        source_text = request.source_text or ""

        yield self._event("message.delta", {"content": "已收到小说文本，开始识别项目与分章方式。"})
        title_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="infer_project_title",
            input_json={
                "file_name": file_name,
                "text_length": len(source_text),
            },
        )
        yield self._event("tool.call.started", self._tool_response(title_tool).model_dump())
        title = await self.agent.infer_project_title(self._title_prompt(file_name, source_text))
        await self.recorder.complete_tool(
            title_tool,
            {
                "title": title.title,
                "reason": title.reason,
            },
        )
        yield self._event("tool.call.completed", self._tool_response(title_tool).model_dump())

        project_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="create_project",
            input_json={
                "title": title.title,
                "screenplay_format": request.screenplay_format,
            },
        )
        yield self._event("tool.call.started", self._tool_response(project_tool).model_dump())
        project_service = ProjectService(self.session, self.settings)
        project = await project_service.create_project(
            ProjectCreateRequest(
                title=title.title,
                screenplay_format=request.screenplay_format,
            )
        )
        source_path = self.store.write_source_text(project.id, file_name, source_text)
        session.project_id = project.id
        session.title = project.title
        await self.chat.touch_session(session)
        await self.recorder.complete_tool(
            project_tool,
            {
                "project_id": project.id,
                "title": project.title,
                "source_text_path": str(source_path),
            },
        )
        yield self._event("tool.call.completed", self._tool_response(project_tool).model_dump())
        yield self._event(
            "asset.updated",
            {
                "asset": "project",
                "project_id": project.id,
                "title": project.title,
            },
        )

        split_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="infer_chapter_split_rule",
            input_json={
                "project_id": project.id,
                "file_name": file_name,
                "text_length": len(source_text),
            },
        )
        yield self._event("tool.call.started", self._tool_response(split_tool).model_dump())
        split_service = ChapterSplitInferenceService(self.session, self.settings, self.agent)
        inference = await split_service.infer_rule(
            project.id,
            ChapterSplitInferenceRequest(
                file_name=file_name,
                content=source_text,
                max_sample_chars=5000,
                max_review_rounds=2,
                context_window_chars=1200,
            ),
        )
        split_summary = {
            "rule": inference.rule.model_dump(mode="json"),
            "preview": inference.preview.model_dump(mode="json"),
            "iteration_count": len(inference.iterations),
        }
        await self.recorder.complete_tool(split_tool, split_summary)
        yield self._event("tool.call.completed", self._tool_response(split_tool).model_dump())

        confirmation = await self._create_chapter_split_confirmation(
            session=session,
            project_id=project.id,
            file_name=file_name,
            source_text_path=str(source_path),
            text_length=len(source_text),
            rule=inference.rule,
            preview=inference.preview,
        )
        run.status = ChatRunStatus.waiting_confirmation.value
        assistant = await self.recorder.add_message(
            session_id=session.id,
            role=ChatMessageRole.assistant,
            content=(
                f"我推导出《{project.title}》的分章方式，预览得到 "
                f"{inference.preview.chapter_count} 个章节。请确认分章后，"
                "我会继续生成剧情索引和剧本 YAML。"
            ),
            metadata={"confirmation_id": confirmation.id, "kind": confirmation.kind},
        )
        run.assistant_message_id = assistant.id
        await self.session.commit()
        yield self._event(
            "tool.confirm.required",
            self._confirmation_response(confirmation).model_dump(mode="json"),
        )
        yield self._event(
            "run.waiting_confirmation",
            {"run_id": run.id, "confirmation_id": confirmation.id},
        )

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

        edit_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="edit_script_yaml",
            input_json={"project_id": session.project_id, "instruction": message},
        )
        yield self._event("tool.call.started", self._tool_response(edit_tool).model_dump())
        script_service = ScriptService(self.session, self.settings, self.agent)
        edit = await script_service.edit_script(
            project_id=session.project_id,
            instruction=message,
            target_path=None,
        )
        await self.recorder.complete_tool(
            edit_tool,
            {
                "accepted_version_id": edit.accepted_version_id,
                "operation_count": len(edit.operations),
                "accepted": edit.validation_report.accepted,
            },
        )
        yield self._event("tool.call.completed", self._tool_response(edit_tool).model_dump())
        yield self._event(
            "asset.updated",
            {
                "asset": "script_yaml",
                "project_id": session.project_id,
                "accepted_version_id": edit.accepted_version_id,
                "validation_report": edit.validation_report.model_dump(mode="json"),
            },
        )
        await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content="已根据你的说明修改剧本 YAML，并通过 harness 返回新的校验结果。",
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
        source_text = self.store.read_text(payload.source_text_path)
        project_id = confirmation.project_id
        if project_id is None:
            raise ChatConfirmationStateError("Chapter split confirmation has no project_id.")

        import_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="confirm_chapter_split",
            input_json={
                "project_id": project_id,
                "file_name": payload.file_name,
                "rule": rule.model_dump(mode="json"),
            },
        )
        yield self._event("tool.call.started", self._tool_response(import_tool).model_dump())
        project_service = ProjectService(self.session, self.settings)
        imported = await project_service.import_txt_ebook(
            project_id,
            TxtEbookImportRequest(
                file_name=payload.file_name,
                content=source_text,
                split_strategy="custom_rule",
                chapter_split_rule=rule,
                replace_existing=True,
            ),
        )
        confirmation.status = ChatConfirmationStatus.confirmed.value
        confirmation.resolved_at = datetime.now(UTC)
        await self.recorder.complete_tool(
            import_tool,
            {
                "chapter_count": imported.detected_chapter_count,
                "split_strategy": imported.split_strategy,
            },
        )
        yield self._event("tool.call.completed", self._tool_response(import_tool).model_dump())
        yield self._event(
            "asset.updated",
            {
                "asset": "chapters",
                "project_id": project_id,
                "chapter_count": imported.detected_chapter_count,
            },
        )

        index_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="build_book_index",
            input_json={"project_id": project_id, "force_rebuild": True},
        )
        yield self._event("tool.call.started", self._tool_response(index_tool).model_dump())
        index_service = BookIndexService(self.session, self.settings, self.agent)
        index = await index_service.build_index(project_id, force_rebuild=True)
        await self.recorder.complete_tool(
            index_tool,
            {
                "file_path": index.file_path,
                "chapter_count": index.book_index.chapter_count,
                "character_count": len(index.book_index.characters),
                "location_count": len(index.book_index.locations),
            },
        )
        yield self._event("tool.call.completed", self._tool_response(index_tool).model_dump())
        yield self._event(
            "asset.updated",
            {"asset": "book_index", "project_id": project_id, "file_path": index.file_path},
        )

        script_tool = await self.recorder.start_tool(
            chat_session=session,
            run=run,
            name="generate_script_yaml",
            input_json={"project_id": project_id, "force_regenerate": True},
        )
        yield self._event("tool.call.started", self._tool_response(script_tool).model_dump())
        script_service = ScriptService(self.session, self.settings, self.agent)
        script = await script_service.generate_script(project_id, force_regenerate=True)
        await self.recorder.complete_tool(
            script_tool,
            {
                "accepted_version_id": script.accepted_version_id,
                "accepted": script.validation_report.accepted,
                "severity": script.validation_report.severity,
            },
        )
        yield self._event("tool.call.completed", self._tool_response(script_tool).model_dump())
        yield self._event(
            "asset.updated",
            {
                "asset": "script_yaml",
                "project_id": project_id,
                "accepted_version_id": script.accepted_version_id,
                "validation_report": script.validation_report.model_dump(mode="json"),
            },
        )
        await self.recorder.complete_run(
            run=run,
            chat_session=session,
            content=(
                "分章已确认，剧情索引和剧本 YAML 已生成。"
                "你现在可以直接用自然语言继续要求我修改剧本。"
            ),
        )
        yield self._event("run.completed", {"run_id": run.id})

    async def _create_chapter_split_confirmation(
        self,
        session: ChatSessionRecord,
        project_id: str,
        file_name: str,
        source_text_path: str,
        text_length: int,
        rule: ChapterSplitRule,
        preview: ChapterSplitInferencePreview,
    ) -> ChatConfirmationRecord:
        payload = ChapterSplitConfirmationPayload(
            file_name=file_name,
            source_text_path=source_text_path,
            text_length=text_length,
            rule=rule,
            preview=preview,
        )
        confirmation = ChatConfirmationRecord(
            id=f"confirm_{uuid4().hex[:12]}",
            session_id=session.id,
            project_id=project_id,
            kind="chapter_split",
            status=ChatConfirmationStatus.pending.value,
            prompt="请确认当前分章预览。确认后我会继续构建剧情索引并生成剧本 YAML。",
            payload_json=payload.model_dump(mode="json"),
        )
        await self.chat.add_confirmation(confirmation)
        await self.session.commit()
        return confirmation

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

    def _title_prompt(self, file_name: str, source_text: str) -> str:
        normalized = source_text.replace("\r\n", "\n").replace("\r", "\n")
        head = normalized[:3000]
        tail = normalized[-1200:] if len(normalized) > 4200 else ""
        suggestion = ProjectTitleSuggestion(
            title="标题格式示例",
            reason="示例仅用于说明输出结构。",
        )
        return "\n\n".join(
            [
                "请为这份小说改编任务推导项目名。",
                f"文件名：{file_name}",
                f"全文字符数：{len(source_text)}",
                "输出结构示例：",
                suggestion.model_dump_json(ensure_ascii=False),
                "正文开头：",
                head,
                "正文结尾：" if tail else "",
                tail,
            ]
        )

    def _event(self, name: str, data: dict[str, Any]) -> str:
        return format_sse_event(name, data)
