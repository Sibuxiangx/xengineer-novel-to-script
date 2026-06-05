from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.book_index import get_screenplay_agent
from app.main import app
from app.schemas.book_index import BookIndex, IndexedChapter, IndexedCharacter, IndexedEvent

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"


class FakeBookIndexAgent:
    async def build_book_index(self, prompt: str) -> BookIndex:
        assert "章节内容如下" in prompt
        return BookIndex(
            schema_version="1.0",
            book_id="proj_test",
            title="五章长篇",
            language="zh-CN",
            chapter_count=2,
            chapters=[
                IndexedChapter(
                    id="chapter_placeholder_001",
                    title="第一章",
                    order=1,
                    summary="主角收到旧剧本。",
                    events=[
                        IndexedEvent(
                            id="event_001",
                            summary="主角发现剧本。",
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


def create_project_with_long_txt(client: TestClient) -> tuple[str, list[dict]]:
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


def sample_valid_yaml(chapter_id: str) -> str:
    return f"""
schema_version: "1.0"
project:
  title: "五章长篇改编"
  genre: ["悬疑"]
  format: "short_drama"
  logline: "编剧追查旧剧本背后的真相。"
characters:
  - id: "char_lin"
    name: "林栩"
    role: "protagonist"
    description: "追查旧剧本真相的编剧。"
locations:
  - id: "loc_theater"
    name: "白鸽剧院"
    description: "废弃剧院。"
scenes:
  - id: "scene_001"
    title: "旧剧本出现"
    source_refs:
      - chapter_id: "{chapter_id}"
        range_hint: "开头至收到戏票"
        usage: "adapted"
    setting:
      location_id: "loc_theater"
      time_of_day: "night"
      atmosphere: "潮湿、紧张"
    dramatic_purpose: "建立主角目标。"
    conflict: "林栩想知道旧剧本来源，但线索指向失踪导师。"
    events:
      - id: "event_001"
        type: "action"
        content: "林栩翻开旧剧本。"
      - id: "event_002"
        type: "dialogue"
        character_id: "char_lin"
        content: "这不是我写的结局。"
    adaptation_notes:
      intent: "把原文悬疑线索改成可表演的场景。"
      omitted_or_changed: []
"""


def test_build_and_get_book_index_uses_agent_boundary() -> None:
    app.dependency_overrides[get_screenplay_agent] = lambda: FakeBookIndexAgent()
    try:
        with TestClient(app) as client:
            project_id, _ = create_project_with_long_txt(client)

            response = client.post(
                f"/projects/{project_id}/book-index",
                json={"force_rebuild": True},
            )
            assert response.status_code == 201
            payload = response.json()
            assert payload["project_id"] == project_id
            assert payload["book_index"]["characters"][0]["id"] == "char_lin"

            get_response = client.get(f"/projects/{project_id}/book-index")
            assert get_response.status_code == 200
            assert get_response.json()["file_path"].endswith("book_index.json")
    finally:
        app.dependency_overrides.clear()


def test_script_validation_accepts_valid_yaml_and_rejects_bad_reference() -> None:
    with TestClient(app) as client:
        project_id, chapters = create_project_with_long_txt(client)
        chapter_id = chapters[0]["id"]

        valid_response = client.post(
            f"/projects/{project_id}/scripts/validate",
            json={"script_yaml": sample_valid_yaml(chapter_id)},
        )
        assert valid_response.status_code == 200
        assert valid_response.json()["validation_report"]["accepted"] is True

        invalid_yaml = sample_valid_yaml(chapter_id).replace("char_lin", "char_missing", 1)
        invalid_response = client.post(
            f"/projects/{project_id}/scripts/validate",
            json={"script_yaml": invalid_yaml},
        )
        assert invalid_response.status_code == 200
        report = invalid_response.json()["validation_report"]
        assert report["accepted"] is False
        assert any(issue["code"] == "undefined_character" for issue in report["errors"])
