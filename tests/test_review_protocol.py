from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.domain.review_protocol import (
    Claim,
    CriterionScore,
    DecisionLedger,
    Evidence,
    EvidenceLevel,
    Finding,
    FindingSeverity,
    Obligation,
    Recommendation,
    RubricProfile,
    ReviewEvent,
    ReviewTrack,
    Verification,
    Verdict,
    diagnostic_total,
    normalize_score,
    resolve_verdict,
    resolve_claim_verdict,
    official_total,
)


def test_protocol_objects_validate_and_keep_evidence_locations() -> None:
    evidence = Evidence(
        id="ev-1",
        kind="document",
        asset_id="asset-1",
        block_id="block-3",
        page=4,
        paragraph=2,
        quote="The model was validated against the observed data.",
        evidence_level=EvidenceLevel.VERIFIED,
    )
    obligation = Obligation(id="obl-1", text="Provide validation evidence", required=True)
    claim = Claim(
        id="claim-1",
        exact_text="The model is valid.",
        obligation_ids=[obligation.id],
        evidence_ids=[evidence.id],
        verdict=Verdict.SUPPORTED,
        evidence_verified=True,
        locations=[evidence.location],
    )
    verification = Verification(
        id="ver-1",
        claim_id=claim.id,
        evidence_ids=[evidence.id],
        evidence_level=EvidenceLevel.INDEPENDENTLY_VERIFIED,
        passed=True,
    )
    finding = Finding(
        id="finding-1",
        title="Validation is documented",
        severity=FindingSeverity.MINOR,
        verdict=Verdict.SUPPORTED,
        evidence_ids=[evidence.id],
    )
    recommendation = Recommendation(
        id="rec-1",
        finding_id=finding.id,
        action="Add the validation data split to the appendix.",
        acceptance="A reviewer can reproduce the split from the appendix.",
    )
    score = CriterionScore(
        id="score-1",
        criterion="结果分析",
        track=ReviewTrack.DIAGNOSTIC,
        raw_score_0_10=8,
        weight=0.1,
        evidence_ids=[evidence.id],
        verdict=Verdict.SUPPORTED,
    )
    ledger = DecisionLedger(
        id="decision-1",
        subject_id=claim.id,
        decision="accepted",
        rationale="Evidence is independently checked.",
        evidence_ids=[evidence.id],
    )
    event = ReviewEvent(
        id="event-1",
        review_id="review-1",
        event_type="evidence_audit",
        reason="verification complete",
    )

    assert evidence.location["page"] == 4
    assert claim.verdict is Verdict.INCONCLUSIVE
    assert claim.requested_verdict is Verdict.SUPPORTED
    assert verification.passed is True
    assert finding.severity is FindingSeverity.MINOR
    assert recommendation.acceptance.startswith("A reviewer")
    assert score.track is ReviewTrack.DIAGNOSTIC
    assert ledger.decided_by == "human"
    assert event.review_id == "review-1"


def test_evidence_levels_and_verdicts_are_closed_enums() -> None:
    assert [level.value for level in EvidenceLevel] == [
        "NOT_CHECKED",
        "DERIVED",
        "EXECUTED",
        "VERIFIED",
        "INDEPENDENTLY_VERIFIED",
        "EXTERNALLY_VALIDATED",
    ]
    assert {verdict.value for verdict in Verdict} == {
        "SUPPORTED",
        "CONDITIONAL",
        "INCONCLUSIVE",
        "REFUTED",
    }
    with pytest.raises(ValidationError):
        Evidence(id="ev-bad", kind="document", evidence_level="PASS")


def test_missing_evidence_downgrades_supported_to_inconclusive() -> None:
    claim = Claim(id="claim-2", exact_text="An unsupported claim", verdict=Verdict.SUPPORTED)

    assert resolve_verdict(claim.verdict, evidence_count=0) is Verdict.INCONCLUSIVE
    assert resolve_verdict(Verdict.CONDITIONAL, evidence_count=0) is Verdict.INCONCLUSIVE


def test_supported_claim_with_unlocated_evidence_id_is_inconclusive() -> None:
    claim = Claim(
        id="claim-unlocated",
        exact_text="A claim with only an opaque evidence id",
        evidence_ids=["ev-opaque"],
        verdict=Verdict.SUPPORTED,
    )
    assert claim.verdict is Verdict.INCONCLUSIVE


