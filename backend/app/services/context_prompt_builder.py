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
        adaptation_requirements: str | None = None,
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
        if adaptation_requirements:
            blocks.append(
                self._block(
                    block_id="adaptation_requirements",
                    block_type="user_requirements",
                    priority=98,
                    required=True,
                    content="\n".join(
                        [
                            "用户在上传小说时给出的改编要求：",
                            adaptation_requirements,
                            "请在抽取人物、事件、线索和摘要时保留与这些要求相关的信息。",
                        ]
                    ),
                )
            )
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
        adaptation_requirements: str | None = None,
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
        if adaptation_requirements:
            blocks.append(
                self._block(
                    block_id="adaptation_requirements",
                    block_type="user_requirements",
                    priority=98,
                    required=True,
                    content="\n".join(
                        [
                            "用户在上传小说时给出的改编要求：",
                            adaptation_requirements,
                            (
                                "生成剧本时必须优先遵守这些要求；如果与原文冲突，"
                                "请在 adaptation_notes 中说明取舍。"
                            ),
                        ]
                    ),
                )
            )
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

    def build_novel_answer_prompt(
        self,
        question: str,
        project_id: str,
        project_title: str,
        chapters: list[dict[str, Any]],
        book_index: BookIndex | None,
        current_yaml: str | None,
    ) -> PackedPrompt:
        blocks = [
            self._block(
                block_id="task.novel_qa",
                block_type="task_instruction",
                priority=100,
                required=True,
                content="\n".join(
                    [
                        "请把小说原文、剧情索引和当前剧本当作知识库回答用户问题。",
                        "必须使用中文回答。",
                        (
                            "优先依据小说原文与 book_index.json；涉及已生成剧本的内容时，"
                            "可以参考当前 script.yaml。"
                        ),
                        "如果上下文不足以确定答案，请明确说明无法确认，不要编造。",
                        "回答应简洁、可直接展示给作者；必要时列出依据的章节标题或场景。",
                        f"项目 ID：{project_id}",
                        f"项目标题：{project_title}",
                        f"用户问题：{question}",
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
        if book_index is not None:
            blocks.append(
                self._block(
                    block_id="book_index",
                    block_type="book_index",
                    priority=92,
                    required=False,
                    content=book_index.model_dump_json(indent=2),
                )
            )
        if current_yaml:
            blocks.append(
                self._block(
                    block_id="current_script_yaml",
                    block_type="script_yaml",
                    priority=80,
                    required=False,
                    content=current_yaml,
                )
            )
        for chapter in chapters:
            blocks.append(
                self._block(
                    block_id=f"source_excerpt.{chapter['id']}",
                    block_type="source_excerpt",
                    priority=max(30, 75 - int(chapter["order"])),
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
                content="\n".join(
                    [
                        "请根据验证报告对上一版剧本 YAML 做定向修复。",
                        "只修复验证报告指出的问题，不要从头重写或重新生成整份剧本。",
                        "必须保留未出错的项目标题、人物、地点、场景、事件、稳定 ID 和顺序。",
                        "如果需要补充字段，请基于上一版 YAML 的上下文做最小必要补充。",
                        "最终只输出符合 ScreenplayYaml 模型的完整结构化结果，不要输出解释文字。",
                    ]
                ),
            ),
            self._block(
                block_id="validation_issue_summary",
                block_type="validation_issue_summary",
                priority=98,
                required=True,
                content=self._validation_issue_summary(validation_report_json),
            ),
            self._block(
                block_id="validation_report_json",
                block_type="validation_report",
                priority=96,
                required=True,
                content="\n".join(
                    [
                        "验证报告 JSON：",
                        json.dumps(validation_report_json, ensure_ascii=False, indent=2),
                    ]
                ),
            ),
            self._block(
                block_id="previous_script_yaml",
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

    def _validation_issue_summary(self, validation_report_json: dict[str, Any]) -> str:
        issues: list[dict[str, Any]] = []
        for kind in ("errors", "warnings"):
            raw_items = validation_report_json.get(kind, [])
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                issues.append(
                    {
                        "kind": kind.removesuffix("s"),
                        "code": item.get("code"),
                        "path": item.get("path"),
                        "severity": item.get("severity"),
                        "message": item.get("message"),
                        "repair_hint": item.get("repair_hint"),
                    }
                )
        if not issues:
            issues.append(
                {
                    "kind": "unknown",
                    "code": "accepted_false_without_issue",
                    "message": (
                        "验证报告未列出具体问题，请对照完整验证报告和上一版 YAML "
                        "修复导致 accepted=false 的最小必要字段。"
                    ),
                }
            )
        return "\n".join(
            [
                "以下是本次必须优先修复的问题定位。请逐条处理 path/code/message/repair_hint，"
                "不要改动无关内容：",
                json.dumps(issues, ensure_ascii=False, indent=2),
            ]
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
