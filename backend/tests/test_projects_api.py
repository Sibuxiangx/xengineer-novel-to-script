from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"


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


def test_project_routes_are_documented_in_openapi() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    schema = response.json()
    assert schema["paths"]["/projects"]["post"]["summary"] == "Create an adaptation project"
    import_route = schema["paths"]["/projects/{project_id}/ebook/import-txt"]["post"]
    assert import_route["summary"] == "Import a TXT ebook"
    assert "TxtEbookImportResponse" in str(import_route["responses"]["201"])

