from __future__ import annotations

import json
import re
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.screenplay_agent import ScreenplayAgent
from app.api.models.projects import (
    ChapterSplitInferenceIteration,
    ChapterSplitInferencePreview,
    ChapterSplitInferenceRequest,
    ChapterSplitInferenceResponse,
)
from app.core.config import Settings
from app.db.repositories.projects import ProjectRepository
from app.schemas.chapter_split import (
    ChapterSplitContextRequest,
    ChapterSplitReview,
    ChapterSplitRule,
    HeadingCandidate,
    RequestedContextSample,
    TextPeekSample,
)
from app.services.chapter_splitter import ChapterSplitter, DetectedChapter

BROAD_HEADING_PATTERN = re.compile(
    r"^\s*(第.{1,18}[章节回卷部篇]|chapter\s+\d+|book\s+\d+).{0,90}$",
    re.IGNORECASE,
)


class ChapterSplitInferenceProjectNotFoundError(Exception):
    """Raised when a project does not exist for chapter split inference."""


class ChapterSplitInferenceService:
    """Infer long TXT chapter split rules from sampled text snippets."""

    def __init__(self, session: AsyncSession, settings: Settings, agent: ScreenplayAgent) -> None:
        self.session = session
        self.settings = settings
        self.agent = agent
        self.projects = ProjectRepository(session)
        self.splitter = ChapterSplitter()

    async def infer_rule(
        self,
        project_id: str,
        request: ChapterSplitInferenceRequest,
    ) -> ChapterSplitInferenceResponse:
        project = await self.projects.get(project_id)
        if project is None:
            raise ChapterSplitInferenceProjectNotFoundError(project_id)

        samples = self._peek_samples(request.content, request.max_sample_chars)
        prompt = self._build_prompt(request.file_name, request.content, samples)
        rule = await self.agent.infer_chapter_split_rule(prompt)
        iterations: list[ChapterSplitInferenceIteration] = []
        requested_contexts: list[RequestedContextSample] = []

        for round_index in range(request.max_review_rounds + 1):
            detected = self.splitter.split(request.content, rule=rule)
            preview = self._preview(request.content, detected, rule)
            review = await self.agent.review_chapter_split_result(
                self._build_review_prompt(
                    file_name=request.file_name,
                    content=request.content,
                    samples=samples,
                    rule=rule,
                    preview=preview,
                    round_index=round_index,
                )
            )
            requested_contexts = self._requested_contexts(
                request.content,
                review.context_requests,
                request.context_window_chars,
            )
            iterations.append(
                ChapterSplitInferenceIteration(
                    round_index=round_index,
                    rule=rule,
                    preview=preview,
                    review=review,
                    requested_contexts=requested_contexts,
                )
            )
            if review.accepted or round_index >= request.max_review_rounds:
                break
            rule = await self.agent.revise_chapter_split_rule(
                self._build_revision_prompt(
                    file_name=request.file_name,
                    content=request.content,
                    samples=samples,
                    current_rule=rule,
                    preview=preview,
                    review=review,
                    requested_contexts=requested_contexts,
                )
            )

        final_iteration = iterations[-1]
        return ChapterSplitInferenceResponse(
            project_id=project_id,
            file_name=request.file_name,
            text_length=len(request.content),
            samples=samples,
            rule=final_iteration.rule,
            preview=final_iteration.preview,
            iterations=iterations,
        )

    def _peek_samples(self, content: str, max_sample_chars: int) -> list[TextPeekSample]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        text_length = len(normalized)
        if text_length <= max_sample_chars * 3:
            return [
                TextPeekSample(
                    label="head",
                    start_char=0,
                    end_char=text_length,
                    text=normalized,
                )
            ]

        middle_start = max(0, text_length // 2 - max_sample_chars // 2)
        windows: list[tuple[Literal["head", "middle", "tail"], int, int]] = [
            ("head", 0, min(max_sample_chars, text_length)),
            (
                "middle",
                middle_start,
                min(middle_start + max_sample_chars, text_length),
            ),
            (
                "tail",
                max(0, text_length - max_sample_chars),
                text_length,
            ),
        ]
        return [
            TextPeekSample(label=label, start_char=start, end_char=end, text=normalized[start:end])
            for label, start, end in windows
        ]

    def _build_prompt(
        self,
        file_name: str,
        content: str,
        samples: list[TextPeekSample],
    ) -> str:
        sample_blocks = []
        for sample in samples:
            sample_blocks.append(
                "\n".join(
                    [
                        f"片段位置：{sample.label}",
                        f"字符范围：{sample.start_char} - {sample.end_char}",
                        "片段内容：",
                        sample.text,
                    ]
                )
            )
        return "\n\n".join(
            [
                "请根据以下 TXT 电子书片段推导全文分章规则。",
                f"文件名：{file_name}",
                f"全文字符数：{len(content)}",
                "只需要推导标题行匹配规则，不需要总结剧情。",
                "片段：",
                "\n\n---\n\n".join(sample_blocks),
            ]
        )

    def _preview(
        self,
        content: str,
        detected: list[DetectedChapter],
        rule: ChapterSplitRule,
    ) -> ChapterSplitInferencePreview:
        candidates = self._heading_candidates(content)
        unmatched = self._unmatched_candidates(candidates, rule)
        return ChapterSplitInferencePreview(
            chapter_count=len(detected),
            titles=[chapter.title for chapter in detected[:20]],
            last_titles=[chapter.title for chapter in detected[-20:]],
            candidate_heading_count=len(candidates),
            unmatched_candidate_count=len(unmatched),
            unmatched_candidates=unmatched[:30],
        )

    def _heading_candidates(self, content: str) -> list[HeadingCandidate]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        candidates: list[HeadingCandidate] = []
        offset = 0
        for line_number, line in enumerate(normalized.splitlines(), start=1):
            stripped = line.strip()
            if BROAD_HEADING_PATTERN.match(stripped):
                candidates.append(
                    HeadingCandidate(
                        line_number=line_number,
                        start_char=offset + line.find(stripped),
                        text=stripped,
                    )
                )
            offset += len(line) + 1
        return candidates

    def _unmatched_candidates(
        self,
        candidates: list[HeadingCandidate],
        rule: ChapterSplitRule,
    ) -> list[HeadingCandidate]:
        if rule.strategy == "no_chapters" or rule.heading_regex is None:
            return candidates
        try:
            pattern = re.compile(rule.heading_regex, re.IGNORECASE)
        except re.error:
            return candidates
        return [candidate for candidate in candidates if not pattern.match(candidate.text)]

    def _requested_contexts(
        self,
        content: str,
        requests: list[ChapterSplitContextRequest],
        context_window_chars: int,
    ) -> list[RequestedContextSample]:
        samples: list[RequestedContextSample] = []
        text_length = len(content)
        for request in requests:
            requested_start = min(request.start_char, text_length)
            requested_end = min(request.end_char, text_length)
            max_requested_chars = context_window_chars
            clipped_end = min(requested_end, requested_start + max_requested_chars)
            padding = context_window_chars // 2
            start = max(0, requested_start - padding)
            end = min(text_length, clipped_end + padding)
            if end <= start:
                continue
            samples.append(
                RequestedContextSample(
                    request=request,
                    start_char=start,
                    end_char=end,
                    text=content[start:end],
                    truncated=clipped_end < requested_end,
                )
            )
        return samples

    def _build_review_prompt(
        self,
        file_name: str,
        content: str,
        samples: list[TextPeekSample],
        rule: ChapterSplitRule,
        preview: ChapterSplitInferencePreview,
        round_index: int,
    ) -> str:
        return "\n\n".join(
            [
                "请检查本地分章结果。",
                f"文件名：{file_name}",
                f"全文字符数：{len(content)}",
                f"检查轮次：{round_index}",
                "初始 peek 片段范围：",
                json.dumps(
                    [sample.model_dump(exclude={"text"}) for sample in samples],
                    ensure_ascii=False,
                    indent=2,
                ),
                "当前规则：",
                rule.model_dump_json(ensure_ascii=False, indent=2),
                "本地切分预览：",
                preview.model_dump_json(ensure_ascii=False, indent=2),
            ]
        )

    def _build_revision_prompt(
        self,
        file_name: str,
        content: str,
        samples: list[TextPeekSample],
        current_rule: ChapterSplitRule,
        preview: ChapterSplitInferencePreview,
        review: ChapterSplitReview,
        requested_contexts: list[RequestedContextSample],
    ) -> str:
        context_blocks = []
        for context in requested_contexts:
            context_blocks.append(
                "\n".join(
                    [
                        f"请求原因：{context.request.reason}",
                        f"字符范围：{context.start_char} - {context.end_char}",
                        "上下文内容：",
                        context.text,
                    ]
                )
            )
        return "\n\n".join(
            [
                "请基于追加上下文重写分章规则。",
                f"文件名：{file_name}",
                f"全文字符数：{len(content)}",
                "初始 peek 片段范围：",
                json.dumps(
                    [sample.model_dump(exclude={"text"}) for sample in samples],
                    ensure_ascii=False,
                    indent=2,
                ),
                "当前规则：",
                current_rule.model_dump_json(ensure_ascii=False, indent=2),
                "本地切分预览：",
                preview.model_dump_json(ensure_ascii=False, indent=2),
                "检查诊断：",
                review.model_dump_json(ensure_ascii=False, indent=2),
                "追加上下文：",
                "\n\n---\n\n".join(context_blocks),
            ]
        )
