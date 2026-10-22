from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.assets import InMemoryAssetStore, router
from backend.app.services.asset_inventory import AssetInventory


def _client(tmp_path: Path):
    app = FastAPI()
    app.state.asset_inventory = AssetInventory(tmp_path / "data")
    app.state.asset_store = InMemoryAssetStore()
    app.include_router(router)
    return TestClient(app)


def test_upload_and_get_asset_exposes_evidence_location(tmp_path: Path):
    client = _client(tmp_path)
    response = client.post(
        "/api/v1/assets",
        files={"file": ("paper.md", b"# Title\n\nParagraph\n", "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "parsed"
    asset_id = payload["id"]
    assert payload["blocks"][0]["asset_id"] == asset_id

    fetched = client.get(f"/api/v1/assets/{asset_id}")
    assert fetched.status_code == 200
    assert fetched.json()["sha256"] == payload["sha256"]

    blocks = client.get(f"/api/v1/assets/{asset_id}/blocks")
    assert blocks.status_code == 200
    assert blocks.json()[0]["block_id"]


def test_upload_empty_file_returns_uniform_error(tmp_path: Path):
    client = _client(tmp_path)
    response = client.post(
        "/api/v1/assets",
        files={"file": ("empty.md", b"", "text/markdown")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"
