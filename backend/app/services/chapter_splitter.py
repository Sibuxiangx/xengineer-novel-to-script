from __future__ import annotations

import re

from pydantic import BaseModel, Field

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

    def split(self, content: str) -> list[DetectedChapter]:
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return [DetectedChapter(title="全文", content="", order_index=0)]

        lines = normalized.split("\n")
        headings: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            match = CHAPTER_HEADING_PATTERN.match(line.strip())
            if match:
                suffix = match.group(2).strip()
                title = line.strip() if suffix else match.group(1).strip()
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
