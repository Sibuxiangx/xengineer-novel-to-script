from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.scripts import (
    ScriptEditResponse,
    ScriptExportResponse,
    ScriptGenerateResponse,
    ScriptRestoreResponse,
    ScriptValidateResponse,
    ScriptVersionDetailResponse,
    ScriptVersionListResponse,
    ScriptVersionResponse,
)
from app.core.config import Settings
from app.db.models import ScriptVersionRecord, ValidationReportRecord, ValidationStatus
from app.db.repositories.chapters import ChapterRepository
from app.db.repositories.projects import ProjectRepository
from app.db.repositories.script_versions import ScriptVersionRepository
from app.schemas.book_index import BookIndex
from app.schemas.screenplay import ScreenplayYaml
from app.schemas.yaml_patch import YamlPatchOperation
from app.services.validation_service import ValidationService
from app.services.yaml_patch_service import YamlPatchApplier
from app.storage.project_store import ProjectStore


class ScriptServiceProjectNotFoundError(Exception):
    """Raised when a project does not exist for script operations."""


class BookIndexRequiredError(Exception):
    """Raised when an operation requires a generated book index."""


class CurrentScriptNotFoundError(Exception):
    """Raised when an operation requires an existing current script."""


class ScriptVersionNotFoundError(Exception):
    """Raised when a requested accepted script version does not exist."""


class ScriptValidationRejectedError(Exception):
    """Raised when a script cannot be saved because harness rejected it."""


