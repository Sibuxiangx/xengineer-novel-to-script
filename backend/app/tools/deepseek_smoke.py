from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.screenplay_agent import (
    AgentConfigurationError,
    AgentExecutionError,
    ScreenplayAgent,
)
from app.api.models.projects import ProjectCreateRequest, TxtEbookImportRequest
from app.core.config import Settings
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.services.book_index_service import BookIndexService
from app.services.project_service import ProjectService
from app.services.script_service import ScriptService

SMOKE_NOVEL = """第一章 雨夜来信
林栩是一个刚失去创作方向的小说作者。雨夜里，他收到一封没有署名的信，信中只有一张旧剧院的入场券和一句话：“你写丢的结局，在白鸽剧院。”
林栩认出票根上的日期正是导师许知遥失踪的那天。他犹豫许久，还是把票根夹进笔记本，决定第二天去剧院寻找线索。

第二章 空台上的录音
白鸽剧院已经停演三年，前厅落满灰尘。林栩在舞台中央发现一台旧录音机，里面传出许知遥的声音：“如果你听见这段录音，说明故事还没有结束。”
录音里提到一个叫“蓝灯”的暗号，只有真正理解人物选择的人才能找到它。林栩意识到导师留下的不是谜题，而是一场逼他重新面对创作失败的排练。

第三章 蓝灯亮起
夜幕降临，林栩在后台找到一盏蒙尘的蓝色工作灯。灯亮起时，墙上显出导师留下的手写批注：结局不是替人物选择，而是让人物承担选择。
林栩明白自己过去总把人物推向方便的答案。他带着录音和批注离开剧院，准备重写那个被他放弃的故事，也准备寻找导师失踪前真正想完成的剧本。
"""


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _settings_for_smoke(working_root: Path) -> Settings:
    base = Settings()  # pyright: ignore[reportCallIssue]
    return base.model_copy(
        update={
            "sqlite_database_url": f"sqlite+aiosqlite:///{working_root / 'smoke.sqlite'}",
            "local_artifact_root": working_root / "projects",
            "database_echo": False,
        }
    )


def _safe_error(exc: Exception, settings: Settings) -> str:
    message = str(exc)
    if settings.deepseek_api_key is not None:
        secret = settings.deepseek_api_key.get_secret_value()
        if secret:
            message = message.replace(secret, "***")
    return message


async def run_smoke(working_root: Path) -> dict[str, Any]:
    settings = _settings_for_smoke(working_root)
    settings.ensure_local_paths()
    if (
        settings.deepseek_api_key is None
        or not settings.deepseek_api_key.get_secret_value().strip()
    ):
        raise AgentConfigurationError("Missing DEEPSEEK_API_KEY.")

    engine = create_async_engine(settings.sqlite_database_url, echo=settings.database_echo)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            agent = ScreenplayAgent(settings)
            project_service = ProjectService(session=session, settings=settings)
            book_index_service = BookIndexService(
                session=session,
                settings=settings,
                agent=agent,
            )
            script_service = ScriptService(session=session, settings=settings, agent=agent)

            _log("1/4 创建临时项目并导入三章短文")
            project = await project_service.create_project(
                ProjectCreateRequest(title="DeepSeek 冒烟短篇", screenplay_format="short_drama")
            )
            imported = await project_service.import_txt_ebook(
                project.id,
                TxtEbookImportRequest(
                    file_name="deepseek-smoke.txt",
                    content=SMOKE_NOVEL,
                    split_strategy="auto",
                    replace_existing=True,
                ),
            )

            _log("2/4 真实调用 DeepSeek 生成 book_index.json")
            book_index_response = await book_index_service.build_index(
                project.id,
                force_rebuild=True,
            )

            _log("3/4 真实调用 DeepSeek 生成 script.yaml")
            script_response = await script_service.generate_script(
                project.id,
                force_regenerate=True,
            )

            _log("4/4 运行 harness 并汇总结果")
            if not script_response.validation_report.accepted:
                raise RuntimeError(
                    "Generated script.yaml was rejected by harness: "
                    f"{script_response.validation_report.model_dump(mode='json')}"
                )
            if script_response.accepted_version_id is None:
                raise RuntimeError(
                    "Generated script.yaml passed validation but no version was saved."
                )

            return {
                "ok": True,
                "created_at": datetime.now(UTC).isoformat(),
                "model": settings.deepseek_model,
                "base_url": settings.deepseek_base_url,
                "project_id": project.id,
                "chapter_count": imported.detected_chapter_count,
                "book_index": {
                    "chapter_count": book_index_response.book_index.chapter_count,
                    "character_count": len(book_index_response.book_index.characters),
                    "event_count": sum(
                        len(chapter.events) for chapter in book_index_response.book_index.chapters
                    ),
                },
                "script": {
                    "accepted": script_response.validation_report.accepted,
                    "accepted_version_id": script_response.accepted_version_id,
                    "metrics": script_response.validation_report.metrics,
                    "warning_count": len(script_response.validation_report.warnings),
                },
                "artifact_root": str(settings.local_artifact_root),
            }
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real DeepSeek smoke flow against the backend service layer."
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Persist smoke SQLite and project artifacts under backend/data/deepseek-smoke.",
    )
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    if args.keep_artifacts:
        working_root = Path("data") / "deepseek-smoke"
        working_root.mkdir(parents=True, exist_ok=True)
        try:
            result = await run_smoke(working_root)
        except (AgentConfigurationError, AgentExecutionError, RuntimeError) as exc:
            settings = _settings_for_smoke(working_root)
            print(
                json.dumps(
                    {"ok": False, "error": _safe_error(exc, settings)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix="xengineer-deepseek-smoke-") as temp_dir:
        working_root = Path(temp_dir)
        try:
            result = await run_smoke(working_root)
        except (AgentConfigurationError, AgentExecutionError, RuntimeError) as exc:
            settings = _settings_for_smoke(working_root)
            print(
                json.dumps(
                    {"ok": False, "error": _safe_error(exc, settings)},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
