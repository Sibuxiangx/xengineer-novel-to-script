from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.events import format_sse_event
from app.agent_runtime.recorder import ChatRunRecorder
from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.chat import (
    ChapterSplitConfirmationPayload,
    ChatConfirmationResponse,
    ChatMessageResponse,
    ChatToolCallResponse,
)
from app.api.models.projects import (
    ChapterSplitInferencePreview,
    ChapterSplitInferenceRequest,
    ProjectCreateRequest,
    TxtEbookImportRequest,
)
from app.core.config import Settings
from app.db.models import (
    ChatConfirmationRecord,
    ChatConfirmationStatus,
    ChatMessageRecord,
    ChatMessageRole,
    ChatRunRecord,
    ChatRunStatus,
    ChatSessionRecord,
    ChatToolCallRecord,
)
from app.db.repositories.chat import ChatRepository
from app.schemas.chapter_split import ChapterSplitRule
from app.schemas.chat import ProjectTitleSuggestion
from app.services.book_index_service import BookIndexService
from app.services.chapter_split_inference_service import ChapterSplitInferenceService
from app.services.context_packer import ContextPackingReport
from app.services.project_service import ProjectService
from app.services.script_service import ScriptService
from app.storage.project_store import ProjectStore

StreamDeltaCallback = Callable[[dict[str, Any]], Awaitable[None]]


class ProjectCreatedToolResult(BaseModel):
    project_id: str = Field(..., description="Created project ID.")
    title: str = Field(..., description="Project title.")
    source_text_path: str = Field(..., description="Persisted source TXT artifact path.")


class ChapterSplitProposedToolResult(BaseModel):
    rule: ChapterSplitRule = Field(..., description="Inferred chapter split rule.")
    preview: ChapterSplitInferencePreview = Field(..., description="Local split preview.")
    iteration_count: int = Field(..., description="Inference and review iteration count.")


class ConfirmationRequestedToolResult(BaseModel):
    confirmation_id: str = Field(..., description="Pending confirmation ID.")
    prompt: str = Field(..., description="Prompt shown to the user.")
    chapter_count: int = Field(..., description="Preview chapter count.")


class ChapterImportToolResult(BaseModel):
    chapter_count: int = Field(..., description="Imported chapter count.")
    split_strategy: str = Field(..., description="Applied split strategy.")


class BookIndexBuiltToolResult(BaseModel):
    file_path: str = Field(..., description="Path to generated book_index.json.")
    chapter_count: int = Field(..., description="Indexed chapter count.")
    character_count: int = Field(..., description="Indexed character count.")
    location_count: int = Field(..., description="Indexed location count.")
    context_report: ContextPackingReport | None = Field(
        default=None,
        description="Context packing diagnostics for the book index model prompt.",
    )


class ScriptGeneratedToolResult(BaseModel):
    accepted_version_id: str | None = Field(
        default=None,
        description="Accepted screenplay version ID, if validation accepted the YAML.",
    )
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID, if validation rejected the YAML after repairs.",
    )
    accepted: bool = Field(..., description="Whether the generated YAML passed validation.")
    severity: str = Field(..., description="Validation severity.")
    repair_attempt_count: int = Field(..., description="Automatic repair attempts performed.")
    validation_status: Literal["accepted", "rejected"] = Field(
        ...,
        description="Final persisted validation status.",
    )
    context_report: ContextPackingReport | None = Field(
        default=None,
        description="Context packing diagnostics for the generation prompt.",
    )


class ScriptEditedToolResult(BaseModel):
    accepted_version_id: str | None = Field(
        default=None,
        description="Accepted screenplay version ID, if validation accepted the edit.",
    )
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID, if validation rejected the edit after repairs.",
    )
    operation_count: int = Field(..., description="Applied YAML patch operation count.")
    accepted: bool = Field(..., description="Whether the edited YAML passed validation.")
    repair_attempt_count: int = Field(..., description="Automatic repair attempts performed.")
    validation_status: Literal["accepted", "rejected"] = Field(
        ...,
        description="Final persisted validation status.",
    )
    context_report: ContextPackingReport | None = Field(
        default=None,
        description="Context packing diagnostics for the edit planning prompt.",
    )


