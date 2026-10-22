"""Typed review protocol primitives and deterministic score helpers.

The module deliberately contains no I/O or model calls.  It is the contract
shared by pipeline stages, report builders, and API adapters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, ClassVar, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Verdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONDITIONAL = "CONDITIONAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    REFUTED = "REFUTED"


class EvidenceLevel(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    DERIVED = "DERIVED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    EXTERNALLY_VALIDATED = "EXTERNALLY_VALIDATED"


class FindingSeverity(str, Enum):
    FATAL = "fatal"
    MAJOR = "major"
    MINOR = "minor"


class ReviewTrack(str, Enum):
    DIAGNOSTIC = "diagnostic"
    OFFICIAL = "official"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(ProtocolModel):
    id: str
    kind: str
    asset_id: str | None = None
    block_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    quote: str | None = None
    quote_hash: str | None = None
    source_locator: str | None = None
    input_hashes: list[str] = Field(default_factory=list)
    output_hashes: list[str] = Field(default_factory=list)
    command: str | None = None
    environment: dict[str, str] = Field(default_factory=dict)
    exit_code: int | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.NOT_CHECKED
    limitations: list[str] = Field(default_factory=list)

    @property
    def location(self) -> dict[str, Any]:
        """Return only available, stable locator fields for report citations."""
        names = ("asset_id", "block_id", "page", "paragraph", "line_start", "line_end")
        return {name: getattr(self, name) for name in names if getattr(self, name) is not None}


class Obligation(ProtocolModel):
    id: str
    text: str
    required: bool = True
    fulfilled: bool | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class Claim(ProtocolModel):
    id: str
    exact_text: str
    type: str = "general"
    scope: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    obligation_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    countercheck_ids: list[str] = Field(default_factory=list)
    verdict: Verdict = Verdict.INCONCLUSIVE
    limitations: list[str] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    stale: bool = False
    reviewed_at: datetime = Field(default_factory=_utc_now)
    reviewer_model: str | None = None
    evidence_verified: bool = False
    counterevidence_verified: bool = False
    # Preserve the requested state for deterministic resolution, while the
    # persisted verdict remains inconclusive until resolve_claim_verdict()
    # validates the full object graph.
    requested_verdict: Verdict | None = None

    @model_validator(mode="after")
    def enforce_evidence_gate(self) -> "Claim":
        requested = self.requested_verdict or self.verdict
        object.__setattr__(self, "requested_verdict", requested)
        if requested in {Verdict.SUPPORTED, Verdict.REFUTED}:
            object.__setattr__(self, "verdict", Verdict.INCONCLUSIVE)
            return self
        object.__setattr__(
            self,
            "verdict",
            resolve_verdict(requested, evidence_count=len(self.evidence_ids)),
        )
        return self


class Verification(ProtocolModel):
    id: str
    claim_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.NOT_CHECKED
    passed: bool | None = None
    method: str | None = None
    notes: list[str] = Field(default_factory=list)


class Finding(ProtocolModel):
    id: str
    title: str
    detail: str | None = None
    severity: FindingSeverity
    verdict: Verdict = Verdict.INCONCLUSIVE
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    stale: bool = False
    evidence_verified: bool = False
    requested_verdict: Verdict | None = None

    @model_validator(mode="after")
    def require_locator_for_refutation(self) -> "Finding":
        requested = self.requested_verdict or self.verdict
        object.__setattr__(self, "requested_verdict", requested)
        if requested in {Verdict.SUPPORTED, Verdict.REFUTED}:
            object.__setattr__(self, "verdict", Verdict.INCONCLUSIVE)
        return self


class Recommendation(ProtocolModel):
    id: str
    finding_id: str
    action: str
    acceptance: str
    priority: FindingSeverity = FindingSeverity.MINOR
    evidence_ids: list[str] = Field(default_factory=list)
    owner: str | None = None


class CriterionScore(ProtocolModel):
    id: str
    criterion: str
    track: ReviewTrack
    raw_score_0_10: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    normalized_score_0_4: float | None = None
    score_rationale: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    verdict: Verdict = Verdict.INCONCLUSIVE
    confidence: float | None = Field(default=None, ge=0, le=1)
    rubric_profile_id: str | None = None
    rubric_published: bool = False
    human_confirmed: bool = False
    rubric_decision_id: str | None = None
    rubric_source_hash: str | None = None

    @model_validator(mode="after")
    def normalize_diagnostic_score(self) -> "CriterionScore":
        if self.track is ReviewTrack.DIAGNOSTIC:
            if self.raw_score_0_10 > 10:
                raise ValueError("diagnostic raw_score_0_10 must be between 0 and 10")
            object.__setattr__(
                self,
                "normalized_score_0_4",
                normalize_score(self.raw_score_0_10),
            )
        else:
            if (
                not self.rubric_profile_id
                or not self.rubric_published
                or not self.human_confirmed
                or not self.rubric_decision_id
                or not self.rubric_source_hash
            ):
                raise ValueError(
                    "official scores require a published rubric, source hash, decision record, and human confirmation"
                )
            object.__setattr__(self, "normalized_score_0_4", None)
        return self


class RubricProfile(ProtocolModel):
    """Published official rubric identity and its criterion weights."""

    id: str
    version: str
    source_hash: str
    published: bool = False
    criteria: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile(self) -> "RubricProfile":
        if not self.id.strip() or not self.version.strip() or not self.source_hash.strip():
            raise ValueError("rubric profile id, version, and source_hash are required")
        if not self.criteria:
            raise ValueError("rubric profile requires at least one criterion")
        if any(not criterion.strip() for criterion in self.criteria):
            raise ValueError("rubric criterion names must be non-empty")
        if any(weight <= 0 or weight > 1 for weight in self.criteria.values()):
            raise ValueError("rubric criterion weights must be between 0 and 1")
        if not math.isclose(sum(self.criteria.values()), 1.0, rel_tol=0, abs_tol=1e-9):
            raise ValueError("rubric criterion weights must sum to 1")
        return self


class DecisionLedger(ProtocolModel):
    id: str
    subject_id: str
    decision: str
    rationale: str
    decided_by: str = "human"
    evidence_ids: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    decided_at: datetime = Field(default_factory=_utc_now)


class ReviewEvent(ProtocolModel):
    id: str
    review_id: str
    event_type: str
    reason: str
    from_state: str | None = None
    to_state: str | None = None
    input_hashes: list[str] = Field(default_factory=list)
    evidence_fingerprint: str | None = None
    actor: str = "deterministic-coordinator"
    created_at: datetime = Field(default_factory=_utc_now)


DIAGNOSTIC_STAGE_WEIGHTS: ClassVar[Mapping[str, float]] = {
    "problem_identification": 0.15,
    "problem_formulation": 0.15,
    "assumptions": 0.15,
    "model_construction": 0.20,
    "solving": 0.10,
    "code_implementation": 0.15,
    "results_analysis": 0.10,
}


def normalize_score(raw_score_0_10: float) -> float:
    """Convert a 0–10 stage score to the protocol's 0–4 scale."""
    if not 0 <= raw_score_0_10 <= 10:
        raise ValueError("raw score must be between 0 and 10")
    return round(raw_score_0_10 / 10 * 4, 2)


