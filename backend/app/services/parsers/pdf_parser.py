from __future__ import annotations

from backend.app.domain.assets import DocumentBlock


def parse_pdf(path, asset_id: str) -> tuple[DocumentBlock, ...]:
    """Extract text blocks from a PDF while preserving 1-based page numbers."""

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - exercised by service error path
        raise RuntimeError("missing_dependency:pymupdf") from exc

    blocks: list[DocumentBlock] = []
    document = fitz.open(str(path))
    try:
        order = 0
        for page_number, page in enumerate(document, start=1):
            text_blocks = page.get_text("blocks")
            for raw in text_blocks:
                text = str(raw[4]).strip()
                if not text:
                    continue
                order += 1
                block_id = f"{asset_id}:block-{order:04d}-page-{page_number}"
                block_type = "table" if "|" in text and "---" in text else "paragraph"
                blocks.append(
                    DocumentBlock(
                        block_id=block_id,
                        asset_id=asset_id,
                        block_type=block_type,
                        text=text,
                        page=page_number,
                        block_order=order,
                        metadata={"bbox": [raw[0], raw[1], raw[2], raw[3]]},
                    )
                )
        return tuple(blocks)
    finally:
        document.close()
