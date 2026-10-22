from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.db import AssetRecord, RubricProfileRecord, SqlAlchemyReviewJobRepository, init_db, session_scope
from backend.app.domain.review_jobs import ReviewJob
from backend.app.domain.review_protocol import Evidence, EvidenceLevel, Verdict
from backend.app.domain.review_results import ReviewResult
from backend.app.services.review_results import ReviewResultService
from backend.app.settings import Settings


def _evidence() -> Evidence:
    return Evidence(
        id="e-1",
        kind="document",
        asset_id="asset-1",
        block_id="block-1",
        line_start=1,
        line_end=2,
        evidence_level=EvidenceLevel.VERIFIED,
    )


def test_result_keeps_diagnostic_and_official_tracks_separate() -> None:
    result = ReviewResult(review_id="review-1", evidence=[_evidence()])
    assert result.diagnostic_scores == []
    assert result.official_scores == []
    assert result.to_snapshot()["review_id"] == "review-1"


def test_result_rejects_strong_claim_without_evidence() -> None:
    # model_construct simulates an untrusted deserialized payload.  Pydantic
    # revalidates the nested Claim and deterministically downgrades it.
    from backend.app.domain.review_protocol import Claim

    claim = Claim.model_construct(id="c-1", exact_text="x", verdict=Verdict.SUPPORTED, evidence_ids=[])
    result = ReviewResult(review_id="review-1", claims=[claim])
    assert result.claims[0].verdict is Verdict.INCONCLUSIVE


def test_result_service_resolves_claim_and_persists_json(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)
    repo = SqlAlchemyReviewJobRepository(settings)
    with session_scope(settings) as session:
        session.add(AssetRecord(id="asset-1", filename="paper.md", media_type="text/markdown", size_bytes=1, sha256="sha256:a", status="parsed", storage_path=str(tmp_path / "paper.md")))
        session.add(RubricProfileRecord(id="rubric-1", name="rubric", version="1", source_hash="sha256:b", status="published", warnings=[]))
    job = ReviewJob(
        id="review-result-1",
        asset_id="asset-1",
        rubric_profile_id="rubric-1",
        asset_sha256="sha256:a",
        rubric_source_hash="sha256:b",
        input_snapshot_hash="sha256:c",
    )
    repo.create(job)
    result = ReviewResult(review_id=job.id, evidence=[_evidence()])
    saved = ReviewResultService(repo).save(result)
    assert saved.review_id == job.id
    loaded = ReviewResultService(repo).load(job.id)
    assert loaded is not None
    assert loaded.evidence[0].location["block_id"] == "block-1"
