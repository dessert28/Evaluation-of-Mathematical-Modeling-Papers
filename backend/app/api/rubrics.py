"""FastAPI endpoints for rubric import, preview, and publication."""

from __future__ import annotations

from collections.abc import Iterable
import json
import tempfile
from pathlib import Path
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.domain.rubrics import RubricDraft, RubricPublishResult, RubricStatus, rubric_dict
from backend.app.services.rubric_importer import RubricImportError, RubricImporter


class RubricRepository(Protocol):
    def create(self, rubric: RubricDraft) -> RubricDraft: ...

    def list(self) -> list[RubricDraft]: ...

    def get(self, rubric_id: str) -> RubricDraft | None: ...

    def publish(self, rubric: RubricDraft, decision: Any) -> None: ...

    def update(self, rubric: RubricDraft) -> RubricDraft: ...


class InMemoryRubricRepository:
    """Small repository used by tests and as a local development fallback."""

    def __init__(self) -> None:
        self._items: dict[str, RubricDraft] = {}
        self.decisions: dict[str, Any] = {}

    def create(self, rubric: RubricDraft) -> RubricDraft:
        if any(item.name == rubric.name and item.version == rubric.version for item in self._items.values()):
            raise RubricImportError(f"rubric name and version already exist: {rubric.name} {rubric.version}")
        self._items[rubric.id] = rubric
        return rubric

    def list(self) -> list[RubricDraft]:
        return list(self._items.values())

    def get(self, rubric_id: str) -> RubricDraft | None:
        return self._items.get(rubric_id)

    def publish(self, rubric: RubricDraft, decision: Any) -> None:
        self._items[rubric.id] = rubric
        self.decisions[decision.id] = decision

    def update(self, rubric: RubricDraft) -> RubricDraft:
        existing = self._items.get(rubric.id)
        if existing is None:
            raise RubricImportError("rubric not found")
        if existing.status is RubricStatus.PUBLISHED:
            raise RubricImportError("published rubric cannot be edited")
        if rubric.status is not RubricStatus.DRAFT:
            raise RubricImportError("only draft rubrics can be edited")
        if any(item.id != rubric.id and item.name == rubric.name and item.version == rubric.version for item in self._items.values()):
            raise RubricImportError(f"rubric name and version already exist: {rubric.name} {rubric.version}")
        self._items[rubric.id] = rubric
        return rubric


class RubricImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: str = Field(pattern="^(json|markdown|pdf|docx|document_blocks)$")
    source_asset_id: str = Field(min_length=1)
    source_hash: str = Field(min_length=1)
    content: Any | None = None
    document_blocks: list[dict[str, Any]] | None = None


class RubricPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed_by: str
    decision: str = "publish"
    rationale: str


