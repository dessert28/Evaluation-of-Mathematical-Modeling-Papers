from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol

try:
    from fastapi import APIRouter, File, HTTPException, Request, UploadFile
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover - installed by application package
    APIRouter = None

from backend.app.domain.assets import Asset
from backend.app.services.asset_inventory import AssetInventory


class AssetStore(Protocol):
    def save(self, asset: Asset) -> Asset: ...
    def get(self, asset_id: str) -> Asset | None: ...
    def list(self) -> list[Asset]: ...


class InMemoryAssetStore:
    """Small adapter used by local API tests and development previews."""

    def __init__(self):
        self._items: dict[str, Asset] = {}

    def save(self, asset: Asset) -> Asset:
        existing = next((item for item in self._items.values() if item.sha256 == asset.sha256), None)
        if existing is not None:
            return existing
        self._items[asset.id] = asset
        return asset

    def get(self, asset_id: str) -> Asset | None:
        return self._items.get(asset_id)

    def list(self) -> list[Asset]:
        return sorted(self._items.values(), key=lambda item: item.created_at or "", reverse=True)


if APIRouter is not None:
    router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

    def _inventory(request: Request) -> AssetInventory:
        inventory = getattr(request.app.state, "asset_inventory", None)
        if inventory is None:
            raise HTTPException(status_code=503, detail={"error": {"code": "inventory_unavailable", "message": "资产服务未配置", "details": {}}})
        return inventory

    def _store(request: Request) -> AssetStore:
        store = getattr(request.app.state, "asset_store", None)
        if store is None:
            raise HTTPException(status_code=503, detail={"error": {"code": "store_unavailable", "message": "资产存储未配置", "details": {}}})
        return store

    @router.post("", status_code=201)
    async def upload_asset(request: Request, file: UploadFile = File(...)):
        inventory = _inventory(request)
        store = _store(request)
        suffix = Path(file.filename or "asset").suffix or ".upload"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(await file.read())
            temporary_path = Path(temporary.name)
        try:
            asset = inventory.inspect(temporary_path, filename=file.filename or "asset")
        finally:
            temporary_path.unlink(missing_ok=True)
        if asset.status.value == "failed":
            # Keep a durable failed record so parse errors remain auditable and
            # can be inspected without retaining the request body in logs.
            asset = store.save(asset)
            status = 413 if asset.error_code == "file_too_large" else 422
            return JSONResponse(
                status_code=status,
                content={"error": {"code": asset.error_code or "parse_failed", "message": asset.parse_error or "资产解析失败", "details": asset.as_dict(include_text=False)}},
            )
        asset = store.save(asset)
        return asset.as_dict()

    @router.get("")
    def list_assets(request: Request):
        return [asset.as_dict(include_text=False) for asset in _store(request).list()]

    @router.get("/{asset_id}")
    def get_asset(asset_id: str, request: Request):
        asset = _store(request).get(asset_id)
        if asset is None:
            return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "资产不存在", "details": {}}})
        return asset.as_dict()

    @router.get("/{asset_id}/blocks")
    def get_asset_blocks(asset_id: str, request: Request):
        asset = _store(request).get(asset_id)
        if asset is None:
            return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "资产不存在", "details": {}}})
        return [block.as_dict() for block in asset.blocks]
else:  # pragma: no cover
    router = None


__all__ = ["router", "InMemoryAssetStore"]
