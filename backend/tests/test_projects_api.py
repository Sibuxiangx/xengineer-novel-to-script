from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.projects import get_chapter_split_agent
from app.main import app
from app.schemas.chapter_split import (
    ChapterSplitContextRequest,
    ChapterSplitReview,
    ChapterSplitRule,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"
CLASSIC_HUI_REGEX = r"^\s*第[零〇一二三四五六七八九十百千万两\d]+回[：:、.\-\s].*$"


def create_project(client: TestClient, title: str = "测试项目") -> dict:
    response = client.post(
        "/projects",
        json={"title": title, "screenplay_format": "short_drama"},
    )
    assert response.status_code == 201
    return response.json()


def test_import_short_txt_without_chapters_creates_single_editable_chapter() -> None:
    content = (FIXTURE_ROOT / "short_no_chapters.txt").read_text(encoding="utf-8")

    with TestClient(app) as client:
        project = create_project(client, "无分章短篇")
        import_response = client.post(
            f"/projects/{project['id']}/ebook/import-txt",
            json={
                "file_name": "short_no_chapters.txt",
                "content": content,
                "split_strategy": "auto",
            },
        )

        assert import_response.status_code == 201
        imported = import_response.json()
        assert imported["detected_chapter_count"] == 1
        assert imported["chapters"][0]["title"] == "全文"
        assert imported["chapters"][0]["content"] == content.strip()
        assert imported["chapters"][0]["token_estimate"] > 0

        chapter_id = imported["chapters"][0]["id"]
        update_response = client.patch(
            f"/projects/{project['id']}/chapters/{chapter_id}",
            json={"title": "改写后的短篇", "content": "这是用户手动编辑后的章节内容。"},
        )

        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["title"] == "改写后的短篇"
        assert updated["content"] == "这是用户手动编辑后的章节内容。"


def test_import_long_txt_detects_multiple_chapters_in_order() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")

    with TestClient(app) as client:
        project = create_project(client, "五章长篇")
        import_response = client.post(
            f"/projects/{project['id']}/ebook/import-txt",
            json={
                "file_name": "long_chaptered.txt",
                "content": content,
                "split_strategy": "auto",
            },
        )

        assert import_response.status_code == 201
        imported = import_response.json()
        assert imported["detected_chapter_count"] == 5
        assert [chapter["order_index"] for chapter in imported["chapters"]] == [0, 1, 2, 3, 4]
        assert imported["chapters"][0]["title"].startswith("第一章")

        list_response = client.get(f"/projects/{project['id']}/chapters")
        assert list_response.status_code == 200
        listed = list_response.json()["chapters"]
        assert len(listed) == 5
        assert listed[-1]["title"].startswith("第五章")


def test_import_txt_with_custom_rule_handles_classic_hui_headings() -> None:
    content = "\n".join(
        [
            "第一回：宴桃園豪傑三結義",
            "劉備關羽張飛相識於涿郡。",
            "",
            "第二回：張翼德怒鞭督郵",
            "督郵逼迫縣吏，張飛怒而鞭之。",
        ]
    )

    with TestClient(app) as client:
        project = create_project(client, "章回体导入")
        import_response = client.post(
            f"/projects/{project['id']}/ebook/import-txt",
            json={
                "file_name": "classic.txt",
                "content": content,
                "split_strategy": "custom_rule",
                "chapter_split_rule": {
                    "strategy": "line_regex",
                    "heading_regex": CLASSIC_HUI_REGEX,
                    "title_source": "full_line",
                    "confidence": 0.96,
                    "reason": "标题行使用第几回加冒号的章回体格式。",
                    "examples": ["第一回：宴桃園豪傑三結義", "第二回：張翼德怒鞭督郵"],
                },
            },
        )

        assert import_response.status_code == 201
        imported = import_response.json()
        assert imported["detected_chapter_count"] == 2
        assert imported["split_strategy"] == "custom_rule"
        assert imported["chapters"][0]["title"].startswith("第一回")
        assert imported["chapters"][1]["title"].startswith("第二回")


class FakeChapterSplitAgent:
    def __init__(self, third_heading_start: int) -> None:
        self.third_heading_start = third_heading_start
        self.review_count = 0

    async def infer_chapter_split_rule(self, prompt: str) -> ChapterSplitRule:
        assert "片段位置：head" in prompt
        assert "片段位置：middle" in prompt
        assert "片段位置：tail" in prompt
        assert "正文开头" in prompt
        assert "正文中段" in prompt
        assert "正文结尾" in prompt
        assert len(prompt) < 6000
        return ChapterSplitRule(
            strategy="line_regex",
            heading_regex=r"^\s*第[一二]回[：:、.\-\s].*$",
            title_source="full_line",
            confidence=0.72,
            reason="初步只从片段中确认到前两回标题。",
            examples=["第一回：正文开头", "第二回：正文中段"],
        )

    async def review_chapter_split_result(self, prompt: str) -> ChapterSplitReview:
        self.review_count += 1
        assert "本地切分预览" in prompt
        if self.review_count == 1:
            assert '"unmatched_candidate_count": 1' in prompt
            return ChapterSplitReview(
                accepted=False,
                diagnosis="本地宽松扫描发现第三回标题未被当前规则匹配，需要查看该标题上下文。",
                confidence=0.9,
                context_requests=[
                    ChapterSplitContextRequest(
                        reason="查看未匹配的第三回标题上下文。",
                        start_char=self.third_heading_start,
                        end_char=self.third_heading_start + 20,
                    )
                ],
            )
        assert '"unmatched_candidate_count": 0' in prompt
        return ChapterSplitReview(
            accepted=True,
            diagnosis="修订后所有疑似标题均已匹配。",
            confidence=0.95,
            context_requests=[],
        )

    async def revise_chapter_split_rule(self, prompt: str) -> ChapterSplitRule:
        assert "第三回：正文结尾" in prompt
        return ChapterSplitRule(
            strategy="line_regex",
            heading_regex=CLASSIC_HUI_REGEX,
            title_source="full_line",
            confidence=0.95,
            reason="追加上下文确认第三回同属第几回格式，扩展中文数字字符集。",
            examples=["第一回：正文开头", "第二回：正文中段", "第三回：正文结尾"],
        )


def test_infer_split_rule_uses_peek_samples_and_returns_preview() -> None:
    repeated_body = "不应发送给模型的整本正文。" * 500
    content = "\n".join(
        [
            "第一回：正文开头",
            "开头片段。",
            repeated_body,
            "第二回：正文中段",
            "中段片段。",
            repeated_body,
            "第三回：正文结尾",
            "结尾片段。",
        ]
    )
    fake_agent = FakeChapterSplitAgent(third_heading_start=content.index("第三回"))
    app.dependency_overrides[get_chapter_split_agent] = lambda: fake_agent
    try:
        with TestClient(app) as client:
            project = create_project(client, "AI 推导分章")
            response = client.post(
                f"/projects/{project['id']}/ebook/infer-split-rule",
                json={
                    "file_name": "classic-long.txt",
                    "content": content,
                    "max_sample_chars": 1200,
                },
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["rule"]["strategy"] == "line_regex"
            assert payload["preview"]["chapter_count"] == 3
            assert payload["preview"]["titles"][:3] == [
                "第一回：正文开头",
                "第二回：正文中段",
                "第三回：正文结尾",
            ]
            assert len(payload["samples"]) == 3
            assert len(payload["iterations"]) == 2
            assert payload["iterations"][0]["review"]["accepted"] is False
            assert payload["iterations"][0]["requested_contexts"][0]["text"].find("第三回") >= 0
            assert payload["iterations"][1]["review"]["accepted"] is True
    finally:
        app.dependency_overrides.clear()


def test_project_routes_are_documented_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    assert schema["paths"]["/projects"]["post"]["summary"] == "Create an adaptation project"
    import_route = schema["paths"]["/projects/{project_id}/ebook/import-txt"]["post"]
    assert import_route["summary"] == "Import a TXT ebook"
    assert "TxtEbookImportResponse" in str(import_route["responses"]["201"])
    infer_route = schema["paths"]["/projects/{project_id}/ebook/infer-split-rule"]["post"]
    assert infer_route["summary"] == "Infer TXT chapter split rule"
    assert "ChapterSplitInferenceResponse" in str(infer_route["responses"]["200"])
