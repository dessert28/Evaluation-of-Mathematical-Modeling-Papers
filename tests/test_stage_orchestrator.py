from pathlib import Path

import pytest

from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.domain.review_jobs import ReviewJob
from backend.app.domain.review_protocol import Evidence, EvidenceLevel
from backend.app.services.stage_orchestrator import StageOrchestrator, StageOrchestratorError, StageResult


class JobStore:
    def __init__(self, job):
        self.jobs = {job.id: job}

    def get(self, job_id):
        return self.jobs.get(job_id)

    def update(self, job):
        self.jobs[job.id] = job
        return job


def _asset(status=ParseStatus.PARSED):
    block = DocumentBlock("block-1", "asset-1", "paragraph", "evidence", line_start=1, line_end=1)
    return Asset(
        id="asset-1", filename="paper.md", media_type="text/markdown", size_bytes=8,
        sha256="sha256:abc", status=status, storage_path=Path("paper.md"),
        parsed_document=ParsedDocument(status, (block,)),
    )


def _job():
    return ReviewJob(
        id="review-1", asset_id="asset-1", rubric_profile_id="rubric-1",
        asset_sha256="sha256:abc", rubric_source_hash="sha256:def",
        input_snapshot_hash="sha256:snapshot",
    )


def _result(stage):
    return StageResult(
        stage_id=stage, raw_score_0_10=8, rationale="document evidence inspected",
        evidence=[Evidence(id=f"ev-{stage}", kind="document", asset_id="asset-1", block_id="block-1", line_start=1, evidence_level=EvidenceLevel.VERIFIED)],
    )


def test_stage_result_uses_protocol_stage_ids_and_weights():
    result = _result("model_construction")
    assert result.weight == 0.20
    assert result.criterion_score().weight == 0.20
    assert result.criterion_score().normalized_score_0_4 == 3.2


def test_stage_write_requires_parsed_asset_and_located_evidence():
    job = _job()
    store = JobStore(job)
    assets = {"asset-1": _asset(ParseStatus.FAILED)}
    orchestrator = StageOrchestrator(store, assets)
    with pytest.raises(StageOrchestratorError, match="must be parsed"):
        orchestrator.write_result(job.id, _result("assumptions"))

    assets["asset-1"] = _asset()
    bad = _result("assumptions").model_copy(update={"evidence": [Evidence(id="ev", kind="document", asset_id="asset-1")]})
    with pytest.raises(StageOrchestratorError, match="stable location"):
        orchestrator.write_result(job.id, bad)


def test_stage_result_references_are_checked_and_rerun_marks_downstream_stale():
    job = _job()
    store = JobStore(job)
    orchestrator = StageOrchestrator(store, {"asset-1": _asset()})
    orchestrator.write_result(job.id, _result("problem_identification"))
    orchestrator.write_result(job.id, _result("assumptions"))
    updated = orchestrator.rerun_stage(job.id, "problem_identification", reason="题意解释已修订")
    stale = updated.state_snapshot["stage_stale"]
    assert stale["problem_identification"] is True
    assert stale["assumptions"] is True
    assert stale["results_analysis"] is True
    refreshed = orchestrator.write_result(job.id, _result("problem_identification"))
    assert refreshed.state_snapshot["stage_stale"]["problem_identification"] is False


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError, match="unknown diagnostic stage"):
        _result("not-a-stage")
