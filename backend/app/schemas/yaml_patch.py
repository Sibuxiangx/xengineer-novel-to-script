from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, Field

YamlOperationType: TypeAlias = Literal[
    "create_script",
    "replace_script",
    "patch_project",
    "upsert_character",
    "delete_character",
    "merge_characters",
    "upsert_location",
    "delete_location",
    "upsert_act",
    "delete_act",
    "insert_scene",
    "replace_scene",
    "patch_scene",
    "delete_scene",
    "reorder_scenes",
    "insert_event",
    "replace_event",
    "patch_event",
    "delete_event",
    "reorder_events",
    "patch_adaptation_notes",
    "repair_validation_errors",
]


class YamlPatchOperation(BaseModel):
    type: YamlOperationType = Field(..., description="结构化 YAML 操作类型。")
    target_path: str = Field(
        ...,
        description=(
            "稳定目标路径，例如 scenes.scene_001、"
            "scenes.scene_001.events 或 scenes.scene_001.events.event_001。"
        ),
    )
    reason: str = Field(..., description="中文修改原因。")
    payload: dict[str, Any] = Field(default_factory=dict, description="操作载荷。")


class YamlPatchPlan(BaseModel):
    operations: list[YamlPatchOperation] = Field(..., description="需要应用的 YAML patch 操作。")
