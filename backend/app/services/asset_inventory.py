from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.services.parsers import parse_docx, parse_markdown, parse_pdf


class AssetInventory:
    """Hash, store, and parse paper assets without executing uploaded code."""

    MAX_BYTES = 50 * 1024 * 1024
    SUPPORTED = {".pdf", ".docx", ".md", ".markdown"}

    def __init__(self, data_dir: str | Path, max_bytes: int = MAX_BYTES):
        self.data_dir = Path(data_dir)
        self.asset_dir = self.data_dir / "assets"
        self.max_bytes = max_bytes

    def inspect(self, path: str | Path, filename: str | None = None, *, allow_json: bool = False) -> Asset:
        source = Path(path)
        display_name = self._safe_filename(filename or source.name)
        created_at = datetime.now(timezone.utc).isoformat()
        asset_id = str(uuid4())
        try:
            if not source.is_file():
                return self._failed(asset_id, display_name, "", source, "not_found", "文件不存在", created_at)
            size = source.stat().st_size
            digest = self._sha256(source)
            storage_path = self._store(source, digest, display_name)
            media_type = mimetypes.guess_type(display_name)[0] or "application/octet-stream"
            if size == 0:
                return self._failed(asset_id, display_name, digest, storage_path, "empty_file", "文件为空", created_at, size, media_type)
            if size > self.max_bytes:
                return self._failed(asset_id, display_name, digest, storage_path, "file_too_large", f"文件超过 {self.max_bytes} 字节限制", created_at, size, media_type)
            suffix = source.suffix.lower()
            if suffix not in self.SUPPORTED and not (allow_json and suffix == '.json'):
                return self._failed(asset_id, display_name, digest, storage_path, "unsupported_type", f"不支持的文件类型: {suffix or '无扩展名'}", created_at, size, media_type)
            try:
                blocks = self._parse(source, suffix, digest)
                # Block IDs use the content digest for stability across
                # duplicate uploads, while Evidence.location must point to
                # the concrete asset record returned by this inspection.
                blocks = tuple(replace(block, asset_id=asset_id) for block in blocks)
                parsed = ParsedDocument(status=ParseStatus.PARSED, blocks=blocks)
                return Asset(asset_id, display_name, media_type, size, digest, ParseStatus.PARSED, storage_path, parsed, created_at=created_at)
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                parsed = ParsedDocument(status=ParseStatus.FAILED, error_code="parse_failed", error_message=message)
                return Asset(asset_id, display_name, media_type, size, digest, ParseStatus.FAILED, storage_path, parsed, parse_error=message, created_at=created_at)
        except OSError as exc:
            return self._failed(asset_id, display_name, "", source, "storage_error", str(exc), created_at)

    def _parse(self, source: Path, suffix: str, asset_id: str):
        if suffix == '.json':
            text = source.read_text(encoding='utf-8-sig')
            json.loads(text)
            return (DocumentBlock(f'{asset_id}:json:0', asset_id, 'json', text,
                                  line_start=1, line_end=len(text.splitlines()), block_order=0),)
        if suffix in {".md", ".markdown"}:
            return parse_markdown(source.read_text(encoding="utf-8-sig"), asset_id)
        if suffix == ".pdf":
            return parse_pdf(source, asset_id)
        return parse_docx(source, asset_id)

    def _store(self, source: Path, digest: str, display_name: str) -> Path:
        target_dir = self.asset_dir / digest
        target_dir.mkdir(parents=True, exist_ok=True)
        # A content-addressed asset is stored only once.  Reusing the existing
        # path also makes duplicate uploads deterministic when their filenames
        # differ.
        existing = next((item for item in target_dir.iterdir() if item.is_file()), None)
        if existing is not None:
            return existing
        target = target_dir / display_name
        shutil.copy2(source, target)
        return target

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = Path(filename).name
        cleaned = re.sub(r"[^\w.()\- ]", "_", cleaned, flags=re.UNICODE).strip(" .")
        return cleaned or "asset"

    @staticmethod
    def _failed(asset_id, filename, digest, storage_path, code, message, created_at, size=0, media_type="application/octet-stream"):
        parsed = ParsedDocument(status=ParseStatus.FAILED, error_code=code, error_message=message)
        return Asset(asset_id, filename, media_type, size, digest, ParseStatus.FAILED, Path(storage_path), parsed, parse_error=message, created_at=created_at)
