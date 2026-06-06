from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.api.models.common import ValidationIssueResponse, ValidationReportResponse
from app.schemas.book_index import BookIndex
from app.schemas.screenplay import EventType, ScreenplayYaml


class ValidationIssue(BaseModel):
    code: str = Field(..., description="Stable validation issue code.")
    severity: Literal["info", "warning", "error", "blocking"] = Field(
        ...,
        description="Issue severity.",
    )
    path: str = Field(..., description="YAML path associated with the issue.")
    message: str = Field(..., description="Human-readable validation message.")
    repair_hint: str | None = Field(default=None, description="Optional repair guidance.")
    source: Literal["yaml_parse", "schema", "reference", "book_index", "policy", "export"] = Field(
        ...,
        description="Validation source category.",
    )


class ValidationReport(BaseModel):
    accepted: bool = Field(..., description="Whether the YAML can be accepted.")
    errors: list[ValidationIssue] = Field(default_factory=list, description="Blocking issues.")
    warnings: list[ValidationIssue] = Field(
        default_factory=list,
        description="Non-blocking issues.",
    )
    metrics: dict[str, int | float | str] = Field(
        default_factory=dict,
        description="Validation metrics.",
    )

    def to_response(self) -> ValidationReportResponse:
        severity: Literal["info", "warning", "error", "blocking"] = "info"
        if self.errors:
            severity = (
                "blocking"
                if any(issue.severity == "blocking" for issue in self.errors)
                else "error"
            )
        elif self.warnings:
            severity = "warning"
        return ValidationReportResponse(
            accepted=self.accepted,
            severity=severity,
            errors=[
                ValidationIssueResponse.model_validate(issue.model_dump())
                for issue in self.errors
            ],
            warnings=[
                ValidationIssueResponse.model_validate(issue.model_dump())
                for issue in self.warnings
            ],
            metrics=self.metrics,
        )


