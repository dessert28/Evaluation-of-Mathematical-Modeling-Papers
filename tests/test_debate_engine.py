"""Unit tests for the debate engine and its background run manager.

These never reach a real LLM: a fake adapter that honors the adapter contract
(``complete_json`` returns ``(response_model_instance, metadata)``) drives every
scenario, and a fake store holds the persisted ``DebateSnapshot`` in memory.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from backend.app.domain.debate import (
    DebateError,
    DebateRound,
    DebateSnapshot,
    DebateStatus,
    MessageDraft,
    OpinionDraft,
    Stance,
)
from backend.app.domain.review_protocol import FindingSeverity
from backend.app.services.debate_engine import DebateRunManager, DebateService
from backend.app.services.llm_adapter import LLMAdapterError

EVIDENCE_IDS = ["e-1", "e-2", "e-3"]


def _stage_result(stage_id="model_construction"):
    return {"stage_id": stage_id, "evidence": [{"id": eid} for eid in EVIDENCE_IDS]}


class FakeJob:
    def __init__(self, review_id="review-1", state="EVALUATING"):
        self.id = review_id
        self.review_id = review_id
        self.state = state
        self.options = {"debate": {"enabled": True}}
        self.state_snapshot = {"stage_results": [_stage_result()]}


class FakeStore:
    def __init__(self):
        self.jobs = {"review-1": FakeJob()}
        self.snapshots = {}

    def get(self, review_id):
        return self.jobs.get(review_id)

    def save_debate_snapshot(self, review_id, snapshot):
        self.snapshots[review_id] = snapshot

    def get_debate_snapshot(self, review_id):
        return self.snapshots.get(review_id)

    def update(self, review_id, patch):
        # Present for interface completeness; the engine does not call it.
        self.snapshots.setdefault(review_id, {}).update(patch)
        return self.snapshots[review_id]


class FakePanelStore:
    experts = [
        SimpleNamespace(id="modeling", label="建模专家", lens="建模", weight=1.0),
        SimpleNamespace(id="code", label="代码审计专家", lens="代码", weight=1.0),
    ]

    def __init__(self, max_calls=30):
        self.max_calls = max_calls

    def load(self):
        return SimpleNamespace(
            experts=tuple(self.experts),
            max_rounds=2,
            min_rounds=1,
            agreement_threshold=0.8,
            accept_threshold=0.5,
            fatal_bonus=3.0,
            max_calls=self.max_calls,
            reject_retry=1,
            anonymize=True,
            max_opinions_per_expert=8,
        )

    def resolve_experts(self, expert_ids=None):
        if expert_ids is None:
            return tuple(self.experts)
        by_id = {expert.id: expert for expert in self.experts}
        unknown = [eid for eid in expert_ids if eid not in by_id]
        if unknown:
            raise ValueError(f"unknown expert ids: {unknown}")
        selected = tuple(by_id[eid] for eid in expert_ids)
        if len(selected) < 2:
            raise ValueError("at least two experts required")
        return selected


def _opinion_draft(n=0, title="目标函数缺少闭环约束", evidence=None, severity=FindingSeverity.MAJOR, stage="model_construction"):
    return OpinionDraft(
        stage_id=stage,
        title=title,
        detail=f"detail {n}",
        severity=severity,
        evidence_ids=evidence or ["e-1"],
        confidence=0.7,
    )


def _message_draft(target="op-0-expert-0-0", stance=Stance.AGREE, evidence=None, rationale="同意该判断"):
    return MessageDraft(
        target_opinion_id=target,
        stance=stance,
        evidence_ids=evidence or [],
        confidence=0.6,
        rationale=rationale,
    )


def _opinion_batch(drafts):
    from backend.app.domain.debate import PanelOpinionBatch

    return PanelOpinionBatch(opinions=drafts)


def _message_batch(drafts):
    from backend.app.domain.debate import DebateMessageBatch

    return DebateMessageBatch(messages=drafts)


class FakeAdapter:
    """Queue-driven adapter honoring ``(model, metadata)`` return contract."""

    def __init__(self, rounds=None, raise_no_model=False, raise_all=False):
        # rounds[round_index] -> list of per-expert response tuples or exceptions
        self.rounds = rounds or []
        self.raise_no_model = raise_no_model
        self.raise_all = raise_all
        self.calls = []
        self._lock = threading.Lock()

    def complete_json(self, *, system_prompt, user_prompt, response_model, temperature=0.0):
        self.calls.append((system_prompt, user_prompt, response_model))
        if self.raise_no_model:
            raise LLMAdapterError("llm_not_configured", "model not configured")
        if self.raise_all:
            raise LLMAdapterError("llm_transport_error", "transport failed")
        with self._lock:
            # Each entry in ``self.rounds`` is one debate round (a per-expert
            # queue).  Drain the current round before advancing to the next one.
            while self.rounds and not self.rounds[0]:
                self.rounds.pop(0)
            if not self.rounds:
                raise AssertionError("FakeAdapter: preset rounds exhausted")
            result = self.rounds[0].pop(0)
        if isinstance(result, Exception):
            raise result
        batch, _meta = result
        return batch, SimpleNamespace(model="fake", attempts=1, endpoint="fake")


class FakePromptStore:
    def __init__(self, adapter):
        self.adapter = adapter

    def debate_prompt(self, kind, **values):
        if kind not in {"panel_opinion", "debate_message"}:
            raise ValueError(f"unknown debate prompt kind: {kind}")
        return SimpleNamespace(
            version="v0.1",
            page_id=kind,
            stage_id=f"debate:{kind}",
            system="你是评审委员会专家",
            user=f"{kind}:{values}",
        )


def make_service(store=None, adapter=None, panel=None):
    store = store or FakeStore()
    adapter = adapter or FakeAdapter()
    panel = panel or FakePanelStore()
    prompt = FakePromptStore(adapter)
    return DebateService(
        store=store,
        adapter=adapter,
        panel_store=panel,
        prompt_store=prompt,
        context_builder=lambda job: ("论文上下文", "证据目录", "评分量表"),
        max_workers=2,
    )


# ---------------------------------------------------------------- round 0


def test_round0_generates_opinions_and_persists():
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1, title="随机种子未固定", evidence=["e-2"], stage="solving")]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.AGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1", options={"idempotency_key": "k1"})
    assert result["status"] == "COMPLETED"
    round0 = result["rounds"][0]
    assert round0["round_number"] == 0
    assert len(round0["opinions"]) == 2
    assert {opinion["expert_id"] for opinion in round0["opinions"]} == {"expert-1", "expert-2"}
    assert {opinion["id"] for opinion in round0["opinions"]} == {"op-0-expert-0-0", "op-0-expert-1-0"}
    assert all(opinion["id"].startswith("op-0-expert-") for opinion in round0["opinions"])
    by_expert = {opinion["expert_id"]: opinion for opinion in round0["opinions"]}
    assert by_expert["expert-1"]["lens"] == "建模专家"
    assert by_expert["expert-2"]["lens"] == "代码审计专家"
    assert round0["rejected"] == []
    # Round 0 keeps the configured panel order (no shuffling).
    assert round0["speaker_order"] == ["expert-1", "expert-2"]
    assert adapter.calls


def test_round0_rejects_unknown_evidence_and_records_it():
    # Both experts get the same pair (one valid, one unknown-evidence) so the
    # assertions do not depend on which parallel call pops which preset.
    opinion_pair = [
        _opinion_draft(0),  # valid (evidence e-1)
        _opinion_draft(1, evidence=["e-unknown"]),  # unknown evidence -> rejected
    ]
    adapter = FakeAdapter(
        rounds=[
            [(_opinion_batch(list(opinion_pair)), None), (_opinion_batch(list(opinion_pair)), None)],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.AGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1")
    round0 = result["rounds"][0]
    rejected = [item for item in round0["rejected"] if item["code"] == "invalid_evidence"]
    assert len(rejected) == 2
    assert {item["expert_id"] for item in rejected} == {"expert-1", "expert-2"}
    assert all(item["message"] for item in rejected)
    assert len(round0["opinions"]) == 2
    assert result["status"] == "COMPLETED"


def test_no_evidence_basis_rejects_with_409():
    store = FakeStore()
    store.jobs["review-1"].state_snapshot = {"stage_results": []}
    service = make_service(store=store)
    with pytest.raises(DebateError) as exc:
        service.run_sync("review-1")
    assert exc.value.code == "debate_not_ready"
    assert exc.value.status_code == 409


def test_invalid_job_state_rejects():
    store = FakeStore()
    store.jobs["review-1"].state = "REPORT_READY"
    service = make_service(store=store)
    with pytest.raises(DebateError) as exc:
        service.run_sync("review-1")
    assert exc.value.code == "review_not_ready"
    assert exc.value.status_code == 409


def test_missing_job_404():
    service = make_service()
    with pytest.raises(DebateError) as exc:
        service.run_sync("nope")
    assert exc.value.code == "debate_not_found"
    assert exc.value.status_code == 404


def test_unconfigured_model_fails_with_safe_code():
    adapter = FakeAdapter(raise_no_model=True)
    store = FakeStore()
    service = make_service(store=store, adapter=adapter)
    with pytest.raises(DebateError) as exc:
        service.run_sync("review-1")
    assert exc.value.code == "llm_not_configured"
    saved = store.get_debate_snapshot("review-1")
    assert saved["status"] == "FAILED"
    assert saved["last_error"]["code"] == "llm_not_configured"


def test_all_experts_fail_marks_failed():
    adapter = FakeAdapter(raise_all=True)
    store = FakeStore()
    service = make_service(store=store, adapter=adapter)
    with pytest.raises(DebateError) as exc:
        service.run_sync("review-1")
    assert exc.value.code == "debate_failed"
    saved = store.get_debate_snapshot("review-1")
    assert saved["status"] == "FAILED"
    # Full round0 failure must keep triage-safe per-expert code counts.
    rejected_codes = saved["last_error"]["details"]["rejected_codes"]
    assert sum(rejected_codes.values()) == len(saved["panel"])


# ---------------------------------------------------------------- debate rounds


def _converged_adapter():
    same_target = "op-0-expert-0-0"
    return FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
            [
                (_message_batch([_message_draft(target=same_target, stance=Stance.AGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )


def test_rounds_converge_and_complete():
    adapter = _converged_adapter()
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1", options={"idempotency_key": "conv"})
    assert result["status"] == "COMPLETED"
    debate_rounds = [r for r in result["rounds"] if r["round_number"] >= 1]
    assert len(debate_rounds) == 1
    assert debate_rounds[0]["messages"], "round 1 must hold messages"
    out = result["outcome"]
    assert out["converged"] is True
    assert out["stop_reason"] == "converged"
    assert set(out["accepted_opinion_ids"]) == {"op-0-expert-0-0", "op-0-expert-1-0"}


def test_unconverged_exhausts_max_rounds():
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.DISAGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.DISAGREE)]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.DISAGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.DISAGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1", options={"max_rounds": 2})
    assert result["status"] == "COMPLETED"
    assert result["outcome"]["converged"] is False
    assert result["outcome"]["stop_reason"] == "max_rounds"
    assert result["outcome"]["rounds_run"] == 2


def test_budget_exhaustion_stops():
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
        ]
    )
    store = FakeStore()
    service = make_service(store=store, adapter=adapter, panel=FakePanelStore(max_calls=2))
    # Round 0 already consumes the whole budget (2 experts, 2 calls).
    result = service.run_sync("review-1")
    assert result["status"] == "COMPLETED"
    assert result["outcome"]["stop_reason"] == "budget_exhausted"
    assert result["outcome"]["converged"] is False
    assert result["outcome"]["rounds_run"] == 0
    assert [r["round_number"] for r in result["rounds"]] == [0]
    assert result["call_budget"] == {"used": 2, "max": 2}
    assert len(adapter.calls) == 2  # round 1 was never executed


def test_refute_without_evidence_is_rejected():
    # A REFUTE draft without evidence can never pass the domain model validator,
    # so the real adapter rejects the whole batch with a decode error; the fake
    # mimics that by returning the same LLMAdapterError for that expert's call.
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
            [
                LLMAdapterError("schema_validation_failed", "REFUTE requires evidence"),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1", options={"max_rounds": 1})
    round1 = [r for r in result["rounds"] if r["round_number"] == 1][0]
    refuted = [m for m in round1["messages"] if m["stance"] == "REFUTE"]
    assert not refuted, "REFUTE without evidence must be dropped"
    # The rejected batch is recorded as a rejection, the other expert's AGREE survives.
    assert any(item["code"] == "schema_validation_failed" for item in round1["rejected"])
    assert any(m["stance"] == "AGREE" for m in round1["messages"])


def test_refute_with_unknown_evidence_is_rejected():
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.REFUTE, evidence=["e-zzz"])]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1", options={"max_rounds": 1})
    round1 = [r for r in result["rounds"] if r["round_number"] == 1][0]
    assert all(m["stance"] != "REFUTE" for m in round1["messages"])
    assert any(item["code"] == "invalid_evidence" for item in round1["rejected"])


def test_fatal_bonus_drives_acceptance():
    adapter = FakeAdapter(
        rounds=[
            [
                (_opinion_batch([_opinion_draft(0, severity=FindingSeverity.FATAL)]), None),
                (_opinion_batch([_opinion_draft(1)]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.DISAGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
            [
                (_message_batch([_message_draft(target="op-0-expert-0-0", stance=Stance.AGREE)]), None),
                (_message_batch([_message_draft(target="op-0-expert-1-0", stance=Stance.AGREE)]), None),
            ],
        ]
    )
    service = make_service(adapter=adapter)
    result = service.run_sync("review-1")
    tally = result["outcome"]["vote_tally"]
    # Fatal opinion: -1 (DISAGREE) + 1 (AGREE) + fatal_bonus 3.0 = 3.0, accepted
    # despite the opposing vote (without the bonus the net score would be 0.0).
    assert tally["op-0-expert-0-0"] == 3.0
    assert tally["op-0-expert-1-0"] == 2.0
    assert set(result["outcome"]["accepted_opinion_ids"]) == {
        "op-0-expert-0-0",
        "op-0-expert-1-0",
    }
    assert result["outcome"]["stop_reason"] == "max_rounds"
    assert result["outcome"]["rounds_run"] == 2


# ---------------------------------------------------------------- run manager


def test_run_manager_submit_and_get():
    adapter = _converged_adapter()
    store = FakeStore()
    service = make_service(store=store, adapter=adapter)
    manager = DebateRunManager(service)
    payload = manager.submit("review-1", options={}, idempotency_key="mg1")
    assert payload["debate_status"] == "QUEUED"
    # Give the background thread a moment to finish.
    import time

    for _ in range(50):
        snap = store.get_debate_snapshot("review-1")
        if snap and snap.get("status") not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(0.1)
    snap = manager.get("review-1")
    assert snap is not None
    assert snap["status"] in {"COMPLETED", "DEGRADED", "FAILED"}


def test_run_manager_rejects_active_duplicate():
    store = FakeStore()
    # Pre-seed an active debate.
    store.snapshots["review-1"] = {
        "review_id": "review-1",
        "status": "RUNNING",
        "config": {"idempotency_key": "other"},
        "rounds": [],
        "call_budget": {"used": 0, "max": 30},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    service = make_service(store=store, adapter=FakeAdapter())
    manager = DebateRunManager(service)
    with pytest.raises(DebateError) as exc:
        manager.submit("review-1", options={}, idempotency_key="dup")
    assert exc.value.code == "debate_already_active"


def test_run_manager_idempotent_reuse():
    store = FakeStore()
    store.snapshots["review-1"] = {
        "review_id": "review-1",
        "status": "COMPLETED",
        "config": {"idempotency_key": "same"},
        "rounds": [],
        "call_budget": {"used": 1, "max": 30},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    service = make_service(store=store, adapter=FakeAdapter())
    manager = DebateRunManager(service)
    payload = manager.submit("review-1", options={}, idempotency_key="same")
    assert payload["debate_status"] == "COMPLETED"


def test_recover_one_marks_interrupted():
    store = FakeStore()
    store.snapshots["review-1"] = {
        "review_id": "review-1",
        "status": "RUNNING",
        "config": {},
        "rounds": [],
        "call_budget": {"used": 0, "max": 30},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    service = make_service(store=store, adapter=FakeAdapter())
    manager = DebateRunManager(service)
    manager.recover_one("review-1")
    assert store.get_debate_snapshot("review-1")["status"] == "INTERRUPTED"


def test_engine_accepts_wrong_state_rejects_with_409():
    store = FakeStore()
    store.jobs["review-1"].state = "FROZEN"
    service = make_service(store=store, adapter=FakeAdapter())
    with pytest.raises(DebateError) as exc:
        service.run_sync("review-1")
    assert exc.value.code == "review_not_ready"
    assert exc.value.status_code == 409


# ---------------------------------------------------------------- determinism & idempotency


def test_speaker_order_deterministic_for_same_review_and_round():
    def run_once(key):
        store = FakeStore()
        adapter = _converged_adapter()
        service = make_service(store=store, adapter=adapter)
        result = service.run_sync("review-1", options={"idempotency_key": key})
        return [r["speaker_order"] for r in result["rounds"]]

    first = run_once("det-a")
    second = run_once("det-b")
    # Same review_id + round => same seeded shuffle, even across different keys.
    assert first == second
    assert first[0] == ["expert-1", "expert-2"]  # round 0 keeps configured order
    assert sorted(first[1]) == ["expert-1", "expert-2"]


def test_run_sync_idempotency_key_reuses_snapshot():
    adapter = _converged_adapter()
    service = make_service(adapter=adapter)
    first = service.run_sync("review-1", options={"idempotency_key": "same"})
    second = service.run_sync("review-1", options={"idempotency_key": "same"})
    assert second == first
    assert len(adapter.calls) == 4  # the second call reused the snapshot, no new run
