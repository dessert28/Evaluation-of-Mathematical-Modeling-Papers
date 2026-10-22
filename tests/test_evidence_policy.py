import pytest

from backend.app.services.evidence_policy import (
    EvidenceLevel,
    Verdict,
    diagnostic_score,
    normalize_score,
    resolve_verdict,
)
from backend.app.domain.review_protocol import (
    EvidenceLevel as ProtocolEvidenceLevel,
    Verdict as ProtocolVerdict,
)


def test_normalize_raw_score_to_zero_to_four():
    assert normalize_score(0) == 0
    assert normalize_score(5) == 2
    assert normalize_score(10) == 4


def test_normalize_score_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        normalize_score(-0.1)
    with pytest.raises(ValueError):
        normalize_score(10.1)


def test_diagnostic_score_uses_seven_stage_weights():
    scores = {stage: 10 for stage in (
        "problem_identification",
        "problem_formulation",
        "assumptions",
        "model_construction",
        "solving",
        "code_implementation",
        "results_analysis",
    )}
    assert diagnostic_score(scores) == 100


def test_evidence_policy_reuses_protocol_enums():
    assert EvidenceLevel is ProtocolEvidenceLevel
    assert Verdict is ProtocolVerdict


def test_missing_evidence_is_inconclusive():
    assert resolve_verdict(
        obligations_satisfied=True,
        evidence=[{"level": EvidenceLevel.NOT_CHECKED, "locator": None}],
    ) == Verdict.INCONCLUSIVE


def test_sufficient_located_evidence_supports_claim():
    assert resolve_verdict(
        obligations_satisfied=True,
        evidence=[{"level": EvidenceLevel.VERIFIED, "locator": "page:3"}],
    ) == Verdict.SUPPORTED


def test_explicit_scope_or_assumption_yields_conditional():
    assert resolve_verdict(
        obligations_satisfied=True,
        evidence=[{"level": EvidenceLevel.VERIFIED, "locator": "page:3"}],
        conditional=True,
    ) == Verdict.CONDITIONAL


def test_counterevidence_has_highest_precedence():
    assert resolve_verdict(
        obligations_satisfied=True,
        evidence=[{"level": EvidenceLevel.VERIFIED, "locator": "page:3"}],
        refuted=True,
    ) == Verdict.REFUTED


def test_refutation_without_located_counterevidence_is_inconclusive():
    assert resolve_verdict(
        obligations_satisfied=True,
        evidence=[],
        refuted=True,
    ) == Verdict.INCONCLUSIVE
