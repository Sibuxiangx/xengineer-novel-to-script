import asyncio
import json
import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes.chat import get_chat_agent
from app.core.config import get_settings
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
    async def run_source_ingestion_tools(self, prompt: str, deps: Any) -> str:
        assert "工具编排要求" in prompt
        assert deps.toolbox is not None
        title = await deps.toolbox.propose_project_title()
        project = await deps.toolbox.create_project(title.title)
        deps.project_id = project.project_id
        await deps.toolbox.propose_chapter_split()
        await deps.toolbox.request_chapter_split_confirmation()
        return "已创建分章确认。"

    async def run_chat_instruction_tools(self, prompt: str, deps: Any) -> str:
        assert "已有小说改编项目" in prompt
        assert deps.toolbox is not None
        return "已处理当前项目。"

    async def infer_project_title(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ProjectTitleSuggestion:
        assert "推导项目名" in prompt
        assert "long_chaptered.txt" in prompt
        return ProjectTitleSuggestion(title="雾港来信改编", reason="正文围绕雾港与旧信展开。")

    async def infer_chapter_split_rule(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ChapterSplitRule:
        assert "推导全文分章规则" in prompt
        return ChapterSplitRule(
            strategy="line_regex",
            heading_regex=r"^\s*第[一二三四五六七八九十百千万两\d]+章[：:、.\-\s].*$",
            title_source="full_line",
            confidence=0.96,
            reason="正文使用第几章作为独立标题行。",
            examples=["第一章 雾港来信", "第二章 雨夜剧场"],
        )

    async def review_chapter_split_result(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ChapterSplitReview:
        assert "本地切分预览" in prompt
        return ChapterSplitReview(
            accepted=True,
            diagnosis="预览章节数量和标题格式稳定。",
            confidence=0.95,
            context_requests=[],
        )

    async def build_book_index(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> BookIndex:
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

    async def generate_script(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ScreenplayYaml:
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

    async def repair_script(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ScreenplayYaml:
        assert "harness errors" in prompt
        match = re.search(r"chapter_id: ([^\n]+)", prompt)
        chapter_id = match.group(1).strip() if match else "chapter_001"
        return await self.generate_script(f"章节 ID：{chapter_id}")


class RejectedScriptFakeChatAgent(FakeChatAgent):
    def __init__(self) -> None:
        self.repair_count = 0

    async def generate_script(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ScreenplayYaml:
        screenplay = await super().generate_script(prompt)
        screenplay.scenes[0].adaptation_notes = None
        return screenplay

    async def repair_script(
        self,
        prompt: str,
        stream_callback: Any = None,
    ) -> ScreenplayYaml:
        self.repair_count += 1
        assert "harness errors" in prompt
        match = re.search(r"chapter_id: ([^\n]+)", prompt)
        chapter_id = match.group(1).strip() if match else "chapter_001"
        screenplay = await super().generate_script(f"章节 ID：{chapter_id}")
        screenplay.scenes[0].adaptation_notes = None
        return screenplay


class SlowSourceIngestionFakeChatAgent(FakeChatAgent):
    async def run_source_ingestion_tools(self, prompt: str, deps: Any) -> str:
        await asyncio.sleep(0.02)
        return await super().run_source_ingestion_tools(prompt, deps)


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
            assert "run.progress" in event_names

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


def test_chat_stream_emits_heartbeat_while_agent_task_is_running() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")
    settings = get_settings().model_copy(update={"sse_heartbeat_interval_seconds": 0.001})
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_chat_agent] = lambda: SlowSourceIngestionFakeChatAgent()
    try:
        with TestClient(app) as client:
            session_id = client.post("/chat/sessions", json={}).json()["id"]

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

            event_names = [name for name, _ in events]
            assert "heartbeat" in event_names
            progress_events = [
                data
                for name, data in events
                if name == "run.progress" and data["stage"] == "source_ingestion_agent"
            ]
            assert progress_events[0]["status"] == "started"
            assert progress_events[-1]["status"] == "completed"
            assert progress_events[-1]["duration_ms"] >= 1
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
            event_names = [event[0] for event in confirm_events]
            assert event_names.count("model.usage.estimated") >= 2
            assert "run.progress" in event_names

            completed_tool = next(
                data
                for name, data in confirm_events
                if name == "tool.call.completed"
            )
            assert completed_tool["duration_ms"] >= 0
            script_asset = next(
                data
                for name, data in confirm_events
                if name == "asset.updated" and data["asset"] == "script_yaml"
            )
            assert script_asset["context_report"]["estimated_tokens"] > 0

            detail = client.get(f"/chat/sessions/{session_id}").json()
            assert detail["session"]["pending_confirmation_count"] == 0
            assert detail["latest_versions"]
            assert detail["messages"][-1]["content"].startswith("分章已确认")

            chapters_response = client.get(f"/chat/sessions/{session_id}/assets/chapters")
            assert chapters_response.status_code == 200
            assert len(chapters_response.json()["chapters"]) == 5

            book_index_response = client.get(f"/chat/sessions/{session_id}/assets/book-index")
            assert book_index_response.status_code == 200
            assert book_index_response.json()["book_index"]["title"] == "雾港来信改编"

            version_id = detail["latest_versions"][-1]["id"]
            versions_response = client.get(f"/chat/sessions/{session_id}/assets/scripts/versions")
            assert versions_response.status_code == 200
            assert versions_response.json()["versions"][-1]["id"] == version_id

            version_response = client.get(
                f"/chat/sessions/{session_id}/assets/scripts/versions/{version_id}"
            )
            assert version_response.status_code == 200
            assert "scenes:" in version_response.json()["script_yaml"]
    finally:
        app.dependency_overrides.clear()


def test_chat_confirmation_preserves_rejected_draft_when_repairs_fail() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")
    fake_agent = RejectedScriptFakeChatAgent()
    app.dependency_overrides[get_chat_agent] = lambda: fake_agent
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

            validation_event = next(
                data for name, data in confirm_events if name == "validation.completed"
            )
            rejected_version_id = validation_event["rejected_version_id"]
            expected_attempts = get_settings().script_repair_max_attempts
            assert validation_event["validation_status"] == "rejected"
            assert validation_event["accepted_version_id"] is None
            assert rejected_version_id
            assert validation_event["repair_attempt_count"] == expected_attempts
            assert validation_event["validation_report"]["accepted"] is False
            assert fake_agent.repair_count == expected_attempts

            script_asset_event = next(
                data
                for name, data in confirm_events
                if name == "asset.updated" and data["asset"] == "script_yaml"
            )
            assert script_asset_event["validation_status"] == "rejected"
            assert script_asset_event["rejected_version_id"] == rejected_version_id
            assert script_asset_event["accepted_version_id"] is None

            completed_event = confirm_events[-1]
            assert completed_event[0] == "run.completed_with_errors"
            assert completed_event[1]["rejected_version_id"] == rejected_version_id

            detail = client.get(f"/chat/sessions/{session_id}").json()
            latest_version = detail["latest_versions"][-1]
            assert latest_version["id"] == rejected_version_id
            assert latest_version["validation_status"] == "rejected"
            assert detail["messages"][-1]["metadata"]["run_status"] == "completed_with_errors"

            version_response = client.get(
                f"/chat/sessions/{session_id}/assets/scripts/versions/{rejected_version_id}"
            )
            assert version_response.status_code == 200
            assert "adaptation_notes: null" in version_response.json()["script_yaml"]
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
    chapters_route = schema["paths"]["/chat/sessions/{session_id}/assets/chapters"]["get"]
    versions_route = schema["paths"]["/chat/sessions/{session_id}/assets/scripts/versions"]["get"]
    assert create_route["summary"] == "Create a chat session"
    assert "ChatSessionCreateRequest" in str(create_route["requestBody"])
    assert stream_route["summary"] == "Stream an agent chat run"
    assert confirm_route["summary"] == "Stream a confirmation action"
    assert chapters_route["summary"] == "List chat project chapters"
    assert versions_route["summary"] == "List chat project screenplay versions"