def test_direct_strong_verdicts_are_downgraded_until_graph_resolution() -> None:
    claim = Claim(
        id="claim-unresolved-strong",
        exact_text="The model is supported.",
        verdict=Verdict.SUPPORTED,
        evidence_verified=True,
    )
    finding = Finding(
        id="finding-unresolved-strong",
        title="The claim is refuted",
        severity=FindingSeverity.MAJOR,
        verdict=Verdict.REFUTED,
        evidence_ids=["ev-counterexample"],
        locations=[{"page": 4}],
        evidence_verified=True,
    )

    assert claim.verdict is Verdict.INCONCLUSIVE
    assert claim.requested_verdict is Verdict.SUPPORTED
    assert finding.verdict is Verdict.INCONCLUSIVE
    assert finding.requested_verdict is Verdict.REFUTED


def test_refuted_finding_requires_evidence_id() -> None:
    finding = Finding(
        id="finding-unlocated",
        title="Unlocated contradiction",
        severity=FindingSeverity.MAJOR,
        verdict=Verdict.REFUTED,
    )
    assert finding.verdict is Verdict.INCONCLUSIVE


def test_conditional_and_refuted_verdicts_are_not_overridden_by_evidence_count() -> None:
    assert resolve_verdict(Verdict.CONDITIONAL, evidence_count=1) is Verdict.CONDITIONAL
    assert resolve_verdict(Verdict.REFUTED, evidence_count=0) is Verdict.INCONCLUSIVE
    assert resolve_verdict(Verdict.REFUTED, evidence_count=1, counterevidence=True) is Verdict.REFUTED


def test_normalize_score_and_diagnostic_total_use_seven_stage_weights() -> None:
    assert normalize_score(10) == 4.0
    assert normalize_score(7.5) == 3.0
    with pytest.raises(ValueError):
        normalize_score(10.1)

    scores = [
        CriterionScore(
            id=f"s-{idx}",
            criterion=criterion,
            track=ReviewTrack.DIAGNOSTIC,
            raw_score_0_10=10,
            weight=weight,
        )
        for idx, (criterion, weight) in enumerate(
            [
                    ("problem_identification", 0.15),
                    ("problem_formulation", 0.15),
                    ("assumptions", 0.15),
                    ("model_construction", 0.20),
                    ("solving", 0.10),
                    ("code_implementation", 0.15),
                    ("results_analysis", 0.10),
            ]
        )
    ]
    assert diagnostic_total(scores) == pytest.approx(100.0)


def test_diagnostic_total_rejects_duplicate_criteria_and_weight_drift() -> None:
    stages = [
        ("problem_identification", 0.15),
        ("problem_formulation", 0.15),
        ("assumptions", 0.15),
        ("model_construction", 0.20),
        ("solving", 0.10),
        ("code_implementation", 0.15),
        ("results_analysis", 0.10),
    ]
    scores = [
        CriterionScore(
            id=f"dup-{idx}",
            criterion=criterion,
            track=ReviewTrack.DIAGNOSTIC,
            raw_score_0_10=8,
            weight=weight,
        )
        for idx, (criterion, weight) in enumerate(stages)
    ]
    scores.append(
        CriterionScore(
            id="dup-extra",
            criterion="solving",
            track=ReviewTrack.DIAGNOSTIC,
            raw_score_0_10=8,
            weight=0.10,
        )
    )
    with pytest.raises(ValueError, match="duplicate"):
        diagnostic_total(scores)

    drifted_scores = [
        CriterionScore(
            id=f"drift-{idx}",
            criterion=criterion,
            track=ReviewTrack.DIAGNOSTIC,
            raw_score_0_10=8,
            weight=0.11 if criterion == "solving" else weight,
        )
        for idx, (criterion, weight) in enumerate(stages)
    ]
    with pytest.raises(ValueError, match="weight"):
        diagnostic_total(drifted_scores)


def test_official_and_diagnostic_scores_are_kept_on_separate_tracks() -> None:
    diagnostic = CriterionScore(
        id="diag-1",
        criterion="模型构造",
        track=ReviewTrack.DIAGNOSTIC,
        raw_score_0_10=8,
        weight=0.2,
    )
    official = CriterionScore(
        id="official-1",
        criterion="创新性",
        track=ReviewTrack.OFFICIAL,
        raw_score_0_10=95,
        weight=0.3,
        rubric_profile_id="official-v1",
        rubric_published=True,
        human_confirmed=True,
        rubric_decision_id="decision-rubric-v1",
        rubric_source_hash="sha256:rubric-v1",
    )

    assert diagnostic.normalized_score_0_4 == 3.2
    assert official.normalized_score_0_4 is None
    with pytest.raises(ValueError):
        diagnostic_total([diagnostic, official])


