"""Unit tests for the deterministic debate aggregation functions."""

from __future__ import annotations

import itertools

import pytest

from backend.app.domain.debate import (
    DebateMessage,
    PanelOpinion,
    Stance,
    aggregate_votes,
    compute_agreement,
    detect_conflicts,
    evaluate_panel,
    is_converged,
)
from backend.app.domain.review_protocol import FindingSeverity


_counter = itertools.count()


def make_opinion(
    opinion_id: str,
    expert_id: str = "expert-1",
    severity: FindingSeverity = FindingSeverity.MAJOR,
    **overrides,
) -> PanelOpinion:
    values = {
        "id": opinion_id,
        "expert_id": expert_id,
        "stage_id": "model_construction",
        "lens": "algorithm",
        "title": f"title-{opinion_id}",
        "detail": "detail",
        "severity": severity,
        "evidence_ids": [f"ev-{opinion_id}"],
        "confidence": 0.8,
    }
    values.update(overrides)
    return PanelOpinion(**values)


def make_message(
    expert_id: str,
    target_opinion_id: str,
    stance: Stance,
    evidence_ids=None,
    **overrides,
) -> DebateMessage:
    ids = list(evidence_ids) if evidence_ids else []
    if stance is Stance.REFUTE and not ids:
        ids = ["ev-refute"]
    values = {
        "id": f"msg-{next(_counter)}",
        "round": 1,
        "expert_id": expert_id,
        "target_opinion_id": target_opinion_id,
        "stance": stance,
        "evidence_ids": ids,
        "confidence": 0.8,
        "rationale": "ok",
    }
    values.update(overrides)
    return DebateMessage(**values)


def test_aggregate_votes_stance_weights() -> None:
    opinions = [make_opinion("op-1")]
    for stance, expected in (
        (Stance.AGREE, 1.0),
        (Stance.QUALIFY, 0.5),
        (Stance.DISAGREE, -1.0),
        (Stance.REFUTE, -2.0),
        (Stance.WITHDRAW, 0.0),
    ):
        tally = aggregate_votes(opinions, [make_message("expert-1", "op-1", stance)])
        assert tally["op-1"] == pytest.approx(expected)


def test_aggregate_votes_applies_expert_weights() -> None:
    opinions = [make_opinion("op-1")]
    messages = [
        make_message("expert-1", "op-1", Stance.AGREE),
        make_message("expert-2", "op-1", Stance.AGREE),
    ]
    tally = aggregate_votes(opinions, messages, expert_weights={"expert-2": 2.5})
    assert tally["op-1"] == pytest.approx(1.0 + 2.5)
    tally_default = aggregate_votes(
        opinions, [make_message("expert-9", "op-1", Stance.AGREE)]
    )
    assert tally_default["op-1"] == pytest.approx(1.0)


def test_aggregate_votes_adds_fatal_bonus() -> None:
    normal = make_opinion("op-normal")
    fatal = make_opinion("op-fatal", severity=FindingSeverity.FATAL)
    tally = aggregate_votes(
        [normal, fatal],
        [make_message("expert-2", "op-fatal", Stance.DISAGREE)],
    )
    assert tally["op-normal"] == 0.0
    assert tally["op-fatal"] == pytest.approx(-1.0 + 3.0)


def test_aggregate_votes_ignores_messages_with_unknown_targets() -> None:
    opinions = [make_opinion("op-1")]
    tally = aggregate_votes(
        opinions, [make_message("expert-1", "op-ghost", Stance.REFUTE)]
    )
    assert tally["op-1"] == 0.0


def test_detect_conflicts_flags_mixed_stances_with_low_agreement() -> None:
    opinions = [make_opinion("op-1")]
    messages = [
        make_message("expert-1", "op-1", Stance.AGREE),
        make_message("expert-2", "op-1", Stance.DISAGREE),
    ]
    tally = aggregate_votes(opinions, messages)
    assert tally["op-1"] == pytest.approx(0.0)
    assert detect_conflicts(opinions, messages, tally) == ["op-1"]


def test_detect_conflicts_not_flagged_with_strong_preference() -> None:
    opinions = [make_opinion("op-1")]
    messages = [
        make_message("expert-1", "op-1", Stance.AGREE),
        make_message("expert-2", "op-1", Stance.AGREE),
    ]
    tally = aggregate_votes(opinions, messages)
    assert tally["op-1"] == pytest.approx(2.0)
    assert detect_conflicts(opinions, messages, tally) == []


def test_detect_conflicts_strong_refute_is_not_conflict() -> None:
    opinions = [make_opinion("op-1")]
    messages = [
        make_message("expert-1", "op-1", Stance.QUALIFY),
        make_message("expert-2", "op-1", Stance.REFUTE),
    ]
    tally = aggregate_votes(opinions, messages)
    assert tally["op-1"] == pytest.approx(-1.5)
    assert detect_conflicts(opinions, messages, tally) == []


def test_compute_agreement_partial_opposition() -> None:
    opinions = [make_opinion("op-1"), make_opinion("op-2")]
    messages = [make_message("expert-2", "op-1", Stance.DISAGREE)]
    assert compute_agreement(opinions, messages) == pytest.approx(0.5)