def resolve_verdict(
    verdict: Verdict,
    *,
    evidence_count: int,
    counterevidence: bool = False,
) -> Verdict:
    """Apply the evidence gate while preserving an explicit refutation."""
    if counterevidence and evidence_count > 0:
        return Verdict.REFUTED
    if counterevidence and evidence_count <= 0:
        return Verdict.INCONCLUSIVE
    if verdict is Verdict.REFUTED:
        return Verdict.REFUTED if evidence_count > 0 else Verdict.INCONCLUSIVE
    if evidence_count <= 0:
        return Verdict.INCONCLUSIVE
    return verdict


def diagnostic_total(scores: Iterable[CriterionScore]) -> float:
    """Return the weighted diagnostic score on a 0–1 scale.

    Mixing official criteria into this calculation is rejected so the two
    reporting tracks cannot silently contaminate one another.
    """
    materialized = list(scores)
    if not materialized:
        return 0.0
    if any(score.track is not ReviewTrack.DIAGNOSTIC for score in materialized):
        raise ValueError("diagnostic_total accepts diagnostic scores only")
    criteria = [score.criterion for score in materialized]
    if len(criteria) != len(set(criteria)):
        raise ValueError("diagnostic_total rejects duplicate diagnostic criteria")
    by_criterion = {score.criterion: score for score in materialized}
    expected = set(DIAGNOSTIC_STAGE_WEIGHTS)
    if set(by_criterion) != expected:
        raise ValueError("diagnostic_total requires exactly the seven diagnostic stages")
    for criterion, expected_weight in DIAGNOSTIC_STAGE_WEIGHTS.items():
        if by_criterion[criterion].weight != expected_weight:
            raise ValueError(
                f"weight for {criterion} must equal protocol weight {expected_weight}"
            )
    return round(
        sum(
            (by_criterion[criterion].raw_score_0_10 / 10)
            * weight
            * 100
            for criterion, weight in DIAGNOSTIC_STAGE_WEIGHTS.items()
        ),
        6,
    )


