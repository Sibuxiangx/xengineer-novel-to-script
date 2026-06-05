import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes.chat import get_chat_agent
from app.main import app
from app.schemas.book_index import BookIndex, IndexedChapter, IndexedCharacter, IndexedEvent
from app.schemas.chapter_split import ChapterSplitReview, ChapterSplitRule
from app.schemas.chat import ProjectTitleSuggestion
from app.schemas.screenplay import (
    AdaptationNotes,
    Character,
    EventType,
    Location,
    ProjectMetadata,
    Scene,
    SceneSetting,
    ScreenplayFormat,
    ScreenplayYaml,
    ScriptEvent,
    SourceReference,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"


def parse_sse_events(stream_text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in stream_text.strip().split("\n\n"):
        event_name = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_name:
            events.append((event_name, json.loads(data)))
    return events


def extract_chapter_id(prompt: str) -> str:
    explicit = re.search(r"章节 ID：([^\n]+)", prompt)
    if explicit:
        return explicit.group(1).strip()
    raise AssertionError("Fake chat agent prompt did not include a chapter ID.")


class FakeChatAgent:
    async def infer_project_title(self, prompt: str) -> ProjectTitleSuggestion:
        assert "推导项目名" in prompt
        assert "long_chaptered.txt" in prompt
        return ProjectTitleSuggestion(title="雾港来信改编", reason="正文围绕雾港与旧信展开。")

    async def infer_chapter_split_rule(self, prompt: str) -> ChapterSplitRule:
        assert "推导全文分章规则" in prompt
        return ChapterSplitRule(
            strategy="line_regex",
            heading_regex=r"^\s*第[一二三四五六七八九十百千万两\d]+章[：:、.\-\s].*$",
            title_source="full_line",
            confidence=0.96,
            reason="正文使用第几章作为独立标题行。",
            examples=["第一章 雾港来信", "第二章 雨夜剧场"],
        )

    async def review_chapter_split_result(self, prompt: str) -> ChapterSplitReview:
        assert "本地切分预览" in prompt
        return ChapterSplitReview(
            accepted=True,
            diagnosis="预览章节数量和标题格式稳定。",
            confidence=0.95,
            context_requests=[],
        )

    async def build_book_index(self, prompt: str) -> BookIndex:
        chapter_id = extract_chapter_id(prompt)
        return BookIndex(
            schema_version="1.0",
            book_id="proj_chat",
            title="雾港来信改编",
            language="zh-CN",
            chapter_count=1,
            chapters=[
                IndexedChapter(
                    id=chapter_id,
                    title="第一章",
                    order=1,
                    summary="林栩收到一封旧信。",
                    events=[
                        IndexedEvent(
                            id="event_index_001",
                            summary="旧信指向废弃剧场。",
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
                    description="追查旧信来源的编剧。",
                )
            ],
        )

    async def generate_script(self, prompt: str) -> ScreenplayYaml:
        chapter_id = extract_chapter_id(prompt)
        return ScreenplayYaml(
            schema_version="1.0",
            project=ProjectMetadata(
                title="雾港来信改编",
                genre=["悬疑"],
                format=ScreenplayFormat.short_drama,
                logline="编剧追查旧信背后的剧场秘密。",
            ),
            characters=[
                Character(
                    id="char_lin",
                    name="林栩",
                    role="protagonist",
                    description="追查旧信来源的编剧。",
                )
            ],
            locations=[
                Location(
                    id="loc_theater",
                    name="雾港剧场",
                    description="被雨声包围的旧剧场。",
                )
            ],
            scenes=[
                Scene(
                    id="scene_001",
                    title="旧信抵达",
                    source_refs=[
                        SourceReference(
                            chapter_id=chapter_id,
                            range_hint="章节开头",
                            usage="adapted",
                        )
                    ],
                    setting=SceneSetting(
                        location_id="loc_theater",
                        time_of_day="night",
                        atmosphere="潮湿、压迫",
                    ),
                    dramatic_purpose="建立主角目标。",
                    conflict="林栩必须确认旧信是谁寄来的。",
                    events=[
                        ScriptEvent(
                            id="event_001",
                            type=EventType.action,
                            content="林栩拆开旧信。",
                        ),
                        ScriptEvent(
                            id="event_002",
                            type=EventType.dialogue,
                            character_id="char_lin",
                            content="这封信不该在今天出现。",
                        ),
                    ],
                    adaptation_notes=AdaptationNotes(
                        intent="把小说线索转换为可表演场景。",
                        omitted_or_changed=[],
                    ),
                )
            ],
        )


def test_chat_upload_stream_creates_project_and_pending_chapter_confirmation() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")
    app.dependency_overrides[get_chat_agent] = lambda: FakeChatAgent()
    try:
        with TestClient(app) as client:
            session_response = client.post("/chat/sessions", json={})
            assert session_response.status_code == 201
            session_id = session_response.json()["id"]

            with client.stream(
                "POST",
                f"/chat/sessions/{session_id}/runs/stream",
                json={
                    "message": "我上传了一篇小说，请开始改编。",
                    "source_file_name": "long_chaptered.txt",
                    "source_text": content,
                    "screenplay_format": "short_drama",
                },
            ) as response:
                assert response.status_code == 200
                events = parse_sse_events(response.read().decode())

            event_names = [event[0] for event in events]
            assert "tool.call.started" in event_names
            assert "tool.confirm.required" in event_names
            assert "run.waiting_confirmation" in event_names

            confirmation_event = next(
                data for name, data in events if name == "tool.confirm.required"
            )
            assert confirmation_event["kind"] == "chapter_split"
            assert confirmation_event["payload"]["preview"]["chapter_count"] == 5
            assert confirmation_event["payload"]["rule"]["strategy"] == "line_regex"

            detail = client.get(f"/chat/sessions/{session_id}").json()
            assert detail["session"]["title"] == "雾港来信改编"
            assert detail["session"]["project_id"]
            assert detail["session"]["pending_confirmation_count"] == 1
            assert detail["messages"][-1]["role"] == "assistant"
    finally:
        app.dependency_overrides.clear()


def test_chat_confirmation_stream_imports_chapters_and_generates_script() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")
    app.dependency_overrides[get_chat_agent] = lambda: FakeChatAgent()
    try:
        with TestClient(app) as client:
            session_id = client.post("/chat/sessions", json={}).json()["id"]
            with client.stream(
                "POST",
                f"/chat/sessions/{session_id}/runs/stream",
                json={
                    "message": "上传小说。",
                    "source_file_name": "long_chaptered.txt",
                    "source_text": content,
                },
            ) as response:
                events = parse_sse_events(response.read().decode())

            confirmation_id = next(
                data["id"] for name, data in events if name == "tool.confirm.required"
            )

            with client.stream(
                "POST",
                f"/chat/sessions/{session_id}/confirmations/{confirmation_id}/stream",
                json={"action": "confirm", "message": "确认这个分章。"},
            ) as response:
                assert response.status_code == 200
                confirm_events = parse_sse_events(response.read().decode())

            asset_updates = [
                data["asset"] for name, data in confirm_events if name == "asset.updated"
            ]
            assert asset_updates == ["chapters", "book_index", "script_yaml"]
            assert confirm_events[-1][0] == "run.completed"

            detail = client.get(f"/chat/sessions/{session_id}").json()
            assert detail["session"]["pending_confirmation_count"] == 0
            assert detail["latest_versions"]
            assert detail["messages"][-1]["content"].startswith("分章已确认")
    finally:
        app.dependency_overrides.clear()


def test_chat_routes_are_documented_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    create_route = schema["paths"]["/chat/sessions"]["post"]
    stream_route = schema["paths"]["/chat/sessions/{session_id}/runs/stream"]["post"]
    confirm_route = schema["paths"][
        "/chat/sessions/{session_id}/confirmations/{confirmation_id}/stream"
    ]["post"]
    assert create_route["summary"] == "Create a chat session"
    assert "ChatSessionCreateRequest" in str(create_route["requestBody"])
    assert stream_route["summary"] == "Stream an agent chat run"
    assert confirm_route["summary"] == "Stream a confirmation action"
