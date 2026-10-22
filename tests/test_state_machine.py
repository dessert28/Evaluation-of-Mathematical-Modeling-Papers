from __future__ import annotations

import pytest

from backend.app.services.state_machine import (
    InvalidTransitionError,
    ReviewJobStateMachine,
    ReviewState,
)


def advance_to(machine: ReviewJobStateMachine, target: ReviewState) -> None:
    path = [
        ReviewState.INGESTING,
        ReviewState.ASSETS_FROZEN,
        ReviewState.RUBRIC_CONFIRMATION,
        ReviewState.EVALUATING,
        ReviewState.EVIDENCE_AUDIT,
        ReviewState.ARBITRATING,
        ReviewState.REPORT_READY,
    ]
    for state in path:
        if machine.state is state:
            return
        kwargs = {}
        if state is ReviewState.ASSETS_FROZEN:
            kwargs["assets_frozen"] = True
        if state is ReviewState.EVALUATING:
            kwargs.update(rubric_published=True, human_confirmed=True)
        machine.transition(state, reason=f"advance to {state.value}", **kwargs)
        if state is target:
            return


def test_happy_path_requires_each_predecessor() -> None:
    machine = ReviewJobStateMachine("review-1")
    assert machine.state is ReviewState.CREATED

    with pytest.raises(InvalidTransitionError):
        machine.transition(ReviewState.ASSETS_FROZEN, reason="skip ingestion")

    for state in (
        ReviewState.INGESTING,
        ReviewState.ASSETS_FROZEN,
        ReviewState.RUBRIC_CONFIRMATION,
        ReviewState.EVALUATING,
        ReviewState.EVIDENCE_AUDIT,
        ReviewState.ARBITRATING,
        ReviewState.REPORT_READY,
    ):
        kwargs = {}
        if state is ReviewState.ASSETS_FROZEN:
            kwargs["assets_frozen"] = True
        if state is ReviewState.EVALUATING:
            kwargs.update(rubric_published=True, human_confirmed=True)
        machine.transition(state, reason=f"completed {state.value}", **kwargs)

    assert machine.state is ReviewState.REPORT_READY
    assert [event.to_state for event in machine.events] == [
        ReviewState.INGESTING,
        ReviewState.ASSETS_FROZEN,
        ReviewState.RUBRIC_CONFIRMATION,
        ReviewState.EVALUATING,
        ReviewState.EVIDENCE_AUDIT,
        ReviewState.ARBITRATING,
        ReviewState.REPORT_READY,
    ]


def test_same_transition_is_idempotent_and_does_not_duplicate_event() -> None:
    machine = ReviewJobStateMachine("review-2")
    machine.transition(ReviewState.INGESTING, reason="start")
    event_count = len(machine.events)

    machine.transition(ReviewState.INGESTING, reason="retry start")

    assert machine.state is ReviewState.INGESTING
    assert len(machine.events) == event_count


def test_mark_stale_records_reason_and_rerun_clears_stale() -> None:
    machine = ReviewJobStateMachine("review-3")
    machine.transition(ReviewState.INGESTING, reason="start", input_hash="v1")
    machine.mark_stale(reason="paper asset changed", dependency="asset:paper")

    assert machine.stale is True
    assert machine.stale_reason == "paper asset changed"
    assert machine.events[-1].event_type == "STALE_MARKED"

    machine.rerun(
        ReviewState.INGESTING,
        reason="re-ingest changed paper",
        input_hash="v2",
        idempotency_key="rerun-paper-v2",
        clear_dependency="asset:paper",
    )
    assert machine.state is ReviewState.INGESTING
    assert machine.stale is False
    assert machine.events[-1].event_type == "RERUN"


def test_blocked_requires_new_verified_evidence_to_resume() -> None:
    machine = ReviewJobStateMachine("review-4")
    advance_to(machine, ReviewState.ARBITRATING)
    machine.transition(
        ReviewState.BLOCKED,
            reason="core claim lacks reproducible evidence",
            evidence_fingerprint="old-evidence",
            findings=("fatal",),
            verified_evidence_ids=("ev-old",),
        )

    with pytest.raises(InvalidTransitionError):
        machine.transition(
            ReviewState.EVIDENCE_AUDIT,
            reason="retry without new evidence",
            evidence_fingerprint="old-evidence",
            new_verified_evidence=True,
            verified_evidence_bundle=({"id": "ev-old", "level": "INDEPENDENTLY_VERIFIED", "locator": "page:1"},),
        )

    with pytest.raises(InvalidTransitionError):
        machine.transition(
            ReviewState.EVIDENCE_AUDIT,
            reason="unverified evidence",
            evidence_fingerprint="new-evidence",
            new_verified_evidence=False,
            verified_evidence_bundle=({"id": "ev-new", "level": "VERIFIED", "locator": "page:2"},),
        )

    machine.transition(
        ReviewState.EVIDENCE_AUDIT,
        reason="new independently verified evidence",
        evidence_fingerprint="new-evidence",
        new_verified_evidence=True,
        verified_evidence_bundle=({"id": "ev-new", "level": "INDEPENDENTLY_VERIFIED", "locator": "page:2"},),
    )
    assert machine.state is ReviewState.EVIDENCE_AUDIT


