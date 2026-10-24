"""Deterministic domain models and pure aggregation for multi-agent debate.

The module deliberately contains no I/O and no model calls.  It is the frozen
contract shared by the debate engine, the persistence layer, and the API:

- model-output drafts (``OpinionDraft`` / ``MessageDraft``) and persisted
  contracts (``PanelOpinion`` / ``DebateMessage``) carrying the protocol
  evidence rules (REFUTE must cite evidence, stage ids must be diagnostic);
- the snapshot + outcome contracts used at the persistence boundary;
- the purely deterministic aggregation functions (weighted voting, conflict
  detection, agreement, convergence, and final panel evaluation).

Strong conclusions still come only from
``review_protocol.resolve_claim_verdict``; this module never produces verdicts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Literal, Mapping

from pydantic import Field, field_validator, model_validator

from .review_protocol import (
    DIAGNOSTIC_STAGE_WEIGHTS,
    FindingSeverity,
    ProtocolModel,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Stance(str, Enum):
    AGREE = "AGREE"
    QUALIFY = "QUALIFY"
    DISAGREE = "DISAGREE"
    REFUTE = "REFUTE"
    WITHDRAW = "WITHDRAW"


class DebateStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


class DebateError(ValueError):
    """Domain error carrying a stable protocol error code."""

    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


_STAGE_NAMES = tuple(DIAGNOSTIC_STAGE_WEIGHTS)


def _check_stage_id(value: str) -> str:
    if value not in DIAGNOSTIC_STAGE_WEIGHTS:
        raise ValueError(
            "stage_id must be one of the seven diagnostic stages: "
            + ", ".join(_STAGE_NAMES)
        )
    return value


class OpinionDraft(ProtocolModel):
    """Structured opinion a panel expert returns (model output draft)."""

    stage_id: str
    title: str = Field(..., min_length=1, max_length=200)
    detail: str = Field(default="", max_length=2000)
    severity: FindingSeverity
    evidence_ids: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)

    @field_validator("stage_id")
    @classmethod
    def _validate_stage_id(cls, value: str) -> str:
        return _check_stage_id(value)


class PanelOpinion(ProtocolModel):
    """Persisted opinion contract; ``id`` is rewritten by the engine."""

    id: str = Field(..., max_length=128)
    expert_id: str = Field(..., max_length=64)
    stage_id: str
    lens: str = Field(..., max_length=80)
    title: str = Field(..., min_length=1, max_length=200)
    detail: str = Field(default="", max_length=2000)
    severity: FindingSeverity
    evidence_ids: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)

    @field_validator("stage_id")
    @classmethod
    def _validate_stage_id(cls, value: str) -> str:
        return _check_stage_id(value)


class MessageDraft(ProtocolModel):
    """Structured debate message a panel expert returns (model output)."""

    target_opinion_id: str
    stance: Stance
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    rationale: str = Field(..., min_length=1, max_length=1000)
    revised_title: str | None = Field(default=None, max_length=200)
    revised_detail: str | None = Field(default=None, max_length=2000)
    revised_severity: FindingSeverity | None = None

    @model_validator(mode="after")
    def refute_requires_evidence(self) -> "MessageDraft":
        if self.stance is Stance.REFUTE and not self.evidence_ids:
            raise ValueError("REFUTE requires at least one evidence_id")
        return self


class DebateMessage(ProtocolModel):
    """Persisted debate message contract; ``id`` is rewritten by the engine."""

    id: str
    round: int = Field(..., ge=1, le=5)
    expert_id: str
    target_opinion_id: str
    stance: Stance
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float
    rationale: str
    revised_title: str | None = Field(default=None, max_length=200)
    revised_detail: str | None = Field(default=None, max_length=2000)
    revised_severity: FindingSeverity | None = None

    @model_validator(mode="after")
    def refute_requires_evidence(self) -> "DebateMessage":
        if self.stance is Stance.REFUTE and not self.evidence_ids:
            raise ValueError("REFUTE requires at least one evidence_id")
        return self


class DebateRound(ProtocolModel):
    round_number: int = Field(..., ge=0, le=5)
    speaker_order: list[str] = Field(default_factory=list)
    status: Literal["COMPLETED", "PARTIAL", "FAILED"] = "COMPLETED"
    opinions: list[PanelOpinion] = Field(default_factory=list)
    messages: list[DebateMessage] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)


class DebateOutcome(ProtocolModel):
    rounds_run: int = Field(..., ge=0, le=5)
    converged: bool = False
    agreement_ratio: float = Field(..., ge=0, le=1)
    accept_threshold: float = Field(..., gt=0, le=1)
    accepted_opinion_ids: list[str] = Field(default_factory=list)
    conflict_opinion_ids: list[str] = Field(default_factory=list)
    vote_tally: dict[str, float] = Field(default_factory=dict)
    stop_reason: Literal["converged", "max_rounds", "budget_exhausted", "failed"] = (
        "max_rounds"
    )


class DebateSnapshot(ProtocolModel):
    review_id: str
    status: DebateStatus
    panel: list[dict] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    rounds: list[DebateRound] = Field(default_factory=list)
    outcome: DebateOutcome | None = None
    call_budget: dict = Field(default_factory=dict)
    stale: bool = False
    last_error: dict | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class PanelOpinionBatch(ProtocolModel):
    """Structured-output wrapper for one expert's opinions (max 8)."""

    opinions: list[OpinionDraft] = Field(default_factory=list, max_length=8)


