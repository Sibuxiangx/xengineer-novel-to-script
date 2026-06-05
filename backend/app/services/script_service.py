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
from app.db.models import ScriptVersionRecord, ValidationStatus
from app.db.repositories.chapters import ChapterRepository
from app.db.repositories.projects import ProjectRepository
from app.db.repositories.script_versions import ScriptVersionRepository
from app.schemas.book_index import BookIndex
from app.schemas.screenplay import ScreenplayYaml
from app.schemas.yaml_patch import YamlPatchOperation
from app.services.validation_service import ValidationService
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
        accepted_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_accepted_version(
                project_id=project_id,
                script_yaml=script_yaml,
                created_by="agent",
                reason="生成初版剧本 YAML",
                operation_count=0,
            )
        return ScriptGenerateResponse(
            project_id=project_id,
            script_yaml=script_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
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
        accepted_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_accepted_version(
                project_id=project_id,
                script_yaml=patched_yaml,
                created_by="agent",
                reason=instruction,
                operation_count=len(plan.operations),
            )
        return ScriptEditResponse(
            project_id=project_id,
            operations=plan.operations,
            script_yaml=patched_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
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
        prompt = self._repair_prompt(script_yaml, validation_report_json, book_index)
        screenplay = await self.agent.repair_script(prompt)
        repaired_yaml = self._dump_screenplay(screenplay)
        report = await self.validate_script(project_id, repaired_yaml)
        accepted_version_id = None
        if report.validation_report.accepted:
            accepted_version_id = await self._save_accepted_version(
                project_id=project_id,
                script_yaml=repaired_yaml,
                created_by="agent",
                reason="根据 harness 错误修复剧本 YAML",
                operation_count=1,
            )
        return ScriptGenerateResponse(
            project_id=project_id,
            script_yaml=repaired_yaml,
            validation_report=report.validation_report,
            accepted_version_id=accepted_version_id,
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

    async def _save_accepted_version(
        self,
        project_id: str,
        script_yaml: str,
        created_by: str,
        reason: str,
        operation_count: int,
    ) -> str:
        project = await self.projects.get(project_id)
        if project is None:
            raise ScriptServiceProjectNotFoundError(project_id)
        version_id = f"script_v_{uuid4().hex[:12]}"
        current_path = self.store.script_path(project_id)
        version_path = self.store.script_version_path(project_id, version_id)
        self.store.write_text(current_path, script_yaml)
        self.store.write_text(version_path, script_yaml)
        version = ScriptVersionRecord(
            id=version_id,
            project_id=project_id,
            file_path=str(version_path),
            created_by=created_by,
            reason=reason,
            operation_count=operation_count,
            validation_status=ValidationStatus.accepted.value,
        )
        await self.versions.add(version)
        project.current_script_version_id = version_id
        project.updated_at = datetime.now(UTC)
        await self.session.commit()
        return version_id

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
        document = yaml.safe_load(current_yaml)
        if not isinstance(document, dict):
            raise ScriptValidationRejectedError("Current script YAML is not a mapping.")
        for operation in operations:
            document = self._apply_operation(document, operation)
        return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)

    def _apply_operation(self, document: dict, operation: YamlPatchOperation) -> dict:
        if operation.type == "replace_script":
            script = operation.payload.get("script")
            if not isinstance(script, dict):
                raise ScriptValidationRejectedError(
                    "replace_script payload.script must be an object."
                )
            return script
        if operation.type in {"patch_scene", "replace_scene"}:
            scene = self._find_by_path(document, operation.target_path, group="scenes")
            if operation.type == "replace_scene":
                replacement = operation.payload.get("scene")
                if not isinstance(replacement, dict):
                    raise ScriptValidationRejectedError(
                        "replace_scene payload.scene must be an object."
                    )
                scenes = document.get("scenes", [])
                for index, item in enumerate(scenes):
                    if item.get("id") == scene.get("id"):
                        scenes[index] = replacement
                        break
            else:
                self._deep_update(scene, operation.payload)
            return document
        if operation.type in {"insert_event", "patch_event", "delete_event"}:
            return self._apply_event_operation(document, operation)
        if operation.type == "repair_validation_errors":
            return document
        return document

    def _apply_event_operation(self, document: dict, operation: YamlPatchOperation) -> dict:
        if operation.type == "insert_event":
            scene_id = self._parse_event_collection_path(operation.target_path)
            scene = self._find_by_id(document.get("scenes", []), scene_id, "scene")
            events = scene.setdefault("events", [])
            event = operation.payload.get("event")
            if not isinstance(event, dict):
                raise ScriptValidationRejectedError("insert_event payload.event must be an object.")
            insert_after = operation.payload.get("insert_after_event_id")
            if isinstance(insert_after, str):
                for index, item in enumerate(events):
                    if item.get("id") == insert_after:
                        events.insert(index + 1, event)
                        return document
            events.append(event)
            return document

        scene_id, event_id = self._parse_event_path(operation.target_path)
        scene = self._find_by_id(document.get("scenes", []), scene_id, "scene")
        events = scene.setdefault("events", [])
        event = self._find_by_id(events, event_id, "event")
        if operation.type == "delete_event":
            scene["events"] = [item for item in events if item.get("id") != event_id]
        elif operation.type == "patch_event":
            self._deep_update(event, operation.payload)
        return document

    def _find_by_path(self, document: dict, target_path: str, group: str) -> dict:
        parts = target_path.split(".")
        if len(parts) < 2 or parts[0] != group:
            raise ScriptValidationRejectedError(f"Unsupported target path: {target_path}")
        return self._find_by_id(document.get(group, []), parts[1], group)

    def _parse_event_path(self, target_path: str) -> tuple[str, str]:
        parts = target_path.split(".")
        if len(parts) != 4 or parts[0] != "scenes" or parts[2] != "events":
            raise ScriptValidationRejectedError(f"Unsupported event target path: {target_path}")
        return parts[1], parts[3]

    def _parse_event_collection_path(self, target_path: str) -> str:
        parts = target_path.split(".")
        if len(parts) not in {3, 4} or parts[0] != "scenes" or parts[2] != "events":
            raise ScriptValidationRejectedError(f"Unsupported event collection path: {target_path}")
        return parts[1]

    def _find_by_id(self, items: list[dict], item_id: str, group: str) -> dict:
        for item in items:
            if item.get("id") == item_id:
                return item
        raise ScriptValidationRejectedError(f"{group} not found: {item_id}")

    def _deep_update(self, target: dict, patch: dict) -> None:
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_update(target[key], value)
            else:
                target[key] = value

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
