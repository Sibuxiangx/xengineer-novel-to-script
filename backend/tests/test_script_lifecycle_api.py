import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.book_index import get_screenplay_agent as get_book_index_agent
from app.api.routes.scripts import get_script_agent
from app.main import app
from app.schemas.book_index import BookIndex, IndexedChapter, IndexedCharacter, IndexedEvent
from app.schemas.screenplay import (
    AdaptationNotes,
    Character,
    Location,
    ProjectMetadata,
    Scene,
    SceneSetting,
    ScreenplayFormat,
    ScreenplayYaml,
    ScriptEvent,
)
from app.schemas.yaml_patch import YamlPatchOperation, YamlPatchPlan

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"


def _extract_chapter_id(prompt: str) -> str:
    explicit = re.search(r"章节 ID：([^\n]+)", prompt)
    if explicit:
        return explicit.group(1).strip()
    yaml_ref = re.search(r"chapter_id:\s*[\"']?([A-Za-z0-9_-]+)", prompt)
    if yaml_ref:
        return yaml_ref.group(1).strip()
    raise AssertionError("Fake agent prompt did not include a chapter ID.")


def _make_book_index(prompt: str) -> BookIndex:
    chapter_id = _extract_chapter_id(prompt)
    return BookIndex(
        book_id="proj_lifecycle",
        title="五章长篇",
        chapter_count=1,
        chapters=[
            IndexedChapter(
                id=chapter_id,
                title="第一章",
                order=1,
                summary="林栩收到旧剧本并进入废弃剧院。",
                events=[
                    IndexedEvent(
                        id="event_index_001",
                        summary="旧剧本揭开导师失踪线索。",
                        importance="major",
                    )
                ],
            )
        ],
        characters=[
            IndexedCharacter(
                id="char_lin",
                names=["林栩"],
                role="protagonist",
                description="追查旧剧本真相的编剧。",
            )
        ],
    )


def _make_screenplay(chapter_id: str, conflict: str = "林栩想查清剧本来源。") -> ScreenplayYaml:
    return ScreenplayYaml(
        schema_version="1.0",
        project=ProjectMetadata(
            title="五章长篇改编",
            genre=["悬疑"],
            format=ScreenplayFormat.short_drama,
            logline="编剧追查旧剧本背后的真相。",
        ),
        characters=[
            Character(
                id="char_lin",
                name="林栩",
                role="protagonist",
                description="追查旧剧本真相的编剧。",
            )
        ],
        locations=[
            Location(
                id="loc_theater",
                name="白鸽剧院",
                description="废弃剧院。",
            )
        ],
        scenes=[
            Scene(
                id="scene_001",
                title="旧剧本出现",
                source_refs=[
                    {
                        "chapter_id": chapter_id,
                        "range_hint": "开头至收到戏票",
                        "usage": "adapted",
                    }
                ],
                setting=SceneSetting(
                    location_id="loc_theater",
                    time_of_day="night",
                    atmosphere="潮湿、紧张",
                ),
                dramatic_purpose="建立主角目标。",
                conflict=conflict,
                events=[
                    ScriptEvent(
                        id="event_001",
                        type="action",
                        content="林栩翻开旧剧本。",
                    ),
                    ScriptEvent(
                        id="event_002",
                        type="dialogue",
                        character_id="char_lin",
                        content="这不是我写的结局。",
                    ),
                ],
                adaptation_notes=AdaptationNotes(
                    intent="把原文悬疑线索改成可表演的场景。",
                    omitted_or_changed=[],
                ),
            )
        ],
    )


class FakeLifecycleAgent:
    async def build_book_index(self, prompt: str) -> BookIndex:
        assert "章节内容如下" in prompt
        return _make_book_index(prompt)

    async def generate_script(self, prompt: str) -> ScreenplayYaml:
        assert "生成完整 script.yaml" in prompt
        return _make_screenplay(_extract_chapter_id(prompt))

    async def plan_yaml_edit(self, prompt: str) -> YamlPatchPlan:
        assert "YAML patch operations" in prompt
        return YamlPatchPlan(
            operations=[
                YamlPatchOperation(
                    type="patch_scene",
                    target_path="scenes.scene_001",
                    reason="强化冲突",
                    payload={"conflict": "林栩必须在天亮前确认导师是否仍然活着。"},
                ),
                YamlPatchOperation(
                    type="insert_event",
                    target_path="scenes.scene_001.events",
                    reason="补充可表演动作",
                    payload={
                        "insert_after_event_id": "event_001",
                        "event": {
                            "id": "event_003",
                            "type": "stage_direction",
                            "content": "剧院灯牌忽明忽暗，林栩听见后台传来脚步声。",
                        },
                    },
                )
            ]
        )

    async def repair_script(self, prompt: str) -> ScreenplayYaml:
        assert "harness errors" in prompt
        return _make_screenplay(
            _extract_chapter_id(prompt),
            conflict="林栩修复线索链并重新锁定导师留下的暗号。",
        )


