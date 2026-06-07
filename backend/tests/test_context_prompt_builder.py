from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.schemas.book_index import BookIndex, IndexedChapter, IndexedEvent
from app.services.context_prompt_builder import ContextPromptBuilder

LEGACY_VALIDATION_TERM = "har" + "ness"


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


def test_book_index_prompt_includes_first_turn_adaptation_requirements() -> None:
    builder = ContextPromptBuilder(make_settings(model_context_limit=10_000))

    packed = builder.build_book_index_prompt(
        project_title="雾港来信",
        project_id="proj_test",
        adaptation_requirements="请强化悬疑感，弱化爱情线。",
        chapters=[
            {
                "id": "chapter_001",
                "title": "第一章",
                "order": 1,
                "content": "林栩收到旧信。",
                "token_estimate": 30,
            }
        ],
    )

    assert "用户在上传小说时给出的改编要求" in packed.prompt
    assert "请强化悬疑感，弱化爱情线。" in packed.prompt
    assert "adaptation_requirements" in packed.report.included_block_ids


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


def test_script_generation_prompt_includes_first_turn_adaptation_requirements() -> None:
    builder = ContextPromptBuilder(make_settings(model_context_limit=10_000))
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
                summary="林栩收到旧信。",
                events=[],
            )
        ],
    )

    packed = builder.build_script_generation_prompt(
        project_id="proj_test",
        project_title="雾港来信",
        book_index=book_index,
        adaptation_requirements="请强化悬疑感，弱化爱情线。",
        chapters=[
            {
                "id": "chapter_001",
                "title": "第一章",
                "content": "林栩收到旧信。",
            }
        ],
    )

    assert "生成剧本时必须优先遵守这些要求" in packed.prompt
    assert "请强化悬疑感，弱化爱情线。" in packed.prompt
    assert "adaptation_requirements" in packed.report.included_block_ids


def test_novel_answer_prompt_uses_source_index_and_current_script_as_knowledge_base() -> None:
    builder = ContextPromptBuilder(make_settings(model_context_limit=10_000))
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

    packed = builder.build_novel_answer_prompt(
        question="林栩为什么去剧场？",
        project_id="proj_test",
        project_title="雾港来信",
        chapters=[
            {
                "id": "chapter_001",
                "title": "第一章",
                "order": 1,
                "content": "旧信写着：午夜到废弃剧场来。",
                "token_estimate": 40,
            }
        ],
        book_index=book_index,
        current_yaml="schema_version: '1.0'\nproject:\n  title: 雾港来信\n",
    )

    assert "把小说原文、剧情索引和当前剧本当作知识库" in packed.prompt
    assert "林栩为什么去剧场？" in packed.prompt
    assert "旧信指向废弃剧场" in packed.prompt
    assert "旧信写着" in packed.prompt
    assert "task.novel_qa" in packed.report.included_block_ids


def test_repair_prompt_targets_previous_yaml_and_validation_issues() -> None:
    builder = ContextPromptBuilder(make_settings(model_context_limit=10_000))
    script_yaml = "\n".join(
        [
            "schema_version: '1.0'",
            "project:",
            "  title: 雾港来信",
            "scenes:",
            "  - id: scene_001",
            "    adaptation_notes: null",
        ]
    )
    validation_report = {
        "accepted": False,
        "severity": "error",
        "errors": [
            {
                "code": "missing_adaptation_notes",
                "severity": "error",
                "path": "scenes.scene_001.adaptation_notes",
                "message": "每个场景必须说明改编意图。",
                "repair_hint": "请补充 adaptation_notes.intent 和必要的删改说明。",
                "source": "policy",
            }
        ],
        "warnings": [],
        "metrics": {},
    }

    packed = builder.build_repair_prompt(
        script_yaml=script_yaml,
        validation_report_json=validation_report,
        book_index=None,
    )

    assert "只修复验证报告指出的问题" in packed.prompt
    assert "missing_adaptation_notes" in packed.prompt
    assert "scenes.scene_001.adaptation_notes" in packed.prompt
    assert "adaptation_notes: null" in packed.prompt
    assert "previous_script_yaml" in packed.report.included_block_ids
    assert "validation_issue_summary" in packed.report.included_block_ids
    assert "validation_report_json" in packed.report.included_block_ids
    assert LEGACY_VALIDATION_TERM not in packed.prompt.lower()