class ScriptService:
    """Application service for screenplay YAML validation and lifecycle operations."""

    def __init__(self, session: AsyncSession, settings: Settings, agent: ScreenplayAgent) -> None:
        self.session = session
        self.settings = settings
        self.agent = agent
        self.projects = ProjectRepository(session)
        self.chapters = ChapterRepository(session)
        self.versions = ScriptVersionRepository(session)
        self.store = ProjectStore(settings.local_artifact_root)
        self.validation = ValidationService()
        self.yaml_patches = YamlPatchApplier()

    async def validate_script(self, project_id: str, script_yaml: str) -> ScriptValidateResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)

        chapters = await self.chapters.list_by_project(project_id)
        chapter_ids = {chapter.id for chapter in chapters}
        book_index = self._load_book_index(project_id)
        report = self.validation.validate_script_yaml(
            script_yaml=script_yaml,
            chapter_ids=chapter_ids,
            book_index=book_index,
        )
        return ScriptValidateResponse(
            project_id=project_id,
            validation_report=report.to_response(),
        )

    async def generate_script(
        self,
        project_id: str,
        force_regenerate: bool,
    ) -> ScriptGenerateResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)

        current_path = self.store.script_path(project_id)
        if current_path.exists() and not force_regenerate:
            script_yaml = self.store.read_text(current_path)
            report = await self.validate_script(project_id, script_yaml)
            return ScriptGenerateResponse(
                project_id=project_id,
                script_yaml=script_yaml,
                validation_report=report.validation_report,
                accepted_version_id=project.current_script_version_id,
                rejected_version_id=None,
                repair_attempt_count=0,
                validation_status=(
                    ValidationStatus.accepted.value
                    if report.validation_report.accepted
                    else ValidationStatus.rejected.value
                ),
            )

        book_index = self._require_book_index(project_id)
        chapters = await self.chapters.list_by_project(project_id)
        prompt = self._script_generation_prompt(
            project_id=project_id,
            project_title=project.title,
            book_index=book_index,
            chapters=[
                {
                    "id": chapter.id,
                    "title": chapter.title,
                    "content": self.store.read_text(chapter.file_path),
                }
                for chapter in chapters
            ],
        )
        screenplay = await self.agent.generate_script(prompt)
        script_yaml = self._dump_screenplay(screenplay)
        report = await self.validate_script(project_id, script_yaml)
        script_yaml, report, repair_attempt_count = await self._repair_until_accepted(
            project_id=project_id,
            script_yaml=script_yaml,
            report=report,
            book_index=book_index,
        )
        accepted_version_id = None
        rejected_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=script_yaml,
                created_by="agent",
                reason=(
                    "生成初版剧本 YAML"
                    if repair_attempt_count == 0
                    else f"生成初版剧本 YAML，并自动修复 {repair_attempt_count} 次"
                ),
                operation_count=repair_attempt_count,
                validation_status=ValidationStatus.accepted,
                validation_report=report.validation_report,
                make_current=True,
            )
        else:
            rejected_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=script_yaml,
                created_by="agent",
                reason=f"生成初版剧本 YAML 未通过 harness，已自动修复 {repair_attempt_count} 次",
                operation_count=repair_attempt_count,
                validation_status=ValidationStatus.rejected,
                validation_report=report.validation_report,
                make_current=False,
            )
        return ScriptGenerateResponse(
            project_id=project_id,
            script_yaml=script_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
            rejected_version_id=rejected_version_id,
            repair_attempt_count=repair_attempt_count,
            validation_status=(
                ValidationStatus.accepted.value
                if report.validation_report.accepted
                else ValidationStatus.rejected.value
            ),
        )

    async def edit_script(
        self,
        project_id: str,
        instruction: str,
        target_path: str | None,
    ) -> ScriptEditResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        current_yaml = self._require_current_script(project_id)
        book_index = self._load_book_index(project_id)
        prompt = self._edit_prompt(
            instruction=instruction,
            target_path=target_path,
            current_yaml=current_yaml,
            book_index=book_index,
        )
        plan = await self.agent.plan_yaml_edit(prompt)
        patched_yaml = self._apply_operations(current_yaml, plan.operations)
        report = await self.validate_script(project_id, patched_yaml)
        patched_yaml, report, repair_attempt_count = await self._repair_until_accepted(
            project_id=project_id,
            script_yaml=patched_yaml,
            report=report,
            book_index=book_index,
        )
        accepted_version_id = None
        rejected_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=patched_yaml,
                created_by="agent",
                reason=(
                    instruction
                    if repair_attempt_count == 0
                    else f"{instruction}（自动修复 {repair_attempt_count} 次）"
                ),
                operation_count=len(plan.operations) + repair_attempt_count,
                validation_status=ValidationStatus.accepted,
                validation_report=report.validation_report,
                make_current=True,
            )
        else:
            rejected_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=patched_yaml,
                created_by="agent",
                reason=f"{instruction}（未通过 harness，已自动修复 {repair_attempt_count} 次）",
                operation_count=len(plan.operations) + repair_attempt_count,
                validation_status=ValidationStatus.rejected,
                validation_report=report.validation_report,
                make_current=False,
            )
        return ScriptEditResponse(
            project_id=project_id,
            operations=plan.operations,
            script_yaml=patched_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
            rejected_version_id=rejected_version_id,
            repair_attempt_count=repair_attempt_count,
            validation_status=(
                ValidationStatus.accepted.value
                if report.validation_report.accepted
                else ValidationStatus.rejected.value
            ),
        )

    async def repair_script(
        self,
        project_id: str,
        script_yaml: str,
        validation_report_json: dict,
    ) -> ScriptGenerateResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        book_index = self._load_book_index(project_id)
        repaired_yaml, report, repair_attempt_count = await self._repair_from_report_json(
            project_id=project_id,
            script_yaml=script_yaml,
            validation_report_json=validation_report_json,
            book_index=book_index,
        )
        accepted_version_id = None
        rejected_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=repaired_yaml,
                created_by="agent",
                reason=f"根据 harness 错误修复剧本 YAML（自动修复 {repair_attempt_count} 次）",
                operation_count=repair_attempt_count,
                validation_status=ValidationStatus.accepted,
                validation_report=report.validation_report,
                make_current=True,
            )
        else:
            rejected_version_id = await self._save_script_version(
                project_id=project_id,
                script_yaml=repaired_yaml,
                created_by="agent",
                reason=(
                    "根据 harness 错误修复剧本 YAML 后仍未通过"
                    f"（自动修复 {repair_attempt_count} 次）"
                ),
                operation_count=repair_attempt_count,
                validation_status=ValidationStatus.rejected,
                validation_report=report.validation_report,
                make_current=False,
            )
        return ScriptGenerateResponse(
            project_id=project_id,
            script_yaml=repaired_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
            rejected_version_id=rejected_version_id,
            repair_attempt_count=repair_attempt_count,
            validation_status=(
                ValidationStatus.accepted.value
                if report.validation_report.accepted
                else ValidationStatus.rejected.value
            ),
        )

    async def list_versions(self, project_id: str) -> ScriptVersionListResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        versions = await self.versions.list_by_project(project_id)
        return ScriptVersionListResponse(versions=[self._version_response(v) for v in versions])

    async def get_version(self, project_id: str, version_id: str) -> ScriptVersionDetailResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        version = await self.versions.get(project_id, version_id)
        if version is None:
            raise ScriptVersionNotFoundError(version_id)
        return ScriptVersionDetailResponse(
            version=self._version_response(version),
            script_yaml=self.store.read_text(version.file_path),
        )

    async def restore_version(self, project_id: str, version_id: str) -> ScriptRestoreResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        version = await self.versions.get(project_id, version_id)
        if version is None:
            raise ScriptVersionNotFoundError(version_id)
        script_yaml = self.store.read_text(version.file_path)
        self.store.write_text(self.store.script_path(project_id), script_yaml)
        project.current_script_version_id = version_id
        project.updated_at = datetime.now(UTC)
        await self.session.commit()
        return ScriptRestoreResponse(
            project_id=project_id,
            current_version_id=version_id,
            script_yaml=script_yaml,
        )

    async def export_script_yaml(self, project_id: str) -> ScriptExportResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        script_yaml = self._require_current_script(project_id)
        return ScriptExportResponse(
            project_id=project_id,
            file_name="script.yaml",
            media_type="application/x-yaml",
            content=script_yaml,
        )

    async def export_schema_json(self, project_id: str) -> ScriptExportResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        return ScriptExportResponse(
            project_id=project_id,
            file_name="screenplay-schema.json",
            media_type="application/schema+json",
            content=json.dumps(ScreenplayYaml.model_json_schema(), ensure_ascii=False, indent=2),
        )

    def _load_book_index(self, project_id: str) -> BookIndex | None:
        path = self.store.book_index_path(project_id)
        if not path.exists():
            return None
        return BookIndex.model_validate(self.store.read_json(path))

    def _require_book_index(self, project_id: str) -> BookIndex:
        book_index = self._load_book_index(project_id)
        if book_index is None:
            raise BookIndexRequiredError(project_id)
        return book_index

    def _require_current_script(self, project_id: str) -> str:
        path = self.store.script_path(project_id)
        if not path.exists():
            raise CurrentScriptNotFoundError(project_id)
        return self.store.read_text(path)

    async def _save_script_version(
        self,
        project_id: str,
        script_yaml: str,
        created_by: str,
        reason: str,
        operation_count: int,
        validation_status: ValidationStatus,
        validation_report,
        make_current: bool,
    ) -> str:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        version_id = f"script_v_{uuid4().hex[:12]}"
        version_path = self.store.script_version_path(project_id, version_id)
        if make_current:
            current_path = self.store.script_path(project_id)
            self.store.write_text(current_path, script_yaml)
            project.current_script_version_id = version_id
        self.store.write_text(version_path, script_yaml)
        version = ScriptVersionRecord(
            id=version_id,
            project_id=project_id,
            file_path=str(version_path),
            created_by=created_by,
            reason=reason,
            operation_count=operation_count,
            validation_status=validation_status.value,
        )
        await self.versions.add(version)
        await self._add_validation_report(
            project_id=project_id,
            script_version_id=version_id,
            status=validation_status,
            validation_report=validation_report,
        )
        project.updated_at = datetime.now(UTC)
        await self.session.commit()
        return version_id

    async def _add_validation_report(
        self,
        project_id: str,
        script_version_id: str,
        status: ValidationStatus,
        validation_report,
    ) -> None:
        self.session.add(
            ValidationReportRecord(
                id=f"validation_{uuid4().hex[:12]}",
                project_id=project_id,
                script_version_id=script_version_id,
                status=status.value,
                report_json=validation_report.model_dump(mode="json"),
            )
        )
        await self.session.flush()

    async def _repair_until_accepted(
        self,
        project_id: str,
        script_yaml: str,
        report: ScriptValidateResponse,
        book_index: BookIndex | None,
    ) -> tuple[str, ScriptValidateResponse, int]:
        repair_attempt_count = 0
        current_yaml = script_yaml
        current_report = report
        while (
            not current_report.validation_report.accepted
            and repair_attempt_count < self.settings.script_repair_max_attempts
        ):
            repair_attempt_count += 1
            screenplay = await self.agent.repair_script(
                self._repair_prompt(
                    current_yaml,
                    current_report.validation_report.model_dump(mode="json"),
                    book_index,
                )
            )
            current_yaml = self._dump_screenplay(screenplay)
            current_report = await self.validate_script(project_id, current_yaml)
        return current_yaml, current_report, repair_attempt_count

    async def _repair_from_report_json(
        self,
        project_id: str,
        script_yaml: str,
        validation_report_json: dict,
        book_index: BookIndex | None,
    ) -> tuple[str, ScriptValidateResponse, int]:
        repair_attempt_count = 0
        current_yaml = script_yaml
        current_report_json = validation_report_json
        current_report: ScriptValidateResponse | None = None
        while repair_attempt_count < self.settings.script_repair_max_attempts:
            repair_attempt_count += 1
            screenplay = await self.agent.repair_script(
                self._repair_prompt(current_yaml, current_report_json, book_index)
            )
            current_yaml = self._dump_screenplay(screenplay)
            current_report = await self.validate_script(project_id, current_yaml)
            if current_report.validation_report.accepted:
                break
            current_report_json = current_report.validation_report.model_dump(mode="json")
        if current_report is None:
            current_report = await self.validate_script(project_id, current_yaml)
        return current_yaml, current_report, repair_attempt_count

    def _dump_screenplay(self, screenplay: ScreenplayYaml) -> str:
        return yaml.safe_dump(
            screenplay.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        )

    def _apply_operations(
        self,
        current_yaml: str,
        operations: list[YamlPatchOperation],
    ) -> str:
        return self.yaml_patches.apply(current_yaml, operations)

    def _version_response(self, version: ScriptVersionRecord) -> ScriptVersionResponse:
        return ScriptVersionResponse(
            id=version.id,
            project_id=version.project_id,
            file_path=version.file_path,
            created_by=version.created_by,
            reason=version.reason,
            operation_count=version.operation_count,
            validation_status=version.validation_status,
            created_at=version.created_at,
        )

    def _script_generation_prompt(
        self,
        project_id: str,
        project_title: str,
        book_index: BookIndex,
        chapters: list[dict],
    ) -> str:
        chapter_blocks = []
        for chapter in chapters:
            chapter_blocks.append(
                "\n".join(
                    [
                        f"章节 ID：{chapter['id']}",
                        f"章节标题：{chapter['title']}",
                        "章节正文：",
                        chapter["content"],
                    ]
                )
            )
        return "\n\n".join(
            [
                "请基于 book_index.json 和原文章节生成完整 script.yaml。",
                f"项目 ID：{project_id}",
                f"项目标题：{project_title}",
                "必须使用输入中的 chapter_id 作为 source_refs.chapter_id。",
                "每个 scene 必须包含 adaptation_notes。",
                "book_index.json：",
                book_index.model_dump_json(indent=2),
                "原文章节：",
                "\n\n---\n\n".join(chapter_blocks),
            ]
        )

    def _edit_prompt(
        self,
        instruction: str,
        target_path: str | None,
        current_yaml: str,
        book_index: BookIndex | None,
    ) -> str:
        return "\n\n".join(
            [
                "请根据用户指令生成 YAML patch operations，不要直接重写全部剧本。",
                f"用户指令：{instruction}",
                f"目标路径：{target_path or '未指定'}",
                "当前 script.yaml：",
                current_yaml,
                "book_index.json：",
                book_index.model_dump_json(indent=2) if book_index else "未生成",
            ]
        )

    def _repair_prompt(
        self,
        script_yaml: str,
        validation_report_json: dict,
        book_index: BookIndex | None,
    ) -> str:
        return "\n\n".join(
            [
                "请根据 harness 错误修复以下剧本 YAML，只输出符合 ScreenplayYaml 模型的结果。",
                "原始 script.yaml：",
                script_yaml,
                "harness errors：",
                str(validation_report_json),
                "book_index.json：",
                book_index.model_dump_json(indent=2) if book_index else "未生成",
            ]
        )