class DebateMessageBatch(ProtocolModel):
    """Structured-output wrapper for a round of messages (max 16)."""

    messages: list[MessageDraft] = Field(default_factory=list, max_length=16)


STANCE_WEIGHTS: Mapping[Stance, float] = {
    Stance.AGREE: 1.0,
    Stance.QUALIFY: 0.5,
    Stance.DISAGREE: -1.0,
    Stance.REFUTE: -2.0,
    Stance.WITHDRAW: 0.0,
}

_POSITIVE_STANCES = {Stance.AGREE, Stance.QUALIFY}
_NEGATIVE_STANCES = {Stance.DISAGREE, Stance.REFUTE}


def aggregate_votes(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
    *,
    expert_weights: Mapping[str, float] | None = None,
    fatal_bonus: float = 3.0,
) -> dict[str, float]:
    """Return per-opinion weighted score: ``Σ stance_weight × expert_weight``.

    Messages targeting an unknown opinion id are skipped.  Fatal findings get a
    deterministic bonus so a single opposing vote cannot bury a fatal error.
    Every returned score is rounded to 6 decimal places.
    """
    weights = expert_weights or {}
    materialized_opinions = list(opinions)
    tallies: dict[str, float] = {}
    for opinion in materialized_opinions:
        score = 0.0
        for message in messages:
            if message.target_opinion_id != opinion.id:
                continue
            score += STANCE_WEIGHTS[message.stance] * weights.get(
                message.expert_id, 1.0
            )
        if opinion.severity is FindingSeverity.FATAL:
            score += fatal_bonus
        tallies[opinion.id] = round(score, 6)
    return tallies


def _withdrawn_opinion_ids(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
) -> set[str]:
    """Return opinion ids that their own author withdrew via a WITHDRAW message."""
    opinion_by_id = {opinion.id: opinion for opinion in opinions}
    withdrawn: set[str] = set()
    for message in messages:
        if message.stance is not Stance.WITHDRAW:
            continue
        target = opinion_by_id.get(message.target_opinion_id)
        if target is not None and message.expert_id == target.expert_id:
            withdrawn.add(message.target_opinion_id)
    return withdrawn


