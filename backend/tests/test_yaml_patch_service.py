import pytest
import yaml

from app.schemas.yaml_patch import YamlPatchOperation
from app.services.yaml_patch_service import (
    UnsupportedYamlOperationError,
    YamlPatchApplier,
    YamlPatchNoChangeError,
    YamlPatchPayloadError,
)

BASE_SCRIPT_YAML = """
schema_version: "1.0"
project:
  title: 雾港来信
  genre:
    - 悬疑
  format: short_drama
  logline: 编剧追查旧信背后的剧场秘密。
characters:
  - id: char_lin
    name: 林栩
    role: protagonist
    description: 追查旧信来源的编剧。
locations:
  - id: loc_theater
    name: 雾港剧场
    description: 被雨声包围的旧剧场。
scenes:
  - id: scene_001
    title: 旧信抵达
    source_refs:
      - chapter_id: chapter_001
        range_hint: 章节开头
        usage: adapted
    setting:
      location_id: loc_theater
      time_of_day: night
      atmosphere: 潮湿、压迫
    dramatic_purpose: 建立主角目标。
    conflict: 林栩必须确认旧信是谁寄来的。
    events:
      - id: event_001
        type: action
        content: 林栩拆开旧信。
      - id: event_002
        type: dialogue
        character_id: char_lin
        content: 这封信不该在今天出现。
    adaptation_notes:
      intent: 把小说线索转换为可表演场景。
      omitted_or_changed: []
"""


def apply_operations(operations: list[YamlPatchOperation]) -> dict:
    patched = YamlPatchApplier().apply(BASE_SCRIPT_YAML, operations)
    loaded = yaml.safe_load(patched)
    assert isinstance(loaded, dict)
    return loaded


def test_yaml_patch_applier_updates_project_entities_scene_events_and_notes() -> None:
    document = apply_operations(
        [
            YamlPatchOperation(
                type="patch_project",
                target_path="project",
                reason="补充目标观众和风格。",
                payload={"target_audience": "悬疑短剧观众", "tone": "冷峻"},
            ),
            YamlPatchOperation(
                type="upsert_character",
                target_path="characters.char_chen",
                reason="新增调查搭档。",
                payload={
                    "character": {
                        "id": "char_chen",
                        "name": "陈砚",
                        "role": "supporting",
                        "description": "熟悉旧剧场档案的记者。",
                    }
                },
            ),
            YamlPatchOperation(
                type="upsert_location",
                target_path="locations.loc_archive",
                reason="新增档案室地点。",
                payload={
                    "location": {
                        "id": "loc_archive",
                        "name": "剧场档案室",
                        "description": "堆满旧海报和报纸剪贴的窄房间。",
                    }
                },
            ),
            YamlPatchOperation(
                type="patch_scene",
                target_path="scenes.scene_001",
                reason="强化场景冲突。",
                payload={"conflict": "林栩必须在记者到来前判断旧信是否是陷阱。"},
            ),
            YamlPatchOperation(
                type="insert_event",
                target_path="scenes.scene_001.events.event_001",
                reason="补入外部压力。",
                payload={
                    "event": {
                        "id": "event_003",
                        "type": "sound",
                        "content": "门外响起急促敲门声。",
                    }
                },
            ),
            YamlPatchOperation(
                type="replace_event",
                target_path="scenes.scene_001.events.event_003",
                reason="让声音事件更明确。",
                payload={
                    "event": {
                        "id": "event_003",
                        "type": "sound",
                        "content": "门外响起三下急促敲门声，随后雨声突然停住。",
                    }
                },
            ),
            YamlPatchOperation(
                type="reorder_events",
                target_path="scenes.scene_001.events",
                reason="先听见声音，再出现对白。",
                payload={"ordered_event_ids": ["event_001", "event_003", "event_002"]},
            ),
            YamlPatchOperation(
                type="patch_adaptation_notes",
                target_path="scenes.scene_001.adaptation_notes",
                reason="说明新增悬疑压力。",
                payload={"risks": ["新增敲门声可能改变小说原本的安静氛围。"]},
            ),
        ]
    )

    assert document["project"]["tone"] == "冷峻"
    assert document["characters"][-1]["id"] == "char_chen"
    assert document["locations"][-1]["id"] == "loc_archive"
    scene = document["scenes"][0]
    assert scene["conflict"] == "林栩必须在记者到来前判断旧信是否是陷阱。"
    assert [event["id"] for event in scene["events"]] == [
        "event_001",
        "event_003",
        "event_002",
    ]
    assert scene["events"][1]["content"].endswith("雨声突然停住。")
    assert scene["adaptation_notes"]["risks"] == ["新增敲门声可能改变小说原本的安静氛围。"]


