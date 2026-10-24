"""Deterministic seven-stage evaluation result coordinator.

This module stores structured stage output in the ReviewJob snapshot.  It has
no model calls and never executes uploaded code; callers must provide already
validated evidence and audit objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.domain.review_jobs import ReviewJob
from backend.app.domain.review_protocol import (
    Claim,
    CriterionScore,
    DIAGNOSTIC_STAGE_WEIGHTS,
    Evidence,
    Finding,
    Obligation,
    ReviewTrack,
)
from backend.app.services.review_coordinator import machine_for_job
from backend.app.services.state_machine import ReviewJobStateMachine


class StageOrchestratorError(ValueError):
    """Raised when stage output cannot be accepted deterministically."""


class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: str
    raw_score_0_10: float = Field(ge=0, le=10)
    rationale: str = Field(min_length=1)
    evidence: list[Evidence] = Field(min_length=1)
    obligations: list[Obligation] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    run_id: str = Field(default_factory=lambda: f"stage-run-{uuid4().hex}")
    stale: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id(cls, value: str) -> str:
        if value not in DIAGNOSTIC_STAGE_WEIGHTS:
            raise ValueError(f"unknown diagnostic stage: {value}")
        return value

    @model_validator(mode="after")
    def validate_references(self) -> "StageResult":
        evidence_ids = {item.id for item in self.evidence}
        if len(evidence_ids) != len(self.evidence):
            raise ValueError("stage evidence IDs must be unique")
        obligation_ids = {item.id for item in self.obligations}
        if len(obligation_ids) != len(self.obligations):
            raise ValueError("stage obligation IDs must be unique")
        claim_ids = {item.id for item in self.claims}
        if len(claim_ids) != len(self.claims):
            raise ValueError("stage claim IDs must be unique")
        finding_ids = {item.id for item in self.findings}
        if len(finding_ids) != len(self.findings):
            raise ValueError("stage finding IDs must be unique")
        for obligation in self.obligations:
            if not set(obligation.evidence_ids).issubset(evidence_ids):
                raise ValueError(f"obligation {obligation.id} references unknown evidence")
        for claim in self.claims:
            if not set(claim.evidence_ids).issubset(evidence_ids):
                raise ValueError(f"claim {claim.id} references unknown evidence")
            if not set(claim.obligation_ids).issubset(obligation_ids):
                raise ValueError(f"claim {claim.id} references unknown obligation")
        for finding in self.findings:
            if not set(finding.evidence_ids).issubset(evidence_ids):
                raise ValueError(f"finding {finding.id} references unknown evidence")
            if not set(finding.claim_ids).issubset(claim_ids):
                raise ValueError(f"finding {finding.id} references unknown claim")
        return self

    @property
    def weight(self) -> float:
        return DIAGNOSTIC_STAGE_WEIGHTS[self.stage_id]

    def criterion_score(self) -> CriterionScore:
        return CriterionScore(
            id=f"score-{self.stage_id}-{self.run_id}",
            criterion=self.stage_id,
            track=ReviewTrack.DIAGNOSTIC,
            raw_score_0_10=self.raw_score_0_10,
            weight=self.weight,
            score_rationale=self.rationale,
            evidence_ids=[item.id for item in self.evidence],
        )


class StageJobStore(Protocol):
    def get(self, job_id: str) -> ReviewJob | None: ...
    def update(self, job: ReviewJob) -> ReviewJob: ...


class AssetLookup(Protocol):
    def get(self, asset_id: str) -> Any | None: ...


_STAGES = tuple(DIAGNOSTIC_STAGE_WEIGHTS)


class StageOrchestrator:
    """Accept and invalidate stage results with deterministic checks."""

    def __init__(self, store: StageJobStore, asset_store: AssetLookup, *, timezone_name: str = "Asia/Shanghai") -> None:
        self.store = store
        self.asset_store = asset_store
        self.timezone_name = timezone_name

    def _load(self, job_id: str) -> ReviewJob:
        job = self.store.get(job_id)
        if job is None:
            raise StageOrchestratorError("review job not found")
        asset = self.asset_store.get(job.asset_id)
        if asset is None:
            raise StageOrchestratorError("review asset not found")
        if getattr(asset.status, "value", asset.status) != "parsed":
            raise StageOrchestratorError("review asset must be parsed before stage evaluation")
        return job

    @staticmethod
    def _snapshot(job: ReviewJob) -> dict[str, Any]:
        snapshot = dict(job.state_snapshot or {})
        snapshot.setdefault("stage_results", {})
        snapshot.setdefault("stage_stale", {})
        return snapshot

    def write_result(self, job_id: str, result: StageResult | dict[str, Any]) -> ReviewJob:
        job = self._load(job_id)
        try:
            parsed = result if isinstance(result, StageResult) else StageResult.model_validate(result)
        except Exception as exc:
            raise StageOrchestratorError(str(exc)) from exc
        for evidence in parsed.evidence:
            if evidence.asset_id != job.asset_id:
                raise StageOrchestratorError("stage evidence must reference the review asset")
            # An asset ID alone is not a reviewable citation.  Require a
            # document block, page/paragraph/line, quote hash, or source
            # locator so later Claim resolution can reproduce the location.
            if not any(
                getattr(evidence, field) is not None
                for field in ("block_id", "page", "paragraph", "line_start", "line_end", "quote_hash", "source_locator")
            ):
                raise StageOrchestratorError("stage evidence requires a stable location")
        snapshot = self._snapshot(job)
        results = dict(snapshot["stage_results"])
        stale = dict(snapshot["stage_stale"])
        results[parsed.stage_id] = parsed.model_dump(mode="json")
        stale[parsed.stage_id] = False
        snapshot["stage_results"] = results
        snapshot["stage_stale"] = stale
        return self.store.update(job.model_copy(update={"state_snapshot": snapshot, "updated_at": datetime.now(timezone.utc)}))

    def mark_stage_stale(self, job_id: str, stage_id: str, *, reason: str) -> ReviewJob:
        job = self._load(job_id)
        if stage_id not in DIAGNOSTIC_STAGE_WEIGHTS:
            raise StageOrchestratorError(f"unknown diagnostic stage: {stage_id}")
        snapshot = self._snapshot(job)
        stale = dict(snapshot["stage_stale"])
        start = _STAGES.index(stage_id)
        for stage in _STAGES[start:]:
            stale[stage] = True
        snapshot["stage_stale"] = stale
        machine = (
            machine_for_job(job, timezone_name=self.timezone_name)
            if (job.state_snapshot or {}).get("job_id")
            else ReviewJobStateMachine(
                job.id,
                initial_state=job.state.value,
                timezone=self.timezone_name,
            )
        )
        machine.mark_stale(reason=reason, dependency=f"stage:{stage_id}")
        snapshot.update(machine.to_dict())
        self._mark_debate_stale(job_id)
        return self.store.update(job.model_copy(update={"state_snapshot": snapshot, "updated_at": datetime.now(timezone.utc)}))

    def _mark_debate_stale(self, job_id: str) -> None:
        """Flag a persisted multi-agent debate snapshot as stale with the stages.

        The store protocol here is intentionally minimal, so the debate
        snapshot methods are optional; stores without them (including test
        fakes) are silently skipped and the stage flow never blocks.
        """
        if not (hasattr(self.store, "get_debate_snapshot") and hasattr(self.store, "save_debate_snapshot")):
            return
        try:
            debate_snapshot = self.store.get_debate_snapshot(job_id)
        except Exception:
            return
        if debate_snapshot is None:
            return
        debate_snapshot = dict(debate_snapshot)
        debate_snapshot["stale"] = True
        try:
            self.store.save_debate_snapshot(job_id, debate_snapshot)
        except Exception:
            pass

    def rerun_stage(self, job_id: str, stage_id: str, *, reason: str) -> ReviewJob:
        return self.mark_stage_stale(job_id, stage_id, reason=reason)


__all__ = ["StageOrchestrator", "StageOrchestratorError", "StageResult"]
