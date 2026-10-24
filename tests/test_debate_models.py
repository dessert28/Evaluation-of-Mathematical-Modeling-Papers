"""Unit tests for the debate domain models (iteration 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.domain.debate import (
    DebateMessage,
    DebateMessageBatch,
    DebateOutcome,
    DebateRound,
    DebateSnapshot,
    DebateStatus,
    MessageDraft,
    OpinionDraft,
    PanelOpinion,
    PanelOpinionBatch,
    Stance,
)
from backend.app.domain.review_protocol import FindingSeverity


def make_opinion(**overrides) -> PanelOpinion:
    values = {
        "id": "op-0-expert-1-1",
        "expert_id": "expert-1",
        "stage_id": "model_construction",
        "lens": "algorithm",
        "title": "门控单元稳定性结论缺支撑",
        "detail": "详细说明",
        "severity": FindingSeverity.MAJOR,
        "evidence_ids": ["ev-model-1"],
        "confidence": 0.9,
    }
    values.update(overrides)
    return PanelOpinion(**values)


def make_opinion_draft(**overrides) -> dict:
    values = {
        "stage_id": "solving",
        "title": "求解结果缺误差分析",
        "detail": "",
        "severity": FindingSeverity.MINOR,
        "evidence_ids": ["ev-1"],
        "confidence": 0.6,
    }
    values.update(overrides)
    return values


def make_draft(**overrides) -> dict:
    values = {
        "target_opinion_id": "op-0-expert-1-1",
        "stance": Stance.AGREE,
        "evidence_ids": ["ev-model-1"],
        "confidence": 0.8,
        "rationale": "同意该意见",
    }
    values.update(overrides)
    return values


def test_panel_opinion_requires_at_least_one_evidence() -> None:
    with pytest.raises(ValidationError):
        make_opinion(evidence_ids=[])
    base = make_opinion().model_dump()
    base.pop("evidence_ids")
    with pytest.raises(ValidationError):
        PanelOpinion(**base)


def test_panel_opinion_and_draft_reject_unknown_stage_id() -> None:
    with pytest.raises(ValidationError):
        make_opinion(stage_id="unknown_stage")
    with pytest.raises(ValidationError):
        OpinionDraft(**make_opinion_draft(stage_id="unknown_stage"))


def test_opinion_draft_rejects_out_of_range_confidence() -> None:
    for bad in (-0.01, 1.01):
        with pytest.raises(ValidationError):
            OpinionDraft(**make_opinion_draft(confidence=bad))


def test_message_draft_refute_requires_evidence() -> None:
    # REFUTE with an explicit empty evidence list is rejected.
    with pytest.raises(ValidationError):
        MessageDraft(**make_draft(stance=Stance.REFUTE, evidence_ids=[]))
    # REFUTE with the field omitted entirely (defaults to []) is rejected.
    no_evidence = make_draft(stance=Stance.REFUTE)
    no_evidence.pop("evidence_ids")
    with pytest.raises(ValidationError):
        MessageDraft(**no_evidence)
    ok = MessageDraft(**make_draft(stance=Stance.REFUTE, evidence_ids=["ev-1"]))
    assert ok.stance is Stance.REFUTE
    assert ok.evidence_ids == ["ev-1"]


def test_debate_message_refute_requires_evidence() -> None:
    base = {
        "id": "msg-1-2-1",
        "round": 1,
        "expert_id": "expert-2",
        "target_opinion_id": "op-1",
        "stance": Stance.REFUTE,
        "evidence_ids": [],
        "confidence": 0.9,
        "rationale": "反驳理由",
    }
    with pytest.raises(ValidationError):
        DebateMessage(**base)
    ok = DebateMessage(**{**base, "evidence_ids": ["ev-1"]})
    assert ok.stance is Stance.REFUTE
    assert ok.evidence_ids == ["ev-1"]


def test_overlong_title_and_rationale_rejected() -> None:
    with pytest.raises(ValidationError):
        make_opinion(title="x" * 201)
    with pytest.raises(ValidationError):
        MessageDraft(**make_draft(rationale="x" * 1001))


def test_debate_round_round_trips_independently() -> None:
    r = DebateRound(
        round_number=0,
        speaker_order=["expert-1"],
        status="PARTIAL",
        opinions=[make_opinion()],
        rejected=[{"id": "bad"}],
    )
    assert DebateRound.model_validate(r.model_dump(mode="json")) == r


def test_debate_round_and_snapshot_json_round_trip() -> None:
    opinion = make_opinion()
    message = DebateMessage(
        id="msg-1-2-1",
        round=1,
        expert_id="expert-2",
        target_opinion_id=opinion.id,
        stance=Stance.AGREE,
        evidence_ids=["ev-model-1"],
        confidence=0.8,
        rationale="同意",
        revised_title="新的标题",
        revised_detail="新的详情",
        revised_severity=FindingSeverity.MINOR,
    )
    round0 = DebateRound(
        round_number=0,
        speaker_order=["expert-1", "expert-2"],
        status="COMPLETED",
        opinions=[opinion],
    )
    round1 = DebateRound(
        round_number=1,
        speaker_order=["expert-2", "expert-1"],
        status="COMPLETED",
        messages=[message],
        rejected=[{"id": "bad", "reason": "no evidence"}],
    )
    outcome = DebateOutcome(
        rounds_run=1,
        converged=True,
        agreement_ratio=1.0,
        accept_threshold=0.5,
        accepted_opinion_ids=[opinion.id],
        conflict_opinion_ids=[],
        vote_tally={opinion.id: 1.0},
        stop_reason="converged",
    )
    snapshot = DebateSnapshot(
        review_id="review-1",
        status=DebateStatus.COMPLETED,
        panel=[{"expert-1": "modeling", "expert-2": "statistics"}],
        config={"max_rounds": 2},
        rounds=[round0, round1],
        outcome=outcome,
        call_budget={"used": 5, "max": 30},
    )
    dumped = snapshot.model_dump(mode="json")
    restored = DebateSnapshot.model_validate(dumped)
    assert restored == snapshot
    assert restored.rounds[0].opinions[0] == opinion
    assert restored.rounds[1].messages[0] == message
    assert restored.outcome == outcome
    assert restored.created_at == snapshot.created_at
    assert restored.updated_at == snapshot.updated_at


def test_debate_outcome_rejects_invalid_stop_reason() -> None:
    with pytest.raises(ValidationError):
        DebateOutcome(
            rounds_run=1,
            agreement_ratio=0.5,
            accept_threshold=0.5,
            stop_reason="unknown",
        )


def test_panel_opinion_batch_holds_drafts() -> None:
    drafts = [
        OpinionDraft(**make_opinion_draft(stage_id="problem_identification", title="t1")),
        OpinionDraft(**make_opinion_draft(stage_id="solving", title="t2")),
    ]
    batch = PanelOpinionBatch(opinions=drafts)
    assert [d.stage_id for d in batch.opinions] == ["problem_identification", "solving"]
    assert PanelOpinionBatch.model_validate(batch.model_dump(mode="json")) == batch


def test_panel_opinion_batch_rejects_more_than_8_drafts() -> None:
    drafts = [OpinionDraft(**make_opinion_draft(title=f"t{i}")) for i in range(9)]
    with pytest.raises(ValidationError):
        PanelOpinionBatch(opinions=drafts)


def test_debate_message_batch_holds_drafts() -> None:
    messages = [MessageDraft(**make_draft(target_opinion_id=f"op-{i}")) for i in range(3)]
    batch = DebateMessageBatch(messages=messages)
    assert len(batch.messages) == 3
    assert DebateMessageBatch.model_validate(batch.model_dump(mode="json")) == batch