def create_project_with_imported_txt(client: TestClient) -> tuple[str, list[dict]]:
    project_response = client.post(
        "/projects",
        json={"title": "五章长篇", "screenplay_format": "short_drama"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")
    import_response = client.post(
        f"/projects/{project_id}/ebook/import-txt",
        json={
            "file_name": "long_chaptered.txt",
            "content": content,
            "split_strategy": "auto",
        },
    )
    assert import_response.status_code == 201
    return project_id, import_response.json()["chapters"]


def test_script_generation_requires_book_index() -> None:
    app.dependency_overrides[get_script_agent] = lambda: FakeLifecycleAgent()
    try:
        with TestClient(app) as client:
            project_id, _ = create_project_with_imported_txt(client)

            response = client.post(
                f"/projects/{project_id}/scripts/generate",
                json={"force_regenerate": True},
            )

            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "book_index_required"
    finally:
        app.dependency_overrides.clear()


def test_script_generation_edit_repair_version_and_export_flow() -> None:
    fake_agent = FakeLifecycleAgent()
    app.dependency_overrides[get_book_index_agent] = lambda: fake_agent
    app.dependency_overrides[get_script_agent] = lambda: fake_agent
    try:
        with TestClient(app) as client:
            project_id, _ = create_project_with_imported_txt(client)
            index_response = client.post(
                f"/projects/{project_id}/book-index",
                json={"force_rebuild": True},
            )
            assert index_response.status_code == 201

            generate_response = client.post(
                f"/projects/{project_id}/scripts/generate",
                json={"force_regenerate": True},
            )
            assert generate_response.status_code == 201
            generated = generate_response.json()
            assert generated["validation_report"]["accepted"] is True
            first_version_id = generated["accepted_version_id"]
            assert first_version_id
            assert "旧剧本出现" in generated["script_yaml"]

            edit_response = client.post(
                f"/projects/{project_id}/scripts/edit",
                json={
                    "instruction": "强化第一场冲突",
                    "target_path": "scenes.scene_001",
                },
            )
            assert edit_response.status_code == 200
            edited = edit_response.json()
            assert edited["accepted_version_id"] != first_version_id
            assert edited["operations"][0]["type"] == "patch_scene"
            assert "天亮前确认导师" in edited["script_yaml"]
            assert "后台传来脚步声" in edited["script_yaml"]

            versions_response = client.get(f"/projects/{project_id}/scripts/versions")
            assert versions_response.status_code == 200
            versions = versions_response.json()["versions"]
            assert len(versions) == 2

            first_version_response = client.get(
                f"/projects/{project_id}/scripts/versions/{first_version_id}"
            )
            assert first_version_response.status_code == 200
            assert "想查清剧本来源" in first_version_response.json()["script_yaml"]

            export_response = client.get(f"/projects/{project_id}/scripts/exports/script.yaml")
            assert export_response.status_code == 200
            assert export_response.json()["file_name"] == "script.yaml"
            assert "天亮前确认导师" in export_response.json()["content"]

            bad_yaml = generated["script_yaml"].replace("character_id: char_lin", "", 1)
            validation_response = client.post(
                f"/projects/{project_id}/scripts/validate",
                json={"script_yaml": bad_yaml},
            )
            assert validation_response.status_code == 200
            assert validation_response.json()["validation_report"]["accepted"] is False

            repair_response = client.post(
                f"/projects/{project_id}/scripts/repair",
                json={
                    "script_yaml": bad_yaml,
                    "validation_report": validation_response.json()["validation_report"],
                },
            )
            assert repair_response.status_code == 200
            assert repair_response.json()["validation_report"]["accepted"] is True
            assert "重新锁定导师" in repair_response.json()["script_yaml"]

            restore_response = client.post(
                f"/projects/{project_id}/scripts/versions/{first_version_id}/restore"
            )
            assert restore_response.status_code == 200
            assert restore_response.json()["current_version_id"] == first_version_id

            schema_response = client.get(
                f"/projects/{project_id}/scripts/exports/screenplay-schema.json"
            )
            assert schema_response.status_code == 200
            assert schema_response.json()["file_name"] == "screenplay-schema.json"
            assert '"ScreenplayYaml"' in schema_response.json()["content"]
    finally:
        app.dependency_overrides.clear()


def test_script_lifecycle_routes_are_documented_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    generate_route = schema["paths"]["/projects/{project_id}/scripts/generate"]["post"]
    edit_route = schema["paths"]["/projects/{project_id}/scripts/edit"]["post"]
    versions_route = schema["paths"]["/projects/{project_id}/scripts/versions"]["get"]
    assert generate_route["summary"] == "Generate screenplay YAML"
    assert "ScriptGenerateRequest" in str(generate_route["requestBody"])
    assert edit_route["summary"] == "Edit screenplay YAML"
    assert versions_route["summary"] == "List accepted screenplay versions"
