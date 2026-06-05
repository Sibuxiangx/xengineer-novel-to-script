from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.schemas.chapter_split import ChapterSplitRule

CHAPTER_HEADING_PATTERN = re.compile(
    r"^\s*(第[零〇一二三四五六七八九十百千万两\d]+章|chapter\s+\d+)\s*[：:、.\-\s]*(.*)$",
    re.IGNORECASE,
)


class DetectedChapter(BaseModel):
    title: str = Field(..., description="Detected chapter title.")
    content: str = Field(..., description="Detected chapter body content.")
    order_index: int = Field(..., description="Zero-based chapter order.")


class ChapterSplitter:
    """Split TXT ebook content into editable chapters."""

    def split(
        self,
        content: str,
        rule: ChapterSplitRule | None = None,
    ) -> list[DetectedChapter]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return [DetectedChapter(title="全文", content="", order_index=0)]
        if rule is not None and rule.strategy == "no_chapters":
            return [DetectedChapter(title="全文", content=normalized, order_index=0)]

        pattern = self._resolve_heading_pattern(rule)

        lines = normalized.split("\n")
        headings: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            match = pattern.match(line.strip())
            if match:
                title = self._heading_title(line.strip(), match, rule)
                headings.append((index, title))

        if not headings:
            return [DetectedChapter(title="全文", content=normalized, order_index=0)]

        chapters: list[DetectedChapter] = []
        leading = "\n".join(lines[: headings[0][0]]).strip()
        if leading:
            chapters.append(
                DetectedChapter(title="前言", content=leading, order_index=len(chapters))
            )

        for heading_index, (line_index, title) in enumerate(headings):
            if heading_index + 1 < len(headings):
                next_line_index = headings[heading_index + 1][0]
            else:
                next_line_index = len(lines)
            body = "\n".join(lines[line_index + 1 : next_line_index]).strip()
            chapters.append(
                DetectedChapter(title=title, content=body, order_index=len(chapters))
            )

        return chapters

    def _resolve_heading_pattern(self, rule: ChapterSplitRule | None) -> re.Pattern[str]:
        if rule is None or rule.heading_regex is None:
            return CHAPTER_HEADING_PATTERN
        try:
            return re.compile(rule.heading_regex, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Invalid chapter heading regex: {exc}") from exc

    def _heading_title(
        self,
        line: str,
        match: re.Match[str],
        rule: ChapterSplitRule | None,
    ) -> str:
        if rule is not None:
            return line
        suffix = match.group(2).strip()
        return line if suffix else match.group(1).strip()
