from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.schemas.book_index import BookIndex, IndexedChapter, IndexedEvent
from app.services.context_prompt_builder import ContextPromptBuilder


def make_settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_env": "local",
        "app_name": "XEngineer Novel-to-Script Backend",
        "deepseek_api_key": "sk-test",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_model": "deepseek-v4-pro",
        "model_context_limit": 500,
        "context_reserved_output_tokens": 100,
        "context_reserved_instruction_tokens": 100,
        "context_safety_margin_ratio": 0,
        "context_source_excerpt_chars": 500,
        "backend_cors_origins": "http://localhost:5173",
        "sqlite_database_url": "sqlite+aiosqlite:///./data/app.db",
        "local_artifact_root": Path("./data/projects"),
        "database_echo": False,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def test_book_index_prompt_packs_manifest_without_blindly_including_long_raw_text() -> None:
    builder = ContextPromptBuilder(make_settings(model_context_limit=350))
    long_body = "这一段正文会非常非常长。" * 200

    packed = builder.build_book_index_prompt(
        project_title="雾港来信",
        project_id="proj_test",
        chapters=[
            {
                "id": "chapter_001",
                "title": "第一章",
                "order": 1,
                "content": long_body,
                "token_estimate": 9999,
            }
        ],
    )

    assert "chapter_manifest" in packed.prompt
    assert '"id": "chapter_001"' in packed.prompt
    assert long_body not in packed.prompt
    assert packed.report.included_block_ids == ["task.book_index", "chapter_manifest"]
    assert packed.report.omitted_block_ids == ["raw_chapter.chapter_001"]


def test_script_generation_prompt_uses_index_and_bounded_source_excerpts() -> None:
    builder = ContextPromptBuilder(
        make_settings(
            model_context_limit=10_000,
            context_source_excerpt_chars=100,
        )
    )
    book_index = BookIndex(
        schema_version="1.0",
        book_id="proj_test",
        title="雾港来信",
        language="zh-CN",
        chapter_count=1,
        chapters=[
            IndexedChapter(
                id="chapter_001",
                title="第一章",
                order=1,
                summary="林栩收到旧信并前往剧场。",
                events=[
                    IndexedEvent(
                        id="event_index_001",
                        summary="旧信指向废弃剧场。",
                        importance="major",
                    )
                ],
            )
        ],
    )
    long_body = "开头线索" + ("中段铺垫" * 100) + "结尾反转"

    packed = builder.build_script_generation_prompt(
        project_id="proj_test",
        project_title="雾港来信",
        book_index=book_index,
        chapters=[
            {
                "id": "chapter_001",
                "title": "第一章",
                "content": long_body,
            }
        ],
    )

    assert "林栩收到旧信并前往剧场" in packed.prompt
    assert "开头线索" in packed.prompt
    assert "结尾反转" in packed.prompt
    assert "中间省略" in packed.prompt
    assert long_body not in packed.prompt
    assert "source_excerpt.chapter_001" in packed.report.included_block_ids