def test_event_ledger_contains_hashes_and_is_read_only() -> None:
    machine = ReviewJobStateMachine("review-5")
    machine.transition(
        ReviewState.INGESTING,
        reason="start",
        input_hash="paper-v1",
        evidence_fingerprint="asset-snapshot",
    )

    event = machine.events[0]
    assert event.job_id == "review-5"
    assert event.from_state is ReviewState.CREATED
    assert event.to_state is ReviewState.INGESTING
    assert event.input_hash == "paper-v1"
    assert event.evidence_fingerprint == "asset-snapshot"
    assert event.reason == "start"
    assert event.timestamp.tzinfo is not None

    with pytest.raises(AttributeError):
        machine.events.append(event)  # type: ignore[attr-defined]


def test_terminal_frozen_state_rejects_mutation() -> None:
    machine = ReviewJobStateMachine("review-6")
    advance_to(machine, ReviewState.REPORT_READY)
    machine.transition(ReviewState.FROZEN, reason="human approved final report", final_confirmed=True)

    with pytest.raises(InvalidTransitionError):
        machine.rerun(ReviewState.EVALUATING, reason="late rerun", input_hash="v2")


def test_only_deterministic_coordinator_can_transition() -> None:
    machine = ReviewJobStateMachine("review-7")
    with pytest.raises(InvalidTransitionError):
        machine.transition(ReviewState.INGESTING, reason="model tried", actor="gpt-6-luna")


def test_rerun_idempotency_key_does_not_duplicate_event() -> None:
    machine = ReviewJobStateMachine("review-8")
    machine.transition(ReviewState.INGESTING, reason="start", input_hash="v1")
    machine.rerun(ReviewState.INGESTING, reason="retry", input_hash="v1", idempotency_key="retry-1")
    count = len(machine.events)
    machine.rerun(ReviewState.INGESTING, reason="retry duplicate", input_hash="v1", idempotency_key="retry-1")
    assert len(machine.events) == count


def test_rerun_cannot_skip_unreached_predecessor_gates() -> None:
    machine = ReviewJobStateMachine("review-9")
    with pytest.raises(InvalidTransitionError):
        machine.rerun(ReviewState.EVALUATING, reason="skip gates", input_hash="v1")


def test_outcome_state_requires_matching_finding_severity() -> None:
    machine = ReviewJobStateMachine("review-10")
    advance_to(machine, ReviewState.ARBITRATING)
    with pytest.raises(InvalidTransitionError):
        machine.transition(ReviewState.REVIEWABLE, reason="hide fatal", findings=("fatal",))
    machine.transition(ReviewState.BLOCKED, reason="fatal confirmed", findings=("fatal",), evidence_fingerprint="fatal-v1")


def test_report_ready_and_frozen_apply_cumulative_finding_gate() -> None:
    machine = ReviewJobStateMachine("review-result-gate")
    advance_to(machine, ReviewState.ARBITRATING)

    with pytest.raises(InvalidTransitionError, match="REPORT_READY"):
        machine.transition(
            ReviewState.REPORT_READY,
            reason="attempt to hide major finding",
            findings=("major",),
        )

    # A finding recorded while entering arbitration remains effective even if
    # a later report request omits the findings field.
    machine = ReviewJobStateMachine("review-cumulative-gate")
    advance_to(machine, ReviewState.EVIDENCE_AUDIT)
    machine.transition(
        ReviewState.ARBITRATING,
        reason="major finding recorded",
        findings=("major",),
    )
    with pytest.raises(InvalidTransitionError, match="REPORT_READY"):
        machine.transition(ReviewState.REPORT_READY, reason="omit major finding")

    clean = ReviewJobStateMachine("review-freeze-gate")
    advance_to(clean, ReviewState.REPORT_READY)
    with pytest.raises(InvalidTransitionError, match="FROZEN"):
        clean.transition(
            ReviewState.FROZEN,
            reason="attempt to freeze with fatal finding",
            findings=("fatal",),
            final_confirmed=True,
        )


def test_same_stage_input_hash_change_marks_stale() -> None:
    machine = ReviewJobStateMachine("review-11")
    machine.transition(ReviewState.INGESTING, reason="start", input_hash="v1")
    machine.transition(ReviewState.INGESTING, reason="same stage changed input", input_hash="v2")
    assert machine.stale is True
    assert machine.current_input_hash == "v2"


def test_snapshot_is_json_friendly() -> None:
    machine = ReviewJobStateMachine("review-7")
    machine.transition(ReviewState.INGESTING, reason="start")

    snapshot = machine.to_dict()

    assert snapshot["state"] == "INGESTING"
    assert snapshot["events"][0]["from_state"] == "CREATED"
    assert snapshot["events"][0]["to_state"] == "INGESTING"
