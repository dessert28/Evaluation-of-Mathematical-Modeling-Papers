"""Validated, serializable result contract for a review job.

This module intentionally contains no model calls or file I/O.  It collects the
typed protocol objects produced by later stages and enforces the evidence graph
and the two independent scoring tracks at the persistence boundary.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from .review_protocol import (
    Claim,
    CriterionScore,
    Evidence,
    Finding,
    Obligation,
    Recommendation,
    ReviewTrack,
    Verdict,
    resolve_claim_verdict,
)
from .review_protocol import ProtocolModel


class ReviewResult(ProtocolModel):
    """A complete or partial, JSON-safe snapshot of one review execution."""

    review_id: str
    evidence: list[Evidence] = Field(default_factory=list)
    obligations: list[Obligation] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    diagnostic_scores: list[CriterionScore] = Field(default_factory=list)
    official_scores: list[CriterionScore] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_and_tracks(self) -> "ReviewResult":
        evidence_ids = {item.id for item in self.evidence}
        obligation_ids = {item.id for item in self.obligations}
        claim_ids = {item.id for item in self.claims}
        finding_ids = {item.id for item in self.findings}

        for values, label, field_name in (
            (evidence_ids, "evidence", "evidence"),
            (obligation_ids, "obligation", "obligations"),
            (claim_ids, "claim", "claims"),
            (finding_ids, "finding", "findings"),
        ):
            if len(values) != len(getattr(self, field_name)):
                raise ValueError(f"duplicate {label} ids are not allowed")

        for claim in self.claims:
            if any(item_id not in obligation_ids for item_id in claim.obligation_ids):
                raise ValueError(f"claim {claim.id} references an unknown obligation")
            if any(item_id not in evidence_ids for item_id in claim.evidence_ids):
                raise ValueError(f"claim {claim.id} references unknown evidence")
            if any(item_id not in evidence_ids for item_id in claim.countercheck_ids):
                raise ValueError(f"claim {claim.id} references unknown countercheck evidence")
            # A strong verdict without evidence is never accepted at snapshot
            # time, even if a caller bypassed Claim's constructor gate.
            if claim.verdict in {Verdict.SUPPORTED, Verdict.REFUTED} and not claim.evidence_ids:
                raise ValueError(f"claim {claim.id} has a strong verdict without evidence")

        for finding in self.findings:
            if any(item_id not in evidence_ids for item_id in finding.evidence_ids):
                raise ValueError(f"finding {finding.id} references unknown evidence")
            if any(item_id not in claim_ids for item_id in finding.claim_ids):
                raise ValueError(f"finding {finding.id} references an unknown claim")
            if finding.verdict in {Verdict.SUPPORTED, Verdict.REFUTED} and not finding.evidence_ids:
                raise ValueError(f"finding {finding.id} has a strong verdict without evidence")

        for recommendation in self.recommendations:
            if recommendation.finding_id not in finding_ids:
                raise ValueError(f"recommendation {recommendation.id} references an unknown finding")
            if any(item_id not in evidence_ids for item_id in recommendation.evidence_ids):
                raise ValueError(f"recommendation {recommendation.id} references unknown evidence")

        if any(score.track is not ReviewTrack.DIAGNOSTIC for score in self.diagnostic_scores):
            raise ValueError("diagnostic_scores may contain diagnostic scores only")
        if any(score.track is not ReviewTrack.OFFICIAL for score in self.official_scores):
            raise ValueError("official_scores may contain official scores only")
        for scores, label in ((self.diagnostic_scores, "diagnostic"), (self.official_scores, "official")):
            criterion_ids = {score.id for score in scores}
            if len(criterion_ids) != len(scores):
                raise ValueError(f"duplicate {label} score ids are not allowed")
            if any(item_id not in evidence_ids for score in scores for item_id in score.evidence_ids):
                raise ValueError(f"{label} score references unknown evidence")
        return self

    def resolve_claims(self) -> "ReviewResult":
        """Return a copy with claim verdicts deterministically resolved."""
        resolved = [
            claim.model_copy(
                update={
                    "verdict": resolve_claim_verdict(claim, self.obligations, self.evidence),
                }
            )
            for claim in self.claims
        ]
        return self.model_copy(update={"claims": resolved})

    def to_snapshot(self) -> dict[str, Any]:
        """Serialize with ISO datetimes and enum values for SQLite JSON."""
        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, payload: dict[str, Any]) -> "ReviewResult":
        return cls.model_validate(payload)


__all__ = ["ReviewResult"]
