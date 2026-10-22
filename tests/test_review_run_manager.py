from types import SimpleNamespace

import pytest

from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.services.review_run_manager import ReviewRunManager, ReviewRunManagerError


class Store:
    def __init__(self, job):
        self.job = job

    def list(self):
        return [self.job]

    def get(self, _):
        return self.job

    def update(self, job):
        self.job = job
        return job


class Executor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))
        return SimpleNamespace(done=lambda: False)


class Adapter:
    settings = SimpleNamespace(openai_compatible_model="test-model")


def job(state=ReviewJobStatus.EVALUATING, snapshot=None):
    return ReviewJob(
        id="review-1", asset_id="asset-1", rubric_profile_id="rubric-1",
        asset_sha256="asset-hash", rubric_source_hash="rubric-hash",
        input_snapshot_hash="input-hash", state=state, state_snapshot=snapshot or {},
    )


def manager(store, executor=None, asset_hash="asset-hash", rubric_hash="rubric-hash"):
    instance = ReviewRunManager.__new__(ReviewRunManager)
    instance.store = store
    instance.asset_store = SimpleNamespace(get=lambda _: SimpleNamespace(status="parsed", sha256=asset_hash))
    instance.rubric_store = SimpleNamespace(get=lambda _: SimpleNamespace(status="published", source_hash=rubric_hash))
    instance.settings = SimpleNamespace(app_timezone="Asia/Shanghai")
    instance.adapter = Adapter()
    instance._executor = executor or Executor()
    from threading import RLock
    instance._lock = RLock()
    instance._futures = {}
    return instance


def test_run_rejects_changed_asset_or_rubric_snapshot():
    store = Store(job())
    runner = manager(store, asset_hash="changed")
    with pytest.raises(ReviewRunManagerError) as error:
        runner.start_run("review-1", idempotency_key="key-1")
    assert error.value.code == "input_snapshot_changed"


def test_run_idempotency_key_cannot_be_reused_for_different_request():
    store = Store(job())
    runner = manager(store)
    runner.start_run("review-1", stage_ids=["solving"], idempotency_key="key-1")
    with pytest.raises(ReviewRunManagerError) as error:
        runner.start_run("review-1", stage_ids=["assumptions"], idempotency_key="key-1")
    assert error.value.code == "idempotency_conflict"


def test_start_run_rejects_job_without_human_evaluation_gate():
    runner = manager(Store(job(ReviewJobStatus.CREATED)))
    with pytest.raises(ReviewRunManagerError) as error:
        runner.start_run("review-1", idempotency_key="key-1")
    assert error.value.code == "review_not_ready"


def test_manager_marks_abandoned_run_interrupted_on_restart():
    store = Store(job(snapshot={"run": {"run_status": "RUNNING", "run_id": "old"}}))
    instance = ReviewRunManager(
        store,
        SimpleNamespace(get=lambda _: SimpleNamespace(status="parsed", sha256="asset-hash")),
        SimpleNamespace(get=lambda _: SimpleNamespace(status="published", source_hash="rubric-hash")),
        SimpleNamespace(app_timezone="Asia/Shanghai"),
        adapter=Adapter(),
    )
    instance._executor.shutdown(wait=False)
    assert store.job.state is ReviewJobStatus.DEGRADED
    assert store.job.state_snapshot["run"]["run_status"] == "INTERRUPTED"


def test_coordinator_transition_preserves_run_metadata():
    from backend.app.services.review_coordinator import ReviewCoordinator
    from backend.app.services.state_machine import ReviewState

    existing = job(snapshot={
        "job_id": "review-1", "state": "EVALUATING", "events": [],
        "run": {"run_status": "COMPLETED"},
        "stage_results": {"solving": {"raw_score_0_10": 8}},
    })
    store = Store(existing)
    ReviewCoordinator(store).transition("review-1", ReviewState.EVIDENCE_AUDIT, reason="stages complete")
    assert store.job.state_snapshot["run"]["run_status"] == "COMPLETED"
    assert "solving" in store.job.state_snapshot["stage_results"]


def test_stage_rerun_from_evidence_audit_resumes_evaluating_before_queueing():
    store = Store(job(ReviewJobStatus.EVIDENCE_AUDIT))
    executor = Executor()
    runner = manager(store, executor=executor)
    queued = runner.start_stage_run("review-1", "assumptions", idempotency_key="stage-rerun-1")
    assert queued["run_status"] == "QUEUED"
    assert queued["requested_stages"] == ["assumptions"]
    assert store.job.state is ReviewJobStatus.EVALUATING
    assert store.job.state_snapshot["stage_stale"]["assumptions"] is True