class ValidationService:
    """Boundary for script YAML validation."""

    async def accept_empty_scaffold(self) -> ValidationReport:
        return ValidationReport(accepted=True)

    def validate_script_yaml(
        self,
        script_yaml: str,
        chapter_ids: set[str],
        book_index: BookIndex | None = None,
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        try:
            raw = yaml.safe_load(script_yaml)
        except yaml.YAMLError as exc:
            return ValidationReport(
                accepted=False,
                errors=[
                    self._issue(
                        code="yaml_parse_error",
                        severity="blocking",
                        path="$",
                        message=f"YAML 无法解析：{exc}",
                        repair_hint="请修复 YAML 缩进、引号或列表结构。",
                        source="yaml_parse",
                    )
                ],
            )

        if not isinstance(raw, dict):
            return ValidationReport(
                accepted=False,
                errors=[
                    self._issue(
                        code="yaml_root_not_mapping",
                        severity="blocking",
                        path="$",
                        message="YAML 根节点必须是对象。",
                        repair_hint=(
                            "请输出包含 schema_version、project、characters、"
                            "locations、scenes 的对象。"
                        ),
                        source="schema",
                    )
                ],
            )

        try:
            script = ScreenplayYaml.model_validate(raw)
        except ValidationError as exc:
            for error in exc.errors():
                path = ".".join(str(part) for part in error["loc"])
                errors.append(
                    self._issue(
                        code="schema_validation_error",
                        severity="error",
                        path=path or "$",
                        message=str(error["msg"]),
                        repair_hint="请按剧本 YAML Schema 补充或修正该字段。",
                        source="schema",
                    )
                )
            return ValidationReport(accepted=False, errors=errors)

        self._validate_references(script, chapter_ids, errors, warnings)
        if book_index is not None:
            self._validate_against_book_index(script, book_index, warnings)

        metrics: dict[str, int | float | str] = {
            "scene_count": len(script.scenes),
            "character_count": len(script.characters),
            "location_count": len(script.locations),
            "event_count": sum(len(scene.events) for scene in script.scenes),
        }
        return ValidationReport(
            accepted=not errors,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
        )

    def _validate_references(
        self,
        script: ScreenplayYaml,
        chapter_ids: set[str],
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        character_ids = [character.id for character in script.characters]
        location_ids = [location.id for location in script.locations]
        scene_ids = [scene.id for scene in script.scenes]
        event_ids = [event.id for scene in script.scenes for event in scene.events]

        self._check_duplicates("characters", character_ids, errors)
        self._check_duplicates("locations", location_ids, errors)
        self._check_duplicates("scenes", scene_ids, errors)
        self._check_duplicates("events", event_ids, errors)

        character_set = set(character_ids)
        location_set = set(location_ids)
        for scene in script.scenes:
            if scene.setting.location_id not in location_set:
                errors.append(
                    self._issue(
                        code="undefined_location",
                        severity="error",
                        path=f"scenes.{scene.id}.setting.location_id",
                        message=f"场景引用了未定义地点：{scene.setting.location_id}",
                        repair_hint="请在 locations 中定义该地点，或改用已有 location_id。",
                        source="reference",
                    )
                )
            if scene.adaptation_notes is None:
                errors.append(
                    self._issue(
                        code="missing_adaptation_notes",
                        severity="error",
                        path=f"scenes.{scene.id}.adaptation_notes",
                        message="每个场景必须说明改编意图。",
                        repair_hint="请补充 adaptation_notes.intent 和必要的删改说明。",
                        source="policy",
                    )
                )
            for ref in scene.source_refs:
                if chapter_ids and ref.chapter_id not in chapter_ids:
                    errors.append(
                        self._issue(
                            code="undefined_source_chapter",
                            severity="error",
                            path=f"scenes.{scene.id}.source_refs",
                            message=f"场景引用了不存在的章节：{ref.chapter_id}",
                            repair_hint="请改用已导入章节 ID。",
                            source="reference",
                        )
                    )
            for event in scene.events:
                if event.type == EventType.dialogue and not event.character_id:
                    errors.append(
                        self._issue(
                            code="dialogue_missing_character",
                            severity="error",
                            path=f"scenes.{scene.id}.events.{event.id}.character_id",
                            message="对白事件必须引用 character_id。",
                            repair_hint="请为该对白指定已定义人物 ID。",
                            source="schema",
                        )
                    )
                if event.character_id and event.character_id not in character_set:
                    errors.append(
                        self._issue(
                            code="undefined_character",
                            severity="error",
                            path=f"scenes.{scene.id}.events.{event.id}.character_id",
                            message=f"事件引用了未定义人物：{event.character_id}",
                            repair_hint="请在 characters 中定义该人物，或改用已有 character_id。",
                            source="reference",
                        )
                    )
        if not script.scenes:
            errors.append(
                self._issue(
                    code="empty_scenes",
                    severity="blocking",
                    path="scenes",
                    message="剧本必须至少包含一个场景。",
                    repair_hint="请生成至少一个 scene。",
                    source="schema",
                )
            )
        if len(script.scenes) < len(chapter_ids):
            warnings.append(
                self._issue(
                    code="low_scene_coverage",
                    severity="warning",
                    path="scenes",
                    message="场景数量少于导入章节数量，可能存在压缩或遗漏。",
                    repair_hint="请确认 adaptation_notes 是否解释了章节压缩策略。",
                    source="book_index",
                )
            )

    def _validate_against_book_index(
        self,
        script: ScreenplayYaml,
        book_index: BookIndex,
        warnings: list[ValidationIssue],
    ) -> None:
        indexed_characters = {character.id for character in book_index.characters}
        script_characters = {character.id for character in script.characters}
        missing = sorted(indexed_characters - script_characters)
        if missing:
            warnings.append(
                self._issue(
                    code="indexed_characters_missing_from_script",
                    severity="warning",
                    path="characters",
                    message=f"剧本未包含索引中的人物：{', '.join(missing)}",
                    repair_hint="请确认这些人物是否被合理删减，并在 adaptation_notes 中说明。",
                    source="book_index",
                )
            )

    def _check_duplicates(
        self,
        group: str,
        values: list[str],
        errors: list[ValidationIssue],
    ) -> None:
        seen: set[str] = set()
        duplicated: set[str] = set()
        for value in values:
            if value in seen:
                duplicated.add(value)
            seen.add(value)
        for value in sorted(duplicated):
            errors.append(
                self._issue(
                    code="duplicate_id",
                    severity="error",
                    path=group,
                    message=f"{group} 中存在重复 ID：{value}",
                    repair_hint="请保持每个 ID 唯一。",
                    source="reference",
                )
            )

    def _issue(
        self,
        code: str,
        severity: Literal["info", "warning", "error", "blocking"],
        path: str,
        message: str,
        repair_hint: str | None,
        source: Literal["yaml_parse", "schema", "reference", "book_index", "policy", "export"],
    ) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            severity=severity,
            path=path,
            message=message,
            repair_hint=repair_hint,
            source=source,
        )