class ChatToolbox:
    """Business tools exposed to the Pydantic AI chat agent."""

    def __init__(
        self,
        *,
        db_session: AsyncSession,
        settings: Settings,
        agent: ScreenplayAgent,
        chat: ChatRepository,
        recorder: ChatRunRecorder,
        chat_session: ChatSessionRecord,
        run: ChatRunRecord,
        source_file_name: str | None = None,
        source_text: str | None = None,
        screenplay_format: str = "short_drama",
    ) -> None:
        self.db_session = db_session
        self.settings = settings
        self.agent = agent
        self.chat = chat
        self.recorder = recorder
        self.chat_session = chat_session
        self.run = run
        self.source_file_name = source_file_name or "novel.txt"
        self.source_text = source_text or ""
        self.screenplay_format = screenplay_format
        self.store = ProjectStore(settings.local_artifact_root)
        self.events: list[str] = []
        self.project_id = chat_session.project_id
        self.project_title = chat_session.title
        self.source_text_path: str | None = None
        self.chapter_split_rule: ChapterSplitRule | None = None
        self.chapter_split_preview: ChapterSplitInferencePreview | None = None
        self.pending_confirmation_id: str | None = None
        self.completed_with_errors = False
        self.last_rejected_version_id: str | None = None
        self.last_repair_attempt_count = 0
        self.last_validation_report: dict[str, Any] | None = None
        self.last_validation_error_message: str | None = None
        self.live_events: asyncio.Queue[str] = asyncio.Queue()

    async def propose_project_title(self) -> ProjectTitleSuggestion:
        tool = await self._start_tool(
            "propose_project_title",
            {"file_name": self.source_file_name, "text_length": len(self.source_text)},
        )
        try:
            title = await self.agent.infer_project_title(
                self._title_prompt(self.source_file_name, self.source_text),
                stream_callback=self._llm_stream_callback(tool, "infer_project_title"),
            )
            await self._complete_tool(
                tool,
                {
                    "title": title.title,
                    "reason": title.reason,
                },
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return title

    async def create_project(self, title: str) -> ProjectCreatedToolResult:
        tool = await self._start_tool(
            "create_project",
            {"title": title, "screenplay_format": self.screenplay_format},
        )
        try:
            project = await ProjectService(self.db_session, self.settings).create_project(
                ProjectCreateRequest(
                    title=title,
                    screenplay_format=self.screenplay_format,
                )
            )
            source_path = self.store.write_source_text(
                project.id,
                self.source_file_name,
                self.source_text,
            )
            self.chat_session.project_id = project.id
            self.chat_session.title = project.title
            await self.chat.touch_session(self.chat_session)
            self.project_id = project.id
            self.project_title = project.title
            self.source_text_path = str(source_path)
            result = ProjectCreatedToolResult(
                project_id=project.id,
                title=project.title,
                source_text_path=str(source_path),
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self._append_event(
                format_sse_event(
                    "asset.updated",
                    {
                        "asset": "project",
                        "project_id": project.id,
                        "title": project.title,
                    },
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def propose_chapter_split(self) -> ChapterSplitProposedToolResult:
        project_id = self._require_project_id()
        tool = await self._start_tool(
            "propose_chapter_split",
            {
                "project_id": project_id,
                "file_name": self.source_file_name,
                "text_length": len(self.source_text),
            },
        )
        try:
            inference = await ChapterSplitInferenceService(
                self.db_session,
                self.settings,
                self.agent,
            ).infer_rule(
                project_id,
                ChapterSplitInferenceRequest(
                    file_name=self.source_file_name,
                    content=self.source_text,
                    max_sample_chars=5000,
                    max_review_rounds=2,
                    context_window_chars=1200,
                ),
                stream_callback=self._llm_stream_callback(tool, "propose_chapter_split"),
            )
            self.chapter_split_rule = inference.rule
            self.chapter_split_preview = inference.preview
            result = ChapterSplitProposedToolResult(
                rule=inference.rule,
                preview=inference.preview,
                iteration_count=len(inference.iterations),
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def request_chapter_split_confirmation(self) -> ConfirmationRequestedToolResult:
        project_id = self._require_project_id()
        if self.source_text_path is None:
            raise RuntimeError("Source text has not been persisted.")
        if self.chapter_split_rule is None or self.chapter_split_preview is None:
            raise RuntimeError("Chapter split has not been proposed.")

        tool = await self._start_tool(
            "request_chapter_split_confirmation",
            {
                "project_id": project_id,
                "chapter_count": self.chapter_split_preview.chapter_count,
            },
        )
        try:
            confirmation = await self._create_chapter_split_confirmation(
                project_id=project_id,
                source_text_path=self.source_text_path,
                text_length=len(self.source_text),
                rule=self.chapter_split_rule,
                preview=self.chapter_split_preview,
            )
            self.run.status = ChatRunStatus.waiting_confirmation.value
            assistant = await self.recorder.add_message(
                session_id=self.chat_session.id,
                role=ChatMessageRole.assistant,
                content=(
                    f"我推导出《{self.project_title}》的分章方式，预览得到 "
                    f"{self.chapter_split_preview.chapter_count} 个章节。请确认分章后，"
                    "我会继续生成剧情索引和剧本 YAML。"
                ),
                metadata={"confirmation_id": confirmation.id, "kind": confirmation.kind},
            )
            self.run.assistant_message_id = assistant.id
            await self.db_session.commit()
            self._append_event(
                format_sse_event(
                    "message.created",
                    {
                        **self._message_response(assistant).model_dump(mode="json"),
                        "run_id": self.run.id,
                    },
                )
            )
            self.pending_confirmation_id = confirmation.id
            result = ConfirmationRequestedToolResult(
                confirmation_id=confirmation.id,
                prompt=confirmation.prompt,
                chapter_count=self.chapter_split_preview.chapter_count,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self._append_event(
                format_sse_event(
                    "tool.confirm.required",
                    self._confirmation_response(confirmation).model_dump(mode="json"),
                )
            )
            self._append_event(
                format_sse_event(
                    "run.waiting_confirmation",
                    {"run_id": self.run.id, "confirmation_id": confirmation.id},
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def import_chapters(
        self,
        *,
        confirmation: ChatConfirmationRecord,
        rule: ChapterSplitRule,
    ) -> ChapterImportToolResult:
        payload = ChapterSplitConfirmationPayload.model_validate(confirmation.payload_json)
        project_id = confirmation.project_id
        if project_id is None:
            raise RuntimeError("Chapter split confirmation has no project_id.")
        source_text = self.store.read_text(payload.source_text_path)
        tool = await self._start_tool(
            "confirm_chapter_split",
            {
                "project_id": project_id,
                "file_name": payload.file_name,
                "rule": rule.model_dump(mode="json"),
            },
        )
        try:
            imported = await ProjectService(self.db_session, self.settings).import_txt_ebook(
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
            result = ChapterImportToolResult(
                chapter_count=imported.detected_chapter_count,
                split_strategy=imported.split_strategy,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self._append_event(
                format_sse_event(
                    "asset.updated",
                    {
                        "asset": "chapters",
                        "project_id": project_id,
                        "chapter_count": imported.detected_chapter_count,
                    },
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def build_book_index(
        self, project_id: str, force_rebuild: bool = True
    ) -> BookIndexBuiltToolResult:
        tool = await self._start_tool(
            "build_book_index",
            {"project_id": project_id, "force_rebuild": force_rebuild},
        )
        try:
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "preparing",
                    "message": "正在准备章节上下文并请求模型抽取人物、地点与事件。",
                },
            )
            index = await BookIndexService(
                self.db_session,
                self.settings,
                self.agent,
            ).build_index(
                project_id,
                force_rebuild=force_rebuild,
                stream_callback=self._llm_stream_callback(tool, "build_book_index"),
            )
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "parsed",
                    "kind": "metrics",
                    "chapter_count": index.book_index.chapter_count,
                    "character_count": len(index.book_index.characters),
                    "location_count": len(index.book_index.locations),
                },
            )
            for character in index.book_index.characters:
                await self._emit_tool_delta(
                    tool,
                    {
                        "phase": "parsed",
                        "kind": "character",
                        "item": {
                            "id": character.id,
                            "label": " / ".join(character.names),
                            "role": character.role,
                            "description": character.description,
                        },
                    },
                )
                await asyncio.sleep(0)
            for location in index.book_index.locations:
                await self._emit_tool_delta(
                    tool,
                    {
                        "phase": "parsed",
                        "kind": "location",
                        "item": {
                            "id": location.id,
                            "label": location.name,
                            "description": location.description,
                        },
                    },
                )
                await asyncio.sleep(0)
            result = BookIndexBuiltToolResult(
                file_path=index.file_path,
                chapter_count=index.book_index.chapter_count,
                character_count=len(index.book_index.characters),
                location_count=len(index.book_index.locations),
                context_report=index.context_report,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            await self._record_model_usage_estimate(
                tool=tool,
                project_id=project_id,
                task="build_book_index",
                context_report=index.context_report,
            )
            self._append_event(
                format_sse_event(
                    "asset.updated",
                    {
                        "asset": "book_index",
                        "project_id": project_id,
                        "file_path": index.file_path,
                        "context_report": (
                            index.context_report.model_dump(mode="json")
                            if index.context_report is not None
                            else None
                        ),
                    },
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def generate_script_yaml(
        self,
        project_id: str,
        force_regenerate: bool = True,
    ) -> ScriptGeneratedToolResult:
        tool = await self._start_tool(
            "generate_script_yaml",
            {"project_id": project_id, "force_regenerate": force_regenerate},
        )
        try:
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "preparing",
                    "message": "正在根据剧情索引生成剧本 YAML，并准备运行本地验证。",
                },
            )
            script = await ScriptService(
                self.db_session,
                self.settings,
                self.agent,
            ).generate_script(
                project_id,
                force_regenerate=force_regenerate,
                stream_callback=self._llm_stream_callback(tool, "generate_script_yaml"),
            )
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "validated",
                    "kind": "validation",
                    "accepted": script.validation_report.accepted,
                    "validation_status": script.validation_status,
                    "repair_attempt_count": script.repair_attempt_count,
                    "severity": script.validation_report.severity,
                },
            )
            result = ScriptGeneratedToolResult(
                accepted_version_id=script.accepted_version_id,
                rejected_version_id=script.rejected_version_id,
                accepted=script.validation_report.accepted,
                severity=script.validation_report.severity,
                repair_attempt_count=script.repair_attempt_count,
                validation_status=script.validation_status,
                context_report=script.context_report,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            await self._record_model_usage_estimate(
                tool=tool,
                project_id=project_id,
                task="generate_script_yaml",
                context_report=script.context_report,
            )
            self._record_validation_outcome(
                project_id=project_id,
                validation_status=script.validation_status,
                accepted_version_id=script.accepted_version_id,
                rejected_version_id=script.rejected_version_id,
                validation_report=script.validation_report.model_dump(mode="json"),
                repair_attempt_count=script.repair_attempt_count,
                context_report=(
                    script.context_report.model_dump(mode="json")
                    if script.context_report is not None
                    else None
                ),
            )
            self._append_event(
                format_sse_event(
                    "asset.updated",
                    {
                        "asset": "script_yaml",
                        "project_id": project_id,
                        "accepted_version_id": script.accepted_version_id,
                        "rejected_version_id": script.rejected_version_id,
                        "validation_status": script.validation_status,
                        "repair_attempt_count": script.repair_attempt_count,
                        "validation_report": script.validation_report.model_dump(mode="json"),
                        "context_report": (
                            script.context_report.model_dump(mode="json")
                            if script.context_report is not None
                            else None
                        ),
                    },
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def edit_script_yaml(self, project_id: str, instruction: str) -> ScriptEditedToolResult:
        tool = await self._start_tool(
            "edit_script_yaml",
            {"project_id": project_id, "instruction": instruction},
        )
        try:
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "planning",
                    "message": "正在把自然语言修改请求转成结构化 YAML 编辑操作。",
                },
            )
            edit = await ScriptService(
                self.db_session,
                self.settings,
                self.agent,
            ).edit_script(
                project_id=project_id,
                instruction=instruction,
                target_path=None,
                stream_callback=self._llm_stream_callback(tool, "edit_script_yaml"),
            )
            result = ScriptEditedToolResult(
                accepted_version_id=edit.accepted_version_id,
                rejected_version_id=edit.rejected_version_id,
                operation_count=len(edit.operations),
                accepted=edit.validation_report.accepted,
                repair_attempt_count=edit.repair_attempt_count,
                validation_status=edit.validation_status,
                context_report=edit.context_report,
            )
            await self._emit_tool_delta(
                tool,
                {
                    "phase": "validated",
                    "kind": "validation",
                    "accepted": edit.validation_report.accepted,
                    "validation_status": edit.validation_status,
                    "repair_attempt_count": edit.repair_attempt_count,
                    "operation_count": len(edit.operations),
                },
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            await self._record_model_usage_estimate(
                tool=tool,
                project_id=project_id,
                task="edit_script_yaml",
                context_report=edit.context_report,
            )
            self._record_validation_outcome(
                project_id=project_id,
                validation_status=edit.validation_status,
                accepted_version_id=edit.accepted_version_id,
                rejected_version_id=edit.rejected_version_id,
                validation_report=edit.validation_report.model_dump(mode="json"),
                repair_attempt_count=edit.repair_attempt_count,
                context_report=(
                    edit.context_report.model_dump(mode="json")
                    if edit.context_report is not None
                    else None
                ),
            )
            self._append_event(
                format_sse_event(
                    "asset.updated",
                    {
                        "asset": "script_yaml",
                        "project_id": project_id,
                        "accepted_version_id": edit.accepted_version_id,
                        "rejected_version_id": edit.rejected_version_id,
                        "validation_status": edit.validation_status,
                        "repair_attempt_count": edit.repair_attempt_count,
                        "validation_report": edit.validation_report.model_dump(mode="json"),
                        "context_report": (
                            edit.context_report.model_dump(mode="json")
                            if edit.context_report is not None
                            else None
                        ),
                    },
                )
            )
        except Exception as exc:
            await self._fail_tool(tool, str(exc))
            raise
        return result

    async def _start_tool(self, name: str, input_json: dict[str, Any]) -> ChatToolCallRecord:
        tool = await self.recorder.start_tool(
            chat_session=self.chat_session,
            run=self.run,
            name=name,
            input_json=input_json,
        )
        self._append_event(
            format_sse_event("tool.call.started", self._tool_response(tool).model_dump())
        )
        return tool

    async def _complete_tool(self, tool: ChatToolCallRecord, output_json: dict[str, Any]) -> None:
        await self.recorder.complete_tool(tool, output_json)
        self._append_event(
            format_sse_event("tool.call.completed", self._tool_response(tool).model_dump())
        )

    async def _fail_tool(self, tool: ChatToolCallRecord, error_message: str) -> None:
        await self.recorder.fail_tool(tool, error_message)
        self._append_event(
            format_sse_event("tool.call.failed", self._tool_response(tool).model_dump())
        )

    async def _emit_tool_delta(
        self,
        tool: ChatToolCallRecord,
        delta: dict[str, Any],
    ) -> None:
        self._append_event(
            format_sse_event(
                "tool.call.delta",
                {
                    "id": tool.id,
                    "session_id": tool.session_id,
                    "run_id": tool.run_id,
                    "name": tool.name,
                    "status": tool.status,
                    "delta": delta,
                    "created_at": datetime.now(UTC),
                },
            )
        )

    def _llm_stream_callback(
        self,
        tool: ChatToolCallRecord,
        tool_phase: str,
    ) -> StreamDeltaCallback:
        async def callback(delta: dict[str, Any]) -> None:
            await self._emit_tool_delta(
                tool,
                {
                    "kind": "llm_stream",
                    "tool_phase": tool_phase,
                    **delta,
                },
            )

        return callback

    def _append_event(self, event: str) -> None:
        self.events.append(event)
        self.live_events.put_nowait(event)

    async def _record_model_usage_estimate(
        self,
        *,
        tool: ChatToolCallRecord,
        project_id: str,
        task: str,
        context_report: ContextPackingReport | None,
    ) -> None:
        if context_report is None:
            return
        model = self._model_name_for_task(task)
        await self.recorder.record_model_usage(
            project_id=project_id,
            provider="deepseek",
            model=model,
            estimated_input_tokens=context_report.estimated_tokens,
        )
        self._append_event(
            format_sse_event(
                "model.usage.estimated",
                {
                    "id": f"usage:{tool.id}",
                    "tool_call_id": tool.id,
                    "project_id": project_id,
                    "task": task,
                    "provider": "deepseek",
                    "model": model,
                    "estimated_input_tokens": context_report.estimated_tokens,
                    "context_budget_tokens": context_report.budget_tokens,
                    "included_block_ids": context_report.included_block_ids,
                    "omitted_block_ids": context_report.omitted_block_ids,
                },
            )
        )

    def _model_name_for_task(self, task: str) -> str:
        if task in {"build_book_index", "generate_script_yaml"}:
            return self.settings.deepseek_fast_model
        return self.settings.deepseek_model

    def _record_validation_outcome(
        self,
        project_id: str,
        validation_status: Literal["accepted", "rejected"],
        accepted_version_id: str | None,
        rejected_version_id: str | None,
        validation_report: dict[str, Any],
        repair_attempt_count: int,
        context_report: dict[str, Any] | None,
    ) -> None:
        if validation_status == "rejected":
            self.completed_with_errors = True
            self.last_rejected_version_id = rejected_version_id
            self.last_repair_attempt_count = repair_attempt_count
            self.last_validation_report = validation_report
            self.last_validation_error_message = (
                f"剧本 YAML 未通过验证，已自动修复 {repair_attempt_count} 次，"
                "当前结果已保存为 rejected draft。"
            )
        self._append_event(
            format_sse_event(
                "validation.completed",
                {
                    "project_id": project_id,
                    "validation_status": validation_status,
                    "accepted_version_id": accepted_version_id,
                    "rejected_version_id": rejected_version_id,
                    "repair_attempt_count": repair_attempt_count,
                    "validation_report": validation_report,
                    "context_report": context_report,
                },
            )
        )

    async def _create_chapter_split_confirmation(
        self,
        project_id: str,
        source_text_path: str,
        text_length: int,
        rule: ChapterSplitRule,
        preview: ChapterSplitInferencePreview,
    ) -> ChatConfirmationRecord:
        payload = ChapterSplitConfirmationPayload(
            file_name=self.source_file_name,
            source_text_path=source_text_path,
            text_length=text_length,
            rule=rule,
            preview=preview,
        )
        confirmation = ChatConfirmationRecord(
            id=f"confirm_{uuid4().hex[:12]}",
            session_id=self.chat_session.id,
            project_id=project_id,
            kind="chapter_split",
            status=ChatConfirmationStatus.pending.value,
            prompt="请确认当前分章预览。确认后我会继续构建剧情索引并生成剧本 YAML。",
            payload_json=payload.model_dump(mode="json"),
        )
        await self.chat.add_confirmation(confirmation)
        await self.db_session.commit()
        return confirmation

    def _require_project_id(self) -> str:
        if self.project_id is None:
            raise RuntimeError("Project has not been created.")
        return self.project_id

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

    @staticmethod
    def _message_response(record: ChatMessageRecord) -> ChatMessageResponse:
        return ChatMessageResponse(
            id=record.id,
            session_id=record.session_id,
            role=cast(Literal["user", "assistant", "system", "tool"], record.role),
            content=record.content,
            metadata=record.metadata_json,
            created_at=record.created_at,
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
