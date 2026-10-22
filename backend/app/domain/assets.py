"""Domain objects for uploaded paper and rubric source assets.

The objects in this module deliberately do not depend on a database ORM.  The
inventory service can therefore be tested independently and persisted by the
application's database adapter later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ParseStatus(str, Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


@dataclass(frozen=True)
class DocumentBlock:
    """A stable, evidence-addressable part of an uploaded document."""

    block_id: str
    asset_id: str
    block_type: str
    text: str
    page: int | None = None
    paragraph: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    block_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "block_id": self.block_id,
            "page": self.page,
            "paragraph": self.paragraph,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "asset_id": self.asset_id,
            "block_type": self.block_type,
            "text": self.text,
            "page": self.page,
            "paragraph": self.paragraph,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "block_order": self.block_order,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ParsedDocument:
    status: ParseStatus
    blocks: tuple[DocumentBlock, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class Asset:
    id: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    status: ParseStatus
    storage_path: Path
    parsed_document: ParsedDocument | None = None
    parse_error: str | None = None
    created_at: str | None = None

    @property
    def blocks(self) -> tuple[DocumentBlock, ...]:
        return self.parsed_document.blocks if self.parsed_document else ()

    @property
    def error_code(self) -> str | None:
        return self.parsed_document.error_code if self.parsed_document else None

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.parsed_document.warnings if self.parsed_document else ()

    def as_dict(self, include_text: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status.value,
            "storage_path": str(self.storage_path),
            "parse_error": self.parse_error,
            "error_code": self.error_code,
            "warnings": list(self.warnings),
            "created_at": self.created_at,
        }
        result["blocks"] = [
            block.as_dict() if include_text else {k: v for k, v in block.as_dict().items() if k != "text"}
            for block in self.blocks
        ]
        return result