def _has_stable_locator(evidence: Evidence) -> bool:
    return bool(
        evidence.source_locator
        or evidence.block_id
        or evidence.page is not None
        or evidence.paragraph is not None
        or evidence.line_start is not None
        or evidence.quote_hash
    )


def resolve_claim_verdict(
    claim: Claim,
    obligations: Iterable[Obligation],
    evidence: Iterable[Evidence],
) -> Verdict:
    """Resolve a claim against actual obligations and located evidence.

    Claim and evidence IDs alone are not proof: the caller must provide the
    referenced objects so required obligations and stable locators can be
    checked deterministically.
    """
    obligation_list = list(obligations)
    evidence_list = list(evidence)
    obligation_by_id = {item.id: item for item in obligation_list}
    if any(item_id not in obligation_by_id for item_id in claim.obligation_ids):
        return Verdict.INCONCLUSIVE
    evidence_by_id = {item.id: item for item in evidence_list}
    required = [obligation_by_id[item_id] for item_id in claim.obligation_ids if obligation_by_id[item_id].required]
    if any(item.fulfilled is not True for item in required):
        return Verdict.INCONCLUSIVE
    claim_evidence_ids = set(claim.evidence_ids)
    for obligation in required:
        if not obligation.evidence_ids:
            return Verdict.INCONCLUSIVE
        if not set(obligation.evidence_ids).issubset(claim_evidence_ids):
            return Verdict.INCONCLUSIVE
        if any(evidence_id not in evidence_by_id for evidence_id in obligation.evidence_ids):
            return Verdict.INCONCLUSIVE
    linked = [item for item in evidence_list if item.id in claim_evidence_ids]
    located = [
        item
        for item in linked
        if _has_stable_locator(item)
        and item.evidence_level
        in {
            EvidenceLevel.VERIFIED,
            EvidenceLevel.INDEPENDENTLY_VERIFIED,
            EvidenceLevel.EXTERNALLY_VALIDATED,
        }
    ]
    requested_verdict = claim.requested_verdict or claim.verdict
    if requested_verdict is Verdict.REFUTED:
        counter_ids = set(claim.countercheck_ids)
        counter = [item for item in located if item.id in counter_ids]
        return Verdict.REFUTED if counter else Verdict.INCONCLUSIVE
    if not located:
        return Verdict.INCONCLUSIVE
    if requested_verdict is Verdict.CONDITIONAL:
        return Verdict.CONDITIONAL
    return Verdict.SUPPORTED


def official_total(
    scores: Iterable[CriterionScore],
    *,
    rubric_profile: RubricProfile | None = None,
    decision_ledger: DecisionLedger | None = None,
) -> float:
    """Return an official score bound to a published rubric and human decision."""
    materialized = list(scores)
    if not materialized:
        return 0.0
    if any(score.track is not ReviewTrack.OFFICIAL for score in materialized):
        raise ValueError("official_total accepts official scores only")
    if rubric_profile is None or decision_ledger is None:
        raise ValueError("official_total requires a rubric profile and decision ledger")
    if not rubric_profile.published:
        raise ValueError("official_total requires a published rubric profile")
    if decision_ledger.decided_by != "human" or decision_ledger.subject_id != rubric_profile.id:
        raise ValueError("rubric decision must be human and bound to the rubric profile")
    criteria = [score.criterion for score in materialized]
    if len(criteria) != len(set(criteria)):
        raise ValueError("official_total rejects duplicate criteria")
    if set(criteria) != set(rubric_profile.criteria):
        raise ValueError("official scores must cover exactly the rubric criteria")
    bindings = {
        (
            score.rubric_profile_id,
            score.rubric_source_hash,
            score.rubric_decision_id,
        )
        for score in materialized
    }
    if len(bindings) != 1:
        raise ValueError("official scores must share one published rubric binding; score bindings are not bound consistently")
    for score in materialized:
        if (
            score.rubric_profile_id != rubric_profile.id
            or score.rubric_source_hash != rubric_profile.source_hash
            or score.rubric_decision_id != decision_ledger.id
            or not score.rubric_published
            or not score.human_confirmed
            or not math.isclose(
                score.weight,
                rubric_profile.criteria[score.criterion],
                rel_tol=0,
                abs_tol=1e-9,
            )
        ):
            raise ValueError("official score is not bound to the published rubric context")
    return round(sum(score.raw_score_0_10 * score.weight for score in materialized), 6)
