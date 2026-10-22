from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.rubrics import InMemoryRubricRepository, create_rubric_router


@pytest.fixture()
def client() -> TestClient:
    repository = InMemoryRubricRepository()
    app = FastAPI()
    app.include_router(create_rubric_router(repository))
    return TestClient(app)


def test_import_preview_and_list_rubric(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rubrics/import",
        json={
            "format": "json",
            "source_asset_id": "asset-1",
            "source_hash": "sha256:rubric",
            "content": {
                "name": "官方评分",
                "version": "v1",
                "criteria": [{"id": "model", "label": "模型", "weight": 1}],
            },
        },
    )
    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["criteria"][0]["id"] == "model"

    listed = client.get("/api/v1/rubrics")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == draft["id"]


def test_publish_requires_human_confirmation_and_persists_decision(client: TestClient) -> None:
    imported = client.post(
        "/api/v1/rubrics/import",
        json={
            "format": "markdown",
            "source_asset_id": "asset-2",
            "source_hash": "sha256:rubric2",
            "content": "| id | label | weight |\n|---|---|---|\n| model | 模型 | 1 |",
        },
    ).json()

    denied = client.post(
        f"/api/v1/rubrics/{imported['id']}/publish",
        json={"confirmed_by": "agent", "decision": "publish", "rationale": "自动"},
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "human_confirmation_required"

    published = client.post(
        f"/api/v1/rubrics/{imported['id']}/publish",
        json={"confirmed_by": "human", "decision": "publish", "rationale": "已核对"},
    )
    assert published.status_code == 200
    assert published.json()["rubric"]["status"] == "published"
    assert published.json()["decision"]["decided_by"] == "human"


def test_repeated_name_and_version_is_rejected(client: TestClient) -> None:
    body = {
        "format": "json",
        "source_asset_id": "asset-1",
        "source_hash": "sha256:one",
        "content": {"name": "官方评分", "version": "v1", "criteria": [{"id": "model", "label": "模型", "weight": 1}]},
    }
    first = client.post("/api/v1/rubrics/import", json=body)
    assert first.status_code == 201
    second = client.post("/api/v1/rubrics/import", json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_version"


def test_multipart_json_rubric_file_is_imported(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rubrics/import",
        data={"source_asset_id": "asset-upload", "source_hash": "sha256:upload"},
        files={"file": ("rubric.json", b'{"name":"Uploaded","version":"v1","criteria":[{"id":"model","label":"Model","weight":1}]}', "application/json")},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Uploaded"


def test_invalid_rubric_media_type_uses_uniform_error(client: TestClient) -> None:
    response = client.post("/api/v1/rubrics/import", content="plain text", headers={"content-type": "text/plain"})
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_draft_can_be_edited_but_published_rubric_cannot(client: TestClient) -> None:
    imported = client.post(
        "/api/v1/rubrics/import",
        json={
            "format": "json",
            "source_asset_id": "asset-edit",
            "source_hash": "sha256:edit",
            "content": {"name": "Editable", "version": "v1", "criteria": [{"id": "model", "label": "Old", "weight": 1}]},
        },
    ).json()
    edited = client.put(
        f"/api/v1/rubrics/{imported['id']}",
        json={
            "format": "json",
            "source_asset_id": "asset-edit",
            "source_hash": "sha256:edit",
            "content": {"name": "Editable", "version": "v1", "criteria": [{"id": "model", "label": "New", "weight": 1}]},
        },
    )
    assert edited.status_code == 200
    assert edited.json()["criteria"][0]["label"] == "New"
    client.post(f"/api/v1/rubrics/{imported['id']}/publish", json={"confirmed_by": "human", "rationale": "confirmed"})
    rejected = client.put(
        f"/api/v1/rubrics/{imported['id']}",
        json={
            "format": "json",
            "source_asset_id": "asset-edit",
            "source_hash": "sha256:edit",
            "content": {"name": "Editable", "version": "v1", "criteria": [{"id": "model", "label": "No", "weight": 1}]},
        },
    )
    assert rejected.status_code == 409
