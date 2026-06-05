from typing import Literal

from pydantic import BaseModel, Field


class YamlPatchOperation(BaseModel):
    type: Literal[
        "replace_script",
        "patch_scene",
        "replace_scene",
        "insert_event",
        "patch_event",
        "delete_event",
        "repair_validation_errors",
    ] = Field(..., description="结构化 YAML 操作类型。")
    target_path: str = Field(
        ...,
        description=(
            "稳定目标路径，例如 scenes.scene_001、"
            "scenes.scene_001.events 或 scenes.scene_001.events.event_001。"
        ),
    )
    reason: str = Field(..., description="中文修改原因。")
    payload: dict = Field(default_factory=dict, description="操作载荷。")


class YamlPatchPlan(BaseModel):
    operations: list[YamlPatchOperation] = Field(..., description="需要应用的 YAML patch 操作。")
