from pathlib import Path

from app.services.chapter_splitter import ChapterSplitter

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "articles"


def test_splitter_keeps_short_text_without_headings_as_single_chapter() -> None:
    content = (FIXTURE_ROOT / "short_no_chapters.txt").read_text(encoding="utf-8")

    chapters = ChapterSplitter().split(content)

    assert len(chapters) == 1
    assert chapters[0].title == "全文"
    assert "第一章" not in chapters[0].title
    assert len(chapters[0].content) > 500


def test_splitter_detects_chinese_chapter_headings() -> None:
    content = (FIXTURE_ROOT / "long_chaptered.txt").read_text(encoding="utf-8")

    chapters = ChapterSplitter().split(content)

    assert len(chapters) == 5
    assert chapters[0].title.startswith("第一章")
    assert chapters[-1].title.startswith("第五章")
    assert all(chapter.content for chapter in chapters)