def _error(code: str, message: str, *, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": {}}})


def _response_error(exc: HTTPException) -> dict[str, Any]:
    detail = exc.detail
    return detail if isinstance(detail, dict) and "error" in detail else {"error": {"code": "request_failed", "message": str(detail), "details": {}}}


def _validate_source_binding(request: Request, import_request: RubricImportRequest) -> None:
    """Verify rubric source identity when the application has persistent assets."""

    store = getattr(request.app.state, "asset_store", None)
    if store is None:
        # Isolated router tests may intentionally provide synthetic source IDs.
        return
    asset = store.get(import_request.source_asset_id)
    if asset is None:
        raise _error("source_asset_not_found", "量表来源资产不存在", status_code=404)
    expected = import_request.source_hash.removeprefix("sha256:").lower()
    actual = asset.sha256.removeprefix("sha256:").lower()
    if expected != actual:
        raise _error("source_hash_mismatch", "量表来源哈希与资产不一致", status_code=409)


def create_rubric_router(repository: RubricRepository | None = None) -> APIRouter:
    repo = repository or InMemoryRubricRepository()
    router = APIRouter(prefix="/api/v1/rubrics", tags=["rubrics"])

    async def _read_import_request(request: Request) -> RubricImportRequest:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            try:
                return RubricImportRequest.model_validate(await request.json())
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                raise _error("validation_error", "量表导入请求格式无效", status_code=422) from exc
        if "multipart/form-data" not in content_type:
            raise _error("unsupported_media_type", "量表导入需要 JSON 或 multipart/form-data", status_code=415)
        form = await request.form()
        upload = form.get("file")
        fmt = str(form.get("format") or "").lower().strip()
        source_asset_id = str(form.get("source_asset_id") or "").strip()
        source_hash = str(form.get("source_hash") or "").strip()
        content: Any = form.get("content")
        document_blocks: list[dict[str, Any]] | None = None
        if upload is not None and hasattr(upload, "filename"):
            filename = str(getattr(upload, "filename", "asset"))
            suffix = Path(filename).suffix.lower()
            if not fmt:
                fmt = {".json": "json", ".md": "markdown", ".markdown": "markdown", ".pdf": "pdf", ".docx": "docx"}.get(suffix, "")
            inventory = getattr(request.app.state, "asset_inventory", None)
            store = getattr(request.app.state, "asset_store", None)
            if inventory is None:
                # Preserve standalone-router support for explicitly bound text uploads.
                if store is None and fmt in {'json', 'markdown'} and source_asset_id and source_hash:
                    try:
                        content = (await upload.read()).decode('utf-8-sig')
                        return RubricImportRequest(format=fmt, source_asset_id=source_asset_id,
                                                   source_hash=source_hash, content=content)
                    except UnicodeError as exc:
                        raise _error('parse_failed', '量表文件编码无法解析', status_code=422) from exc
                raise _error("inventory_unavailable", "资产服务未配置", status_code=503)
            payload = await upload.read(inventory.max_bytes + 1)
            if len(payload) > inventory.max_bytes:
                raise _error('file_too_large', '量表文件超过上传限制', status_code=413)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
                temporary.write(payload)
                temporary_path = Path(temporary.name)
            try:
                asset = inventory.inspect(temporary_path, filename=filename, allow_json=fmt == 'json')
            finally:
                temporary_path.unlink(missing_ok=True)
            if store is not None:
                asset = store.save(asset)
            if asset.status.value == 'failed':
                # Parser exceptions can contain source snippets: public errors stay fixed.
                raise _error(asset.error_code or 'parse_failed', '量表文件为空、编码异常或无法解析', status_code=422)
            source_asset_id = asset.id
            source_hash = asset.sha256
            if fmt in {'json', 'markdown'}:
                content = payload.decode('utf-8-sig')
            else:
                document_blocks = [block.as_dict() for block in asset.blocks]
        try:
            return RubricImportRequest.model_validate({
                "format": fmt,
                "source_asset_id": source_asset_id,
                "source_hash": source_hash,
                "content": content,
                "document_blocks": document_blocks,
            })
        except ValidationError as exc:
            raise _error("validation_error", "量表导入请求缺少必要字段", status_code=422) from exc

    @router.post("/import", status_code=status.HTTP_201_CREATED)
    async def import_rubric(request: Request) -> dict[str, Any]:
        try:
            import_request = await _read_import_request(request)
            _validate_source_binding(request, import_request)
        except HTTPException as error:
            detail = error.detail if isinstance(error.detail, dict) else {"error": {"code": "request_failed", "message": str(error.detail), "details": {}}}
            if "error" not in detail:
                detail = {"error": {"code": "request_failed", "message": str(error.detail), "details": {}}}
            return JSONResponse(status_code=error.status_code, content=detail)
        try:
            if import_request.format == "json":
                draft = RubricImporter.from_json(
                    import_request.content if isinstance(import_request.content, (str, dict)) else {},
                    source_asset_id=import_request.source_asset_id,
                    source_hash=import_request.source_hash,
                )
            elif import_request.format == "markdown":
                if not isinstance(import_request.content, str):
                    raise RubricImportError("markdown content must be a string")
                draft = RubricImporter.from_markdown(
                    import_request.content,
                    source_asset_id=import_request.source_asset_id,
                    source_hash=import_request.source_hash,
                )
            else:
                blocks = import_request.document_blocks
                if blocks is None and isinstance(import_request.content, list):
                    blocks = import_request.content
                if blocks is None:
                    raise RubricImportError("document_blocks are required for PDF/DOCX rubric import")
                draft = RubricImporter.from_document_blocks(
                    blocks,
                    source_asset_id=import_request.source_asset_id,
                    source_hash=import_request.source_hash,
                )
            created = repo.create(draft)
            return rubric_dict(created)
        except RubricImportError as exc:
            code = "duplicate_version" if "already exist" in str(exc) else "rubric_import_failed"
            status_code = 409 if code == "duplicate_version" else 422
            error = _error(code, str(exc), status_code=status_code)
            return JSONResponse(status_code=error.status_code, content=error.detail)
        except Exception as exc:
            # Covers foreign-key and other persistence conflicts while keeping
            # the public API in the documented error envelope.
            error = _error("rubric_persistence_failed", "量表保存失败", status_code=422)
            return JSONResponse(status_code=error.status_code, content=error.detail)

    @router.get("")
    def list_rubrics() -> list[dict[str, Any]]:
        return [rubric_dict(item) for item in repo.list()]

    @router.get("/{rubric_id}")
    def get_rubric(rubric_id: str) -> dict[str, Any]:
        item = repo.get(rubric_id)
        if item is None:
            error = _error("rubric_not_found", f"rubric {rubric_id} not found", status_code=404)
            return JSONResponse(status_code=error.status_code, content=error.detail)
        return rubric_dict(item)

    @router.put("/{rubric_id}")
    def update_rubric(rubric_id: str, request: RubricImportRequest, http_request: Request) -> dict[str, Any]:
        item = repo.get(rubric_id)
        if item is None:
            error = _error("rubric_not_found", f"rubric {rubric_id} not found", status_code=404)
            return JSONResponse(status_code=error.status_code, content=error.detail)
        try:
            _validate_source_binding(http_request, request)
            if request.format == "json":
                draft = RubricImporter.from_json(request.content if isinstance(request.content, (str, dict)) else {}, source_asset_id=request.source_asset_id, source_hash=request.source_hash)
            elif request.format == "markdown" and isinstance(request.content, str):
                draft = RubricImporter.from_markdown(request.content, source_asset_id=request.source_asset_id, source_hash=request.source_hash)
            else:
                draft = RubricImporter.from_document_blocks(request.document_blocks or request.content or [], source_asset_id=request.source_asset_id, source_hash=request.source_hash)
            draft = draft.model_copy(update={"id": rubric_id})
            return rubric_dict(repo.update(draft))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content=_response_error(exc))
        except RubricImportError as exc:
            code = "rubric_not_found" if "not found" in str(exc) else "rubric_edit_failed"
            message = str(exc)
            status_code = 404 if code == "rubric_not_found" else 409 if (
                "already exist" in message
                or "immutable" in message
                or "published rubric" in message
            ) else 422
            error = _error(code, str(exc), status_code=status_code)
            return JSONResponse(status_code=error.status_code, content=error.detail)
        except Exception:
            error = _error("rubric_persistence_failed", "量表保存失败", status_code=422)
            return JSONResponse(status_code=error.status_code, content=error.detail)

    @router.post("/{rubric_id}/publish")
    def publish_rubric(rubric_id: str, request: RubricPublishRequest) -> dict[str, Any]:
        item = repo.get(rubric_id)
        if item is None:
            error = _error("rubric_not_found", f"rubric {rubric_id} not found", status_code=404)
            return JSONResponse(status_code=error.status_code, content=error.detail)
        try:
            published, decision = RubricImporter.publish(
                item,
                confirmed_by=request.confirmed_by,
                rationale=request.rationale,
                decision=request.decision,
            )
            repo.publish(published, decision)
            return {"rubric": rubric_dict(published), "decision": decision.model_dump(mode="json")}
        except RubricImportError as exc:
            code = "human_confirmation_required" if "human confirmation" in str(exc) else "rubric_publish_failed"
            error = _error(code, str(exc), status_code=422)
            return JSONResponse(status_code=error.status_code, content=error.detail)

    return router