def test_official_score_requires_published_rubric_and_human_confirmation() -> None:
    with pytest.raises(ValidationError):
        CriterionScore(
            id="official-draft",
            criterion="创新性",
            track=ReviewTrack.OFFICIAL,
            raw_score_0_10=80,
            weight=1,
        )


def test_official_score_requires_decision_and_source_binding() -> None:
    with pytest.raises(ValidationError):
        CriterionScore(
            id="official-unbound",
            criterion="创新性",
            track=ReviewTrack.OFFICIAL,
            raw_score_0_10=80,
            weight=1,
            rubric_profile_id="official-v1",
            rubric_published=True,
            human_confirmed=True,
        )


def test_official_total_requires_published_profile_and_human_bound_decision() -> None:
    profile = RubricProfile(
        id="rubric-v1",
        version="1",
        source_hash="sha256:rubric-v1",
        published=True,
        criteria={"创新性": 0.4, "科学性": 0.6},
    )
    decision = DecisionLedger(
        id="decision-rubric-v1",
        subject_id=profile.id,
        decision="publish",
        rationale="Human confirmed the imported rubric.",
        decided_by="human",
    )
    scores = [
        CriterionScore(
            id="official-innovation",
            criterion="创新性",
            track=ReviewTrack.OFFICIAL,
            raw_score_0_10=80,
            weight=0.4,
            rubric_profile_id=profile.id,
            rubric_published=True,
            human_confirmed=True,
            rubric_decision_id=decision.id,
            rubric_source_hash=profile.source_hash,
        ),
        CriterionScore(
            id="official-science",
            criterion="科学性",
            track=ReviewTrack.OFFICIAL,
            raw_score_0_10=90,
            weight=0.6,
            rubric_profile_id=profile.id,
            rubric_published=True,
            human_confirmed=True,
            rubric_decision_id=decision.id,
            rubric_source_hash=profile.source_hash,
        ),
    ]

    assert official_total(scores, rubric_profile=profile, decision_ledger=decision) == pytest.approx(86.0)

    with pytest.raises(ValueError, match="published rubric"):
        official_total(scores, rubric_profile=profile.model_copy(update={"published": False}), decision_ledger=decision)

    with pytest.raises(ValueError, match="bound"):
        official_total(
            [scores[0].model_copy(update={"rubric_source_hash": "sha256:forged"}), scores[1]],
            rubric_profile=profile,
            decision_ledger=decision,
        )

    with pytest.raises(ValueError, match="human"):
        official_total(
            scores,
            rubric_profile=profile,
            decision_ledger=decision.model_copy(update={"decided_by": "gpt-6-luna"}),
        )


def test_rubric_profile_rejects_weight_drift_and_unknown_score_criterion() -> None:
    with pytest.raises(ValidationError, match="sum to 1"):
        RubricProfile(
            id="rubric-invalid",
            version="1",
            source_hash="sha256:invalid",
            published=True,
            criteria={"创新性": 0.5, "科学性": 0.6},
        )

    profile = RubricProfile(
        id="rubric-v2",
        version="2",
        source_hash="sha256:rubric-v2",
        published=True,
        criteria={"创新性": 1.0},
    )
    decision = DecisionLedger(
        id="decision-rubric-v2",
        subject_id=profile.id,
        decision="publish",
        rationale="Confirmed",
    )
    unknown = CriterionScore(
        id="official-unknown",
        criterion="不存在的项",
        track=ReviewTrack.OFFICIAL,
        raw_score_0_10=80,
        weight=1.0,
        rubric_profile_id=profile.id,
        rubric_published=True,
        human_confirmed=True,
        rubric_decision_id=decision.id,
        rubric_source_hash=profile.source_hash,
    )
    with pytest.raises(ValueError, match="criteria"):
        official_total([unknown], rubric_profile=profile, decision_ledger=decision)


