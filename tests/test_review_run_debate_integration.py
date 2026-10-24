"""Integration tests: seven-stage ReviewRunManager wired to the debate layer.

All model access is faked: the stage adapter returns canned StageResults and a
fake debate service records ``run_sync`` calls.  The real ``DebateRunManager``
is used for crash recovery.  ``ReviewCoordinator`` is monkeypatched with a
recording fake so the tests assert on the transition without a state machine.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.app.services.review_run_manager as run_manager_module
from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.domain.debate import DebateError
from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.domain.review_protocol import Evidence, EvidenceLevel
from backend.app.services.automatic_runner import AutomaticReviewRunner
from backend.app.services.debate_engine import DebateRunManager
from backend.app.services.review_run_manager import ReviewRunManager
from backend.app.services.stage_orchestrator import StageOrchestrator, StageResult
from backend.app.services.state_machine import ReviewState

STAGE_IDS = list(AutomaticReviewRunner.stage_ids)


def make_asset():
    blocks = (DocumentBlock("b1", "a1", "paragraph", "论文正文", page=1, paragraph=1, block_order=0),)
    return Asset(
        "a1",
        "paper.md",
        "text/markdown",
        10,
        "h1",
        ParseStatus.PARSED,
        Path("paper.md"),
        ParsedDocument(ParseStatus.PARSED, blocks=blocks),
    )


def make_stage_result(stage_id):
    return StageResult(
        stage_id=stage_id,
        raw_score_0_10=8,
        rationale="ok",
        evidence=[
            Evidence(
                id=f"e-{stage_id}",
                kind="paper",
                asset_id="a1",
                block_id="b1",
                page=1,
                evidence_level=EvidenceLevel.VERIFIED,
            )
        ],
    )


class Store:
    """In-memory ReviewJob repository including the debate snapshot columns."""

    def __init__(self, job):
        self.job = job
        self.debates = {}

    def list(self):
        return [self.job]

    def get(self, _review_id):
        return self.job

    def update(self, job):
        self.job = job
        return job

    def save_result_snapshot(self, _review_id, snapshot):
        self.result = snapshot

    def get_result_snapshot(self, _review_id):
        return getattr(self, "result", None)

    def save_debate_snapshot(self, review_id, snapshot):
        self.debates[review_id] = snapshot

    def get_debate_snapshot(self, review_id):
        return self.debates.get(review_id)


class PlainStore:
    """Store without the debate snapshot methods (like the original fakes)."""

    def __init__(self, job):
        self.job = job

    def get(self, _review_id):
        return self.job

    def update(self, job):
        self.job = job
        return job


class StageAdapter:
    def __init__(self):
        self.calls = []

    def evaluate_stage(self, stage_id, **kwargs):
        self.calls.append(stage_id)
        return make_stage_result(stage_id), SimpleNamespace(model="test", attempts=1, endpoint="http://local")


class FakeDebateService:
    """Stand-in for DebateService: records calls and persists a snapshot."""

    def __init__(self, store, *, fail=False):
        self.store = store
        self.calls = []
        self.fail = fail

    def run_sync(self, review_id, *, options=None):
        options = dict(options or {})
        self.calls.append((review_id, options))
        if self.fail:
            raise DebateError("debate_failed", "辩论未能产生有效结果", status_code=422)
        self.store.save_debate_snapshot(
            review_id,
            {"status": "COMPLETED", "review_id": review_id, "config": {"idempotency_key": options.get("idempotency_key")}},
        )
        return self.store.get_debate_snapshot(review_id)


class FakeCoordinator:
    instances: list["FakeCoordinator"] = []

    def __init__(self, store, *, timezone_name=None):
        self.transitions = []
        FakeCoordinator.instances.append(self)

    def transition(self, review_id, target, *, reason):
        self.transitions.append((review_id, target, reason))
        return SimpleNamespace()


def make_job(**kwargs):
    defaults = dict(
        id="review-1",
        asset_id="a1",
        rubric_profile_id="r1",
        asset_sha256="h1",
        rubric_source_hash="rubric-hash",
        input_snapshot_hash="ih",
        state=ReviewJobStatus.EVALUATING,
        options={"debate": {"enabled": True, "max_rounds": 2}},
        state_snapshot={},
    )
    defaults.update(kwargs)
    return ReviewJob(**defaults)


def make_manager(store, *, debate_service=None, debate_runner=None):
    return ReviewRunManager(
        store,
        SimpleNamespace(get=lambda _: make_asset()),
        SimpleNamespace(get=lambda _: SimpleNamespace(status="published", source_hash="rubric-hash")),
        SimpleNamespace(app_timezone="Asia/Shanghai"),
        adapter=StageAdapter(),
        debate_service=debate_service,
        debate_runner=debate_runner,
    )


def _execute(manager, store, *, debate_service=None, monkeypatch):
    FakeCoordinator.instances = []
    monkeypatch.setattr(run_manager_module, "ReviewCoordinator", FakeCoordinator)
    try:
        manager._execute("review-1", "run-1", STAGE_IDS, False, "key-1")
    finally:
        manager._executor.shutdown(wait=False)
    return FakeCoordinator.instances[-1]


def test_full_run_triggers_debate_then_evidence_audit(monkeypatch):
    store = Store(make_job())
    debate = FakeDebateService(store)
    manager = make_manager(store, debate_service=debate)
    coordinator = _execute(manager, store, monkeypatch=monkeypatch)

    assert debate.calls == [("review-1", {"enabled": True, "max_rounds": 2})]
    assert store.get_debate_snapshot("review-1")["status"] == "COMPLETED"
    run = store.job.state_snapshot["run"]
    assert run["run_status"] == "COMPLETED"
    assert run["last_error"] is None
    assert run["idempotency_key"] == "key-1"
    assert coordinator.transitions == [("review-1", ReviewState.EVIDENCE_AUDIT, "七阶段自动评审完成")]


def test_debate_failure_degrades_run_but_keeps_stage_results(monkeypatch):
    store = Store(make_job())
    debate = FakeDebateService(store, fail=True)
    manager = make_manager(store, debate_service=debate)
    coordinator = _execute(manager, store, monkeypatch=monkeypatch)

    run = store.job.state_snapshot["run"]
    assert run["run_status"] == "DEGRADED"
    assert run["last_error"] == {"code": "debate_failed", "message": "辩论运行失败，但评审阶段结果有效"}
    assert len(run["completed_stages"]) == len(STAGE_IDS)
    # The debate snapshot itself is not persisted by the failed fake.
    assert store.get_debate_snapshot("review-1") is None
    # The stage results still drive the normal lifecycle transition.
    assert coordinator.transitions == [("review-1", ReviewState.EVIDENCE_AUDIT, "七阶段自动评审完成")]


def test_debate_disabled_skips_run_sync(monkeypatch):
    store = Store(make_job(options={"debate": {"enabled": False}}))
    debate = FakeDebateService(store)
    manager = make_manager(store, debate_service=debate)
    coordinator = _execute(manager, store, monkeypatch=monkeypatch)

    assert debate.calls == []
    assert store.get_debate_snapshot("review-1") is None
    assert store.job.state_snapshot["run"]["run_status"] == "COMPLETED"
    assert coordinator.transitions == [("review-1", ReviewState.EVIDENCE_AUDIT, "七阶段自动评审完成")]


def test_run_without_debate_service_never_calls_debate(monkeypatch):
    store = Store(make_job())
    manager = make_manager(store)
    coordinator = _execute(manager, store, monkeypatch=monkeypatch)

    assert store.get_debate_snapshot("review-1") is None
    assert store.job.state_snapshot["run"]["run_status"] == "COMPLETED"
    assert coordinator.transitions == [("review-1", ReviewState.EVIDENCE_AUDIT, "七阶段自动评审完成")]


@pytest.mark.parametrize("initial", ["QUEUED", "RUNNING"])
def test_recover_interrupted_marks_active_debate_interrupted(initial):
    store = Store(make_job())
    store.save_debate_snapshot("review-1", {"status": initial, "rounds": []})
    debate_runner = DebateRunManager(FakeDebateService(store), max_workers=1)
    try:
        make_manager(store, debate_runner=debate_runner)
    finally:
        debate_runner._executor.shutdown(wait=False)
    assert store.get_debate_snapshot("review-1")["status"] == "INTERRUPTED"


def test_recover_interrupted_leaves_finished_debate_untouched():
    store = Store(make_job())
    store.save_debate_snapshot("review-1", {"status": "COMPLETED", "rounds": []})
    debate_runner = DebateRunManager(FakeDebateService(store), max_workers=1)
    try:
        make_manager(store, debate_runner=debate_runner)
    finally:
        debate_runner._executor.shutdown(wait=False)
    assert store.get_debate_snapshot("review-1")["status"] == "COMPLETED"


def test_rerun_stage_marks_debate_snapshot_stale():
    store = Store(make_job())
    store.save_debate_snapshot("review-1", {"status": "COMPLETED", "rounds": [{}]})
    orchestrator = StageOrchestrator(
        store, SimpleNamespace(get=lambda _: make_asset()), timezone_name="Asia/Shanghai"
    )
    orchestrator.rerun_stage("review-1", "solving", reason="manual re-evaluation")

    assert store.job.state_snapshot["stage_stale"]["solving"] is True
    assert store.get_debate_snapshot("review-1")["stale"] is True


def test_rerun_stage_without_debate_snapshot_is_unaffected():
    store = Store(make_job())
    orchestrator = StageOrchestrator(
        store, SimpleNamespace(get=lambda _: make_asset()), timezone_name="Asia/Shanghai"
    )
    orchestrator.rerun_stage("review-1", "solving", reason="manual re-evaluation")

    assert store.job.state_snapshot["stage_stale"]["solving"] is True
    assert store.get_debate_snapshot("review-1") is None


def test_rerun_stage_with_store_lacking_debate_methods_is_unchanged():
    store = PlainStore(make_job())
    orchestrator = StageOrchestrator(
        store, SimpleNamespace(get=lambda _: make_asset()), timezone_name="Asia/Shanghai"
    )
    orchestrator.rerun_stage("review-1", "solving", reason="manual re-evaluation")
    assert store.job.state_snapshot["stage_stale"]["solving"] is True
