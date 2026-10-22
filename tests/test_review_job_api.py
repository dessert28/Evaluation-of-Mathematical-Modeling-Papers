from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.assets import InMemoryAssetStore
from backend.app.api.reviews import create_review_router
from backend.app.api.rubrics import InMemoryRubricRepository
from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.domain.rubrics import RubricCriterion, RubricDraft, RubricStatus
from backend.app.services.review_jobs import build_review_job, input_snapshot_hash
from datetime import datetime, timezone


class MemoryJobs:
    def __init__(self):
        self.items = {}

    def create(self, job):
        if job.id in self.items:
            raise ValueError("review job already exists")
        self.items[job.id] = job
        return job

    def get(self, job_id):
        return self.items.get(job_id)

    def list(self):
        return list(self.items.values())


def _asset():
    block = DocumentBlock("b1", "asset-1", "paragraph", "paper", line_start=1, line_end=1)
    return Asset("asset-1", "paper.md", "text/markdown", 5, "sha256:abc", ParseStatus.PARSED, Path("paper.md"), ParsedDocument(ParseStatus.PARSED, (block,)))


def _rubric():
    return RubricDraft(id="rubric-1", name="Official", version="v1", source_asset_id="rubric-source", source_hash="sha256:def", criteria=[RubricCriterion(id="c1", label="Quality", weight=1.0)])


def test_build_job_requires_published_rubric():
    asset = _asset()
    rubric = _rubric()
    try:
        build_review_job(asset=asset, rubric=rubric)
    except ValueError as exc:
        assert "published rubric" in str(exc)
    else:
        raise AssertionError("draft rubric must be rejected")


def test_snapshot_hash_is_stable():
    first = input_snapshot_hash(asset_sha256="sha256:a", rubric_source_hash="sha256:b", options={"x": 1})
    second = input_snapshot_hash(asset_sha256="a", rubric_source_hash="b", options={"x": 1})
    assert first == second


def test_review_api_rejects_unpublished_rubric():
    app = FastAPI()
    app.state.asset_store = InMemoryAssetStore()
    app.state.asset_store.save(_asset())
    app.state.rubric_repository = InMemoryRubricRepository()
    app.state.rubric_repository.create(_rubric())
    app.state.review_job_repository = MemoryJobs()
    app.include_router(create_review_router(app.state.review_job_repository))
    response = TestClient(app).post("/api/v1/reviews", json={"asset_id": "asset-1", "rubric_profile_id": "rubric-1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "rubric_not_published"


def test_review_api_creates_and_reads_job():
    app = FastAPI()
    app.state.asset_store = InMemoryAssetStore()
    app.state.asset_store.save(_asset())
    app.state.rubric_repository = InMemoryRubricRepository()
    published = RubricDraft(
        id="rubric-2", name="Official", version="v2", source_asset_id="rubric-source", source_hash="sha256:def",
        criteria=[RubricCriterion(id="c1", label="Quality", weight=1.0)], status=RubricStatus.PUBLISHED,
        published_at=datetime.now(timezone.utc), decision_ledger_id="decision-1",
    )
    app.state.rubric_repository.create(published)
    app.state.review_job_repository = MemoryJobs()
    app.include_router(create_review_router(app.state.review_job_repository))
    client = TestClient(app)
    response = client.post("/api/v1/reviews", json={"asset_id": "asset-1", "rubric_profile_id": "rubric-2", "options": {"language": "zh"}})
    assert response.status_code == 201
    job = response.json()
    assert job["state"] == "CREATED"
    assert job["input_snapshot_hash"].startswith("sha256:")
    assert client.get(f"/api/v1/reviews/{job['id']}").json()["id"] == job["id"]
