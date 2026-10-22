"""Deterministic evidence and scoring rules for review results."""

from __future__ import annotations

from typing import Mapping, Sequence
from backend.app.domain.review_protocol import EvidenceLevel, Verdict


STAGE_WEIGHTS: Mapping[str, float] = {
    "problem_identification": 0.15,
    "problem_formulation": 0.15,
    "assumptions": 0.15,
    "model_construction": 0.20,
    "solving": 0.10,
    "code_implementation": 0.15,
    "results_analysis": 0.10,
}


def normalize_score(raw_score: float) -> float:
    """Map a raw 0-10 score to the protocol's 0-4 scale."""
    if not 0 <= raw_score <= 10:
        raise ValueError("raw_score must be between 0 and 10")
    return round(raw_score / 10 * 4, 2)


def diagnostic_score(scores: Mapping[str, float]) -> float:
    """Return the weighted seven-stage score on the raw 0-10 scale."""
    unknown = set(scores) - set(STAGE_WEIGHTS)
    missing = set(STAGE_WEIGHTS) - set(scores)
    if unknown:
        raise ValueError(f"unknown diagnostic stages: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing diagnostic stages: {sorted(missing)}")
    for stage, score in scores.items():
        if not 0 <= score <= 10:
            raise ValueError(f"score for {stage} must be between 0 and 10")
    return round(sum(scores[stage] * weight for stage, weight in STAGE_WEIGHTS.items()), 2) * 10


def _has_located_usable_evidence(evidence: Sequence[Mapping[str, object]]) -> bool:
    for item in evidence:
        level = item.get("level", EvidenceLevel.NOT_CHECKED)
        try:
            level = EvidenceLevel(level)
        except (TypeError, ValueError):
            continue
        rank = list(EvidenceLevel).index(level)
        if rank >= list(EvidenceLevel).index(EvidenceLevel.DERIVED) and item.get("locator"):
            return True
    return False


def resolve_verdict(
    *,
    obligations_satisfied: bool,
    evidence: Sequence[Mapping[str, object]],
    conditional: bool = False,
    refuted: bool = False,
) -> Verdict:
    """Resolve a claim using deterministic precedence and evidence gates."""
    if refuted and _has_located_usable_evidence(evidence):
        return Verdict.REFUTED
    if refuted:
        return Verdict.INCONCLUSIVE
    if not obligations_satisfied or not _has_located_usable_evidence(evidence):
        return Verdict.INCONCLUSIVE
    if conditional:
        return Verdict.CONDITIONAL
    return Verdict.SUPPORTED