def test_yaml_patch_applier_inserts_deletes_and_reorders_scenes() -> None:
    document = apply_operations(
        [
            YamlPatchOperation(
                type="insert_scene",
                target_path="scenes.scene_001",
                reason="新增档案室场景。",
                payload={
                    "scene": {
                        "id": "scene_002",
                        "title": "档案室剪报",
                        "source_refs": [
                            {
                                "chapter_id": "chapter_001",
                                "range_hint": "旧信之后",
                                "usage": "inferred",
                            }
                        ],
                        "setting": {
                            "location_id": "loc_theater",
                            "time_of_day": "night",
                            "atmosphere": "逼仄",
                        },
                        "dramatic_purpose": "放大旧剧场秘密。",
                        "conflict": "林栩发现剪报缺失关键日期。",
                        "events": [
                            {
                                "id": "event_004",
                                "type": "action",
                                "content": "林栩翻出一叠受潮剪报。",
                            }
                        ],
                        "adaptation_notes": {
                            "intent": "把小说内心推理外化为动作。",
                            "omitted_or_changed": [],
                        },
                    }
                },
            ),
            YamlPatchOperation(
                type="reorder_scenes",
                target_path="scenes",
                reason="把新场景提前。",
                payload={"ordered_scene_ids": ["scene_002", "scene_001"]},
            ),
            YamlPatchOperation(
                type="delete_scene",
                target_path="scenes.scene_001",
                reason="删除原始开场，仅保留档案室版本。",
                payload={},
            ),
        ]
    )

    assert [scene["id"] for scene in document["scenes"]] == ["scene_002"]
    assert document["scenes"][0]["title"] == "档案室剪报"


def test_yaml_patch_applier_rejects_unsupported_and_unknown_operations() -> None:
    with pytest.raises(UnsupportedYamlOperationError, match="upsert_act"):
        apply_operations(
            [
                YamlPatchOperation(
                    type="upsert_act",
                    target_path="acts.act_001",
                    reason="当前 Schema 暂不支持幕结构。",
                    payload={"act": {"id": "act_001", "title": "第一幕"}},
                )
            ]
        )

    unknown = YamlPatchOperation.model_construct(
        type="unknown_operation",
        target_path="project",
        reason="模拟模型吐出未知操作。",
        payload={},
    )
    with pytest.raises(UnsupportedYamlOperationError, match="unknown_operation"):
        apply_operations([unknown])


def test_yaml_patch_applier_rejects_no_change_patch() -> None:
    with pytest.raises(YamlPatchNoChangeError, match="did not change"):
        apply_operations(
            [
                YamlPatchOperation(
                    type="patch_project",
                    target_path="project",
                    reason="重复设置相同标题。",
                    payload={"title": "雾港来信"},
                )
            ]
        )


def test_yaml_patch_applier_rejects_incomplete_reorder_payload() -> None:
    with pytest.raises(YamlPatchPayloadError, match="every existing event id"):
        apply_operations(
            [
                YamlPatchOperation(
                    type="reorder_events",
                    target_path="scenes.scene_001.events",
                    reason="遗漏一个事件 ID。",
                    payload={"ordered_event_ids": ["event_002"]},
                )
            ]
        )
