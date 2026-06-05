from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.schemas.book_index import BookIndex, IndexedChapter
from app.services.context_packer import ContextBlock, ContextPacker, ContextPackingReport
from app.services.token_counter import TokenCounter


class PackedPrompt(BaseModel):
    prompt: str = Field(..., description="Prompt assembled from packed context blocks.")
    report: ContextPackingReport = Field(..., description="Context packing report.")


class ContextPromptBuilder:
    """Build budget-aware Chinese prompts for screenplay model tasks."""

    def __init__(
        self,
        settings: Settings,
        token_counter: TokenCounter | None = None,
        packer: ContextPacker | None = None,
    ) -> None:
        self.settings = settings
        self.token_counter = token_counter or TokenCounter()
        self.packer = packer or ContextPacker()

    def build_book_index_prompt(
        self,
        project_title: str,
        project_id: str,
        chapters: list[dict[str, Any]],
    ) -> PackedPrompt:
        blocks = [
            self._block(
                block_id="task.book_index",
                block_type="task_instruction",
                priority=100,
                required=True,
                content="\n".join(
                    [
                        "请为以下已导入小说章节生成 book_index.json。",
                        f"项目 ID：{project_id}",
                        f"项目标题：{project_title}",
                        "要求：必须覆盖全部章节，保留稳定 ID，输出符合 BookIndex 模型。",
                        "如果某个章节正文因上下文预算被省略，请基于章节清单保持 ID 与顺序，"
                        "并在摘要中标记需要后续补充。",
                    ]
                ),
            ),
            self._block(
                block_id="chapter_manifest",
                block_type="chapter_manifest",
                priority=95,
                required=True,
                content=self._chapter_manifest(chapters),
            ),
        ]
        for chapter in chapters:
            blocks.append(
                self._block(
                    block_id=f"raw_chapter.{chapter['id']}",
                    block_type="source_chapter",
                    priority=max(10, 80 - int(chapter["order"])),
                    required=False,
                    content="\n".join(
                        [
                            f"章节 ID：{chapter['id']}",
                            f"章节标题：{chapter['title']}",
                            f"章节顺序：{chapter['order']}",
                            f"token 估算：{chapter.get('token_estimate')}",
                            "章节正文：",
                            str(chapter["content"]),
                        ]
                    ),
                )
            )
        return self._pack(blocks)

    def build_script_generation_prompt(
        self,
        project_id: str,
        project_title: str,
        book_index: BookIndex,
        chapters: list[dict[str, Any]],
    ) -> PackedPrompt:
        blocks = [
            self._block(
                block_id="task.script_generation",
                block_type="task_instruction",
                priority=100,
                required=True,
                content="\n".join(
                    [
                        "请基于 book_index.json、章节摘要和必要原文摘录生成完整 script.yaml。",
                        f"项目 ID：{project_id}",
                        f"项目标题：{project_title}",
                        "必须使用输入中的 chapter_id 作为 source_refs.chapter_id。",
                        "每个 scene 必须包含 adaptation_notes。",
                        "优先依据 book_index 和章节摘要，不要依赖被省略的全文内容。",
                    ]
                ),
            ),
            self._block(
                block_id="book_index",
                block_type="book_index",
                priority=95,
                required=True,
                content=book_index.model_dump_json(indent=2),
            ),
            self._block(
                block_id="chapter_summaries",
                block_type="chapter_summary",
                priority=90,
                required=True,
                content=self._indexed_chapter_summaries(book_index.chapters),
            ),
        ]
        for chapter in chapters:
            blocks.append(
                self._block(
                    block_id=f"source_excerpt.{chapter['id']}",
                    block_type="source_excerpt",
                    priority=60,
                    required=False,
                    content="\n".join(
                        [
                            f"章节 ID：{chapter['id']}",
                            f"章节标题：{chapter['title']}",
                            "章节摘录：",
                            self._excerpt(str(chapter["content"])),
                        ]
                    ),
                )
            )
        return self._pack(blocks)

    def build_yaml_edit_prompt(
        self,
        instruction: str,
        target_path: str | None,
        current_yaml: str,
        book_index: BookIndex | None,
    ) -> PackedPrompt:
        blocks = [
            self._block(
                block_id="task.yaml_edit",
                block_type="task_instruction",
                priority=100,
                required=True,
                content="\n".join(
                    [
                        "请根据用户指令生成 YAML patch operations，不要直接重写全部剧本。",
                        f"用户指令：{instruction}",
                        f"目标路径：{target_path or '未指定'}",
                    ]
                ),
            ),
            self._block(
                block_id="current_script_yaml",
                block_type="script_yaml",
                priority=95,
                required=True,
                content=current_yaml,
            ),
        ]
        if book_index is not None:
            blocks.append(
                self._block(
                    block_id="book_index",
                    block_type="book_index",
                    priority=80,
                    required=False,
                    content=book_index.model_dump_json(indent=2),
                )
            )
        return self._pack(blocks)

    def build_repair_prompt(
        self,
        script_yaml: str,
        validation_report_json: dict[str, Any],
        book_index: BookIndex | None,
    ) -> PackedPrompt:
        blocks = [
            self._block(
                block_id="task.yaml_repair",
                block_type="task_instruction",
                priority=100,
                required=True,
                content=(
                    "请根据 harness 错误修复以下剧本 YAML，只输出符合 ScreenplayYaml 模型的结果。"
                ),
            ),
            self._block(
                block_id="validation_report",
                block_type="validation_report",
                priority=95,
                required=True,
                content="\n".join(
                    [
                        "harness errors:",
                        json.dumps(validation_report_json, ensure_ascii=False, indent=2),
                    ]
                ),
            ),
            self._block(
                block_id="rejected_script_yaml",
                block_type="script_yaml",
                priority=90,
                required=True,
                content=script_yaml,
            ),
        ]
        if book_index is not None:
            blocks.append(
                self._block(
                    block_id="book_index",
                    block_type="book_index",
                    priority=70,
                    required=False,
                    content=book_index.model_dump_json(indent=2),
                )
            )
        return self._pack(blocks)

    def _pack(self, blocks: list[ContextBlock]) -> PackedPrompt:
        packed = self.packer.pack_content(
            blocks=blocks,
            budget=self.settings.effective_context_input_budget,
        )
        report_json = packed.report.model_dump_json(indent=2)
        return PackedPrompt(
            prompt="\n\n".join(
                [
                    packed.content,
                    "## context_packing_report",
                    report_json,
                ]
            ),
            report=packed.report,
        )

    def _block(
        self,
        block_id: str,
        block_type: str,
        content: str,
        priority: int,
        required: bool,
    ) -> ContextBlock:
        estimate = self.token_counter.estimate(content)
        return ContextBlock(
            id=block_id,
            type=block_type,
            content=content,
            priority=priority,
            estimated_tokens=estimate.estimated_tokens,
            required=required,
        )

    def _chapter_manifest(self, chapters: list[dict[str, Any]]) -> str:
        items = [
            {
                "id": chapter["id"],
                "title": chapter["title"],
                "order": chapter["order"],
                "token_estimate": chapter.get("token_estimate"),
                "text_length": len(str(chapter["content"])),
            }
            for chapter in chapters
        ]
        return json.dumps(items, ensure_ascii=False, indent=2)

    def _indexed_chapter_summaries(self, chapters: list[IndexedChapter]) -> str:
        return json.dumps(
            [
                {
                    "id": chapter.id,
                    "title": chapter.title,
                    "order": chapter.order,
                    "summary": chapter.summary,
                    "events": [event.model_dump(mode="json") for event in chapter.events],
                }
                for chapter in chapters
            ],
            ensure_ascii=False,
            indent=2,
        )

    def _excerpt(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        max_chars = self.settings.context_source_excerpt_chars
        if len(normalized) <= max_chars:
            return normalized
        head_chars = max_chars // 2
        tail_chars = max_chars - head_chars
        return "\n".join(
            [
                normalized[:head_chars],
                f"\n[中间省略 {len(normalized) - max_chars} 个字符]\n",
                normalized[-tail_chars:],
            ]
        )
