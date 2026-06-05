from __future__ import annotations

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
from app.services.project_service import ProjectService
from app.services.script_service import ScriptService
from app.storage.project_store import ProjectStore


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


class ScriptGeneratedToolResult(BaseModel):
    accepted_version_id: str | None = Field(
        default=None,
        description="Accepted screenplay version ID, if harness accepted the YAML.",
    )
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID, if harness rejected the YAML after repairs.",
    )
    accepted: bool = Field(..., description="Whether the generated YAML passed harness.")
    severity: str = Field(..., description="Harness validation severity.")
    repair_attempt_count: int = Field(..., description="Automatic repair attempts performed.")
    validation_status: Literal["accepted", "rejected"] = Field(
        ...,
        description="Final persisted validation status.",
    )


class ScriptEditedToolResult(BaseModel):
    accepted_version_id: str | None = Field(
        default=None,
        description="Accepted screenplay version ID, if harness accepted the edit.",
    )
    rejected_version_id: str | None = Field(
        default=None,
        description="Rejected draft version ID, if harness rejected the edit after repairs.",
    )
    operation_count: int = Field(..., description="Applied YAML patch operation count.")
    accepted: bool = Field(..., description="Whether the edited YAML passed harness.")
    repair_attempt_count: int = Field(..., description="Automatic repair attempts performed.")
    validation_status: Literal["accepted", "rejected"] = Field(
        ...,
        description="Final persisted validation status.",
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

    async def propose_project_title(self) -> ProjectTitleSuggestion:
        tool = await self._start_tool(
            "propose_project_title",
            {"file_name": self.source_file_name, "text_length": len(self.source_text)},
        )
        try:
            title = await self.agent.infer_project_title(
                self._title_prompt(self.source_file_name, self.source_text)
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
            self.events.append(
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
            self.pending_confirmation_id = confirmation.id
            result = ConfirmationRequestedToolResult(
                confirmation_id=confirmation.id,
                prompt=confirmation.prompt,
                chapter_count=self.chapter_split_preview.chapter_count,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self.events.append(
                format_sse_event(
                    "tool.confirm.required",
                    self._confirmation_response(confirmation).model_dump(mode="json"),
                )
            )
            self.events.append(
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
            self.events.append(
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
            index = await BookIndexService(
                self.db_session,
                self.settings,
                self.agent,
            ).build_index(project_id, force_rebuild=force_rebuild)
            result = BookIndexBuiltToolResult(
                file_path=index.file_path,
                chapter_count=index.book_index.chapter_count,
                character_count=len(index.book_index.characters),
                location_count=len(index.book_index.locations),
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self.events.append(
                format_sse_event(
                    "asset.updated",
                    {"asset": "book_index", "project_id": project_id, "file_path": index.file_path},
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
            script = await ScriptService(
                self.db_session,
                self.settings,
                self.agent,
            ).generate_script(project_id, force_regenerate=force_regenerate)
            result = ScriptGeneratedToolResult(
                accepted_version_id=script.accepted_version_id,
                rejected_version_id=script.rejected_version_id,
                accepted=script.validation_report.accepted,
                severity=script.validation_report.severity,
                repair_attempt_count=script.repair_attempt_count,
                validation_status=script.validation_status,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self._record_validation_outcome(
                project_id=project_id,
                validation_status=script.validation_status,
                accepted_version_id=script.accepted_version_id,
                rejected_version_id=script.rejected_version_id,
                validation_report=script.validation_report.model_dump(mode="json"),
                repair_attempt_count=script.repair_attempt_count,
            )
            self.events.append(
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
            edit = await ScriptService(
                self.db_session,
                self.settings,
                self.agent,
            ).edit_script(
                project_id=project_id,
                instruction=instruction,
                target_path=None,
            )
            result = ScriptEditedToolResult(
                accepted_version_id=edit.accepted_version_id,
                rejected_version_id=edit.rejected_version_id,
                operation_count=len(edit.operations),
                accepted=edit.validation_report.accepted,
                repair_attempt_count=edit.repair_attempt_count,
                validation_status=edit.validation_status,
            )
            await self._complete_tool(tool, result.model_dump(mode="json"))
            self._record_validation_outcome(
                project_id=project_id,
                validation_status=edit.validation_status,
                accepted_version_id=edit.accepted_version_id,
                rejected_version_id=edit.rejected_version_id,
                validation_report=edit.validation_report.model_dump(mode="json"),
                repair_attempt_count=edit.repair_attempt_count,
            )
            self.events.append(
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
        self.events.append(
            format_sse_event("tool.call.started", self._tool_response(tool).model_dump())
        )
        return tool

    async def _complete_tool(self, tool: ChatToolCallRecord, output_json: dict[str, Any]) -> None:
        await self.recorder.complete_tool(tool, output_json)
        self.events.append(
            format_sse_event("tool.call.completed", self._tool_response(tool).model_dump())
        )

    async def _fail_tool(self, tool: ChatToolCallRecord, error_message: str) -> None:
        await self.recorder.fail_tool(tool, error_message)
        self.events.append(
            format_sse_event("tool.call.failed", self._tool_response(tool).model_dump())
        )

    def _record_validation_outcome(
        self,
        project_id: str,
        validation_status: Literal["accepted", "rejected"],
        accepted_version_id: str | None,
        rejected_version_id: str | None,
        validation_report: dict[str, Any],
        repair_attempt_count: int,
    ) -> None:
        if validation_status == "rejected":
            self.completed_with_errors = True
            self.last_rejected_version_id = rejected_version_id
            self.last_repair_attempt_count = repair_attempt_count
            self.last_validation_report = validation_report
            self.last_validation_error_message = (
                f"剧本 YAML 未通过 harness，已自动修复 {repair_attempt_count} 次，"
                "当前结果已保存为 rejected draft。"
            )
        self.events.append(
            format_sse_event(
                "validation.completed",
                {
                    "project_id": project_id,
                    "validation_status": validation_status,
                    "accepted_version_id": accepted_version_id,
                    "rejected_version_id": rejected_version_id,
                    "repair_attempt_count": repair_attempt_count,
                    "validation_report": validation_report,
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