def detect_conflicts(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
    tally: Mapping[str, float],
    *,
    accept_threshold: float = 0.5,
) -> list[str]:
    """Return opinion ids with both positive and negative stances and a low score.

    An opinion is a conflict only when it received at least one positive
    (AGREE/QUALIFY) and at least one negative (DISAGREE/REFUTE) voice while its
    absolute weighted score stays below ``accept_threshold``.  Order is the
    opinion order and ids are de-duplicated by construction.
    """
    opinion_ids = {opinion.id for opinion in opinions}
    has_positive = {opinion_id: False for opinion_id in opinion_ids}
    has_negative = {opinion_id: False for opinion_id in opinion_ids}
    for message in messages:
        if message.target_opinion_id not in opinion_ids:
            continue
        if message.stance in _POSITIVE_STANCES:
            has_positive[message.target_opinion_id] = True
        elif message.stance in _NEGATIVE_STANCES:
            has_negative[message.target_opinion_id] = True
    return [
        opinion.id
        for opinion in opinions
        if has_positive[opinion.id]
        and has_negative[opinion.id]
        and abs(tally.get(opinion.id, 0.0)) < accept_threshold
    ]


def compute_agreement(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
) -> float:
    """Return the share of opinions not opposed by a DISAGREE/REFUTE message."""
    materialized = list(opinions)
    if not materialized:
        return 0.0
    opinion_ids = {opinion.id for opinion in materialized}
    opposed: set[str] = set()
    for message in messages:
        if (
            message.target_opinion_id in opinion_ids
            and message.stance in _NEGATIVE_STANCES
        ):
            opposed.add(message.target_opinion_id)
    return round(1.0 - len(opposed) / len(materialized), 6)


def is_converged(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
    *,
    rounds_run: int,
    agreement_threshold: float = 0.8,
    min_rounds: int = 1,
) -> bool:
    """Converged only after ``min_rounds`` and at/above the agreement threshold."""
    if rounds_run < min_rounds:
        return False
    return compute_agreement(opinions, messages) >= agreement_threshold


def evaluate_panel(
    opinions: Iterable[PanelOpinion],
    messages: Iterable[DebateMessage],
    *,
    rounds_run: int,
    accept_threshold: float = 0.5,
    fatal_bonus: float = 3.0,
    expert_weights: Mapping[str, float] | None = None,
    stop_reason: Literal[
        "converged", "max_rounds", "budget_exhausted", "failed"
    ] = "max_rounds",
) -> DebateOutcome:
    """Deterministically aggregate a panel into a persisted ``DebateOutcome``.

    ``converged`` is derived solely from ``stop_reason == "converged"``: the
    engine decides why the debate stopped, this function only reports it.
    """
    materialized_opinions = list(opinions)
    materialized_messages = list(messages)
    tally = aggregate_votes(
        materialized_opinions,
        materialized_messages,
        expert_weights=expert_weights,
        fatal_bonus=fatal_bonus,
    )
    withdrawn = _withdrawn_opinion_ids(materialized_opinions, materialized_messages)
    accepted = [
        opinion.id
        for opinion in materialized_opinions
        if tally.get(opinion.id, 0.0) >= accept_threshold
        and opinion.id not in withdrawn
    ]
    conflicts = detect_conflicts(
        materialized_opinions,
        materialized_messages,
        tally,
        accept_threshold=accept_threshold,
    )
    agreement = compute_agreement(materialized_opinions, materialized_messages)
    return DebateOutcome(
        rounds_run=rounds_run,
        converged=stop_reason == "converged",
        agreement_ratio=agreement,
        accept_threshold=accept_threshold,
        accepted_opinion_ids=accepted,
        conflict_opinion_ids=conflicts,
        vote_tally=tally,
        stop_reason=stop_reason,
    )


__all__ = [
    "DebateError",
    "DebateMessage",
    "DebateMessageBatch",
    "DebateOutcome",
    "DebateRound",
    "DebateSnapshot",
    "DebateStatus",
    "MessageDraft",
    "OpinionDraft",
    "PanelOpinion",
    "PanelOpinionBatch",
    "STANCE_WEIGHTS",
    "Stance",
    "aggregate_votes",
    "compute_agreement",
    "detect_conflicts",
    "evaluate_panel",
    "is_converged",
]
