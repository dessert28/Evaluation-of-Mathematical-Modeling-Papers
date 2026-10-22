from __future__ import annotations

from datetime import datetime, timezone

from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.services.review_coordinator import ReviewCoordinator
from backend.app.services.state_machine import ReviewJobStateMachine, ReviewState


class MemoryReviewStore:
    def __init__(self, job: ReviewJob):
        self.job = job

    def get(self, job_id: str):
        return self.job if self.job.id == job_id else None

    def update(self, job: ReviewJob):
        self.job = job
        return job


def _job() -> ReviewJob:
    return ReviewJob(
        id="review-state-1",
        asset_id="asset-1",
        rubric_profile_id="rubric-1",
        asset_sha256="sha256:a",
        rubric_source_hash="sha256:b",
        input_snapshot_hash="sha256:c",
    )


def test_coordinator_persists_state_snapshot_and_events():
    store = MemoryReviewStore(_job())
    updated = ReviewCoordinator(store).transition("review-state-1", ReviewState.INGESTING, reason="开始解析")
    assert updated.state is ReviewJobStatus.INGESTING
    assert updated.state_snapshot["events"][0]["to_state"] == "INGESTING"

    restored = ReviewJobStateMachine.from_dict(updated.state_snapshot)
    assert restored.state is ReviewState.INGESTING
    assert len(restored.events) == 1


def test_rerun_idempotency_survives_snapshot_restore():
    machine = ReviewJobStateMachine("review-rerun")
    machine.transition(ReviewState.INGESTING, reason="开始解析")
    machine.rerun(ReviewState.INGESTING, reason="重跑解析", idempotency_key="rerun-1")
    restored = ReviewJobStateMachine.from_dict(machine.to_dict())
    restored.rerun(ReviewState.INGESTING, reason="重复请求", idempotency_key="rerun-1")
    assert len(restored.events) == 2


def test_transition_requires_asset_freeze_gate():
    machine = ReviewJobStateMachine("review-frozen")
    machine.transition(ReviewState.INGESTING, reason="开始解析")
    try:
        machine.transition(ReviewState.ASSETS_FROZEN, reason="冻结", assets_frozen=False)
    except ValueError as exc:
        assert "asset freeze" in str(exc)
    else:
        raise AssertionError("asset freeze gate must reject an unconfirmed transition")
