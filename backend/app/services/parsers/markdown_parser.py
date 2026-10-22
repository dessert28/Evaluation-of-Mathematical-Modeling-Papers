from __future__ import annotations

import re

from backend.app.domain.assets import DocumentBlock


_FENCE = re.compile(r"^\s*(```+|~~~+)(.*)$")


def _block_id(asset_id: str, order: int, block_type: str, start: int, end: int) -> str:
    # asset_id is already a content hash, making this stable across filenames.
    return f"{asset_id}:block-{order:04d}-{block_type}-{start}-{end}"


def parse_markdown(text: str, asset_id: str) -> tuple[DocumentBlock, ...]:
    """Parse Markdown into evidence-addressable headings, tables, code, and paragraphs."""

    lines = text.splitlines()
    blocks: list[DocumentBlock] = []
    index = 0

    def add(kind: str, content: list[str], start: int, end: int, metadata=None):
        nonlocal index
        value = "\n".join(content).strip("\n")
        if not value.strip():
            return
        index += 1
        blocks.append(
            DocumentBlock(
                block_id=_block_id(asset_id, index, kind, start, end),
                asset_id=asset_id,
                block_type=kind,
                text=value,
                line_start=start,
                line_end=end,
                block_order=index,
                metadata=metadata or {},
            )
        )

    i = 0
    paragraph: list[str] = []
    paragraph_start = 0

    def flush_paragraph(end_line: int):
        nonlocal paragraph
        if paragraph:
            add("paragraph", paragraph, paragraph_start, end_line)
            paragraph = []

    while i < len(lines):
        line = lines[i]
        number = i + 1
        fence = _FENCE.match(line)
        if fence:
            flush_paragraph(number - 1)
            marker = fence.group(1)
            language = fence.group(2).strip()
            start = number
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith(marker):
                code_lines.append(lines[i])
                i += 1
            end = min(i + 1, len(lines))
            add("code", code_lines, start, end, {"language": language})
            i += 1
            continue

        if re.match(r"^\s{0,3}#{1,6}\s+", line):
            flush_paragraph(number - 1)
            add("heading", [line], number, number)
            i += 1
            continue

        separator = lines[i + 1] if i + 1 < len(lines) else ""
        is_table_separator = (
            "|" in separator
            and re.search(r"(?:^|\|)\s*:?-{1,}:?\s*(?:\||$)", separator) is not None
        )
        if "|" in line and is_table_separator:
            flush_paragraph(number - 1)
            table = [line, lines[i + 1]]
            start = number
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                table.append(lines[i])
                i += 1
            add("table", table, start, i, {"format": "pipe"})
            continue

        if not line.strip():
            flush_paragraph(number - 1)
            i += 1
            continue

        if not paragraph:
            paragraph_start = number
        paragraph.append(line)
        i += 1

    flush_paragraph(len(lines))
    return tuple(blocks)