def test_compute_agreement_full_agreement_is_one() -> None:
    opinions = [make_opinion("op-1")]
    messages = [make_message("expert-1", "op-1", Stance.AGREE)]
    assert compute_agreement(opinions, messages) == pytest.approx(1.0)


def test_compute_agreement_all_opposed_is_zero_and_empty_is_zero() -> None:
    opinions = [make_opinion("op-1"), make_opinion("op-2")]
    messages = [
        make_message("expert-2", "op-1", Stance.DISAGREE, evidence_ids=["ev-a"]),
        make_message("expert-3", "op-2", Stance.REFUTE, evidence_ids=["ev-b"]),
    ]
    assert compute_agreement(opinions, messages) == 0.0
    assert compute_agreement([], []) == 0.0


def test_is_converged_requires_min_rounds() -> None:
    opinions = [make_opinion("op-1")]
    messages = [make_message("expert-1", "op-1", Stance.AGREE)]
    assert is_converged(opinions, messages, rounds_run=0, min_rounds=1) is False
    assert is_converged(opinions, messages, rounds_run=1, min_rounds=1) is True
    assert is_converged(opinions, messages, rounds_run=1, min_rounds=2) is False


def test_is_converged_only_at_threshold() -> None:
    opinions = [make_opinion("op-1"), make_opinion("op-2")]
    messages = [make_message("expert-2", "op-1", Stance.DISAGREE)]
    assert is_converged(opinions, messages, rounds_run=2) is False
    assert (
        is_converged(opinions, messages, rounds_run=2, agreement_threshold=0.5)
        is True
    )


def test_evaluate_panel_all_agree_converges() -> None:
    opinions = [make_opinion("op-1"), make_opinion("op-2")]
    messages = [
        make_message("expert-1", "op-1", Stance.AGREE),
        make_message("expert-2", "op-2", Stance.AGREE),
    ]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="converged")
    assert outcome.converged is True
    assert outcome.stop_reason == "converged"
    assert outcome.accepted_opinion_ids == ["op-1", "op-2"]
    assert outcome.agreement_ratio == pytest.approx(1.0)


def test_evaluate_panel_opposition_does_not_converge() -> None:
    opinions = [make_opinion("op-1"), make_opinion("op-2")]
    messages = [
        make_message("expert-2", "op-1", Stance.DISAGREE),
        make_message("expert-1", "op-2", Stance.AGREE),
    ]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="max_rounds")
    assert outcome.converged is False
    assert outcome.stop_reason == "max_rounds"
    assert outcome.agreement_ratio == pytest.approx(0.5)
    assert outcome.accepted_opinion_ids == ["op-2"]
    assert outcome.conflict_opinion_ids == []


def test_evaluate_panel_author_withdraw_not_accepted_even_when_score_qualifies() -> None:
    opinions = [make_opinion("op-1", expert_id="expert-1")]
    messages = [
        make_message("expert-2", "op-1", Stance.AGREE),
        make_message("expert-1", "op-1", Stance.WITHDRAW),
    ]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="max_rounds")
    assert outcome.vote_tally["op-1"] == pytest.approx(1.0)
    assert outcome.accepted_opinion_ids == []


def test_evaluate_panel_withdraw_by_non_author_is_ignored() -> None:
    opinions = [make_opinion("op-1", expert_id="expert-1")]
    messages = [
        make_message("expert-2", "op-1", Stance.WITHDRAW),
        make_message("expert-2", "op-1", Stance.AGREE),
    ]
    outcome = evaluate_panel(opinions, messages, rounds_run=1, stop_reason="max_rounds")
    assert outcome.vote_tally["op-1"] == pytest.approx(1.0)
    assert outcome.accepted_opinion_ids == ["op-1"]


def test_evaluate_panel_fatal_opinion_survives_a_negative_vote() -> None:
    opinions = [make_opinion("op-fatal", severity=FindingSeverity.FATAL)]
    messages = [make_message("expert-2", "op-fatal", Stance.DISAGREE)]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="max_rounds")
    assert outcome.vote_tally["op-fatal"] == pytest.approx(-1.0 + 3.0)
    assert outcome.accepted_opinion_ids == ["op-fatal"]


def test_evaluate_panel_flags_low_agreement_conflict() -> None:
    opinions = [make_opinion("op-1")]
    messages = [
        make_message("expert-1", "op-1", Stance.AGREE),
        make_message("expert-2", "op-1", Stance.DISAGREE),
    ]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="max_rounds")
    assert outcome.vote_tally["op-1"] == pytest.approx(0.0)
    assert outcome.conflict_opinion_ids == ["op-1"]
    assert outcome.accepted_opinion_ids == []


def test_evaluate_panel_converged_only_when_stop_reason_converged() -> None:
    opinions = [make_opinion("op-1")]
    messages = [make_message("expert-1", "op-1", Stance.AGREE)]
    outcome = evaluate_panel(opinions, messages, rounds_run=2, stop_reason="max_rounds")
    assert outcome.agreement_ratio == pytest.approx(1.0)
    assert outcome.converged is False