def test_claim_verdict_requires_satisfied_obligations_and_located_evidence() -> None:
    evidence = Evidence(
        id="ev-claim",
        kind="document",
        asset_id="asset-1",
        page=2,
        quote="The result is stable under perturbation.",
        evidence_level=EvidenceLevel.VERIFIED,
    )
    obligation = Obligation(
        id="obl-claim",
        text="Show robustness evidence",
        required=True,
        fulfilled=True,
        evidence_ids=[evidence.id],
    )
    claim = Claim(
        id="claim-verified",
        exact_text="The result is robust.",
        obligation_ids=[obligation.id],
        evidence_ids=[evidence.id],
        verdict=Verdict.SUPPORTED,
    )
    assert resolve_claim_verdict(claim, [obligation], [evidence]) is Verdict.SUPPORTED

    obligation.fulfilled = False
    assert resolve_claim_verdict(claim, [obligation], [evidence]) is Verdict.INCONCLUSIVE

    unsupported = Evidence(id="ev-no-location", kind="model", evidence_level=EvidenceLevel.VERIFIED)
    obligation.fulfilled = True
    assert resolve_claim_verdict(claim, [obligation], [unsupported]) is Verdict.INCONCLUSIVE


def test_claim_resolution_rejects_unrelated_obligations_and_weak_evidence() -> None:
    claim = Claim(
        id="claim-strict",
        exact_text="The result is independently verified.",
        obligation_ids=["required-obligation"],
        evidence_ids=["weak-evidence"],
        verdict=Verdict.SUPPORTED,
    )
    unrelated = Obligation(id="other-obligation", text="Other", fulfilled=True, evidence_ids=["weak-evidence"])
    weak = Evidence(
        id="weak-evidence",
        kind="document",
        page=1,
        evidence_level=EvidenceLevel.DERIVED,
    )
    assert resolve_claim_verdict(claim, [unrelated], [weak]) is Verdict.INCONCLUSIVE


def test_claim_resolution_requires_each_fulfilled_obligation_to_cite_evidence() -> None:
    claim = Claim(
        id="claim-empty-obligation-evidence",
        exact_text="The model is validated.",
        obligation_ids=["validation-obligation"],
        evidence_ids=["ev-validation"],
        verdict=Verdict.SUPPORTED,
    )
    obligation = Obligation(
        id="validation-obligation",
        text="Show validation evidence",
        fulfilled=True,
        evidence_ids=[],
    )
    evidence = Evidence(
        id="ev-validation",
        kind="document",
        page=3,
        evidence_level=EvidenceLevel.VERIFIED,
    )

    assert resolve_claim_verdict(claim, [obligation], [evidence]) is Verdict.INCONCLUSIVE


def test_refuted_claim_requires_countercheck_evidence() -> None:
    claim = Claim(
        id="claim-refuted",
        exact_text="The model is globally optimal.",
        obligation_ids=["optimality-obligation"],
        evidence_ids=["ordinary-evidence"],
        countercheck_ids=["counterexample"],
        verdict=Verdict.REFUTED,
        counterevidence_verified=True,
    )
    obligation = Obligation(
        id="optimality-obligation",
        text="Prove global optimality",
        fulfilled=True,
        evidence_ids=["ordinary-evidence"],
    )
    ordinary = Evidence(id="ordinary-evidence", kind="document", page=2, evidence_level=EvidenceLevel.VERIFIED)
    counterexample = Evidence(id="counterexample", kind="counterexample", page=6, evidence_level=EvidenceLevel.VERIFIED)
    assert resolve_claim_verdict(claim, [obligation], [ordinary, counterexample]) is Verdict.INCONCLUSIVE
    claim.evidence_ids.append("counterexample")
    assert resolve_claim_verdict(claim, [obligation], [ordinary, counterexample]) is Verdict.REFUTED


def test_finding_severity_and_decision_timestamp_are_recorded() -> None:
    now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
    finding = Finding(
        id="fatal-1",
        title="Core result is refuted",
        severity=FindingSeverity.FATAL,
        verdict=Verdict.REFUTED,
        evidence_ids=["ev-counterexample"],
        locations=[{"asset_id": "asset-1", "page": 8}],
    )
    ledger = DecisionLedger(
        id="decision-2",
        subject_id=finding.id,
        decision="escalate",
        rationale="Counterexample requires human review.",
        decided_at=now,
    )

    assert finding.severity is FindingSeverity.FATAL
    assert ledger.decided_at == now
