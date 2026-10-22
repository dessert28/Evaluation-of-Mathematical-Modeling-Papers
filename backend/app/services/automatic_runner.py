"""Local deterministic runner for the seven diagnostic stages."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from backend.app.domain.review_protocol import DIAGNOSTIC_STAGE_WEIGHTS, Evidence, CriterionScore, ReviewTrack, Verdict, diagnostic_total
from backend.app.domain.review_results import ReviewResult
from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.services.stage_orchestrator import StageResult
from backend.app.services.review_results import ReviewResultService
from backend.app.services.llm_adapter import LLMAdapterError


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    run_status: RunStatus
    current_stage: str | None
    completed_stages: list[str]
    failed_stages: list[str]
    completed_weight: float
    diagnostic_total: float | None
    diagnostic_total_status: str
    stage_runs: dict[str, dict[str, Any]]
    last_error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "run_status": self.run_status.value, "current_stage": self.current_stage,
                "completed_stages": self.completed_stages, "failed_stages": self.failed_stages,
                "completed_weight": self.completed_weight, "diagnostic_total": self.diagnostic_total,
                "diagnostic_total_status": self.diagnostic_total_status, "stage_runs": self.stage_runs,
                "last_error": self.last_error}


class AutomaticRunnerError(ValueError):
    pass


class AutomaticReviewRunner:
    stage_ids = tuple(DIAGNOSTIC_STAGE_WEIGHTS)

    def __init__(self, store: Any, asset_lookup: Callable[[str], Any | None], rubric_lookup: Callable[[str], Any | None], adapter: Any, *, result_service: ReviewResultService | None = None, max_context_chars: int = 120_000, prompt_version: str = "v0.1") -> None:
        self.store = store
        self.asset_lookup = asset_lookup
        self.rubric_lookup = rubric_lookup
        self.adapter = adapter
        self.result_service = result_service or ReviewResultService(store)
        self.max_context_chars = max_context_chars
        self.prompt_version = prompt_version

    def _job(self, review_id: str) -> ReviewJob:
        job = self.store.get(review_id)
        if job is None:
            raise AutomaticRunnerError("review job not found")
        return job

    def build_context(self, review_id: str) -> tuple[str, str, dict[str, Any]]:
        job = self._job(review_id)
        asset = self.asset_lookup(job.asset_id)
        if asset is None or getattr(asset.status, "value", asset.status) != "parsed":
            raise AutomaticRunnerError("review asset must be parsed")
        blocks = sorted(getattr(asset, "blocks", ()), key=lambda b: b.block_order)
        parts, used = [], 0
        truncated = False
        for block in blocks:
            text = str(block.text or "")
            chunk = f"[{block.block_id}] {text}\n"
            if used + len(chunk) > self.max_context_chars:
                remain = max(0, self.max_context_chars - used)
                if remain:
                    parts.append(chunk[:remain])
                truncated = True
                break
            parts.append(chunk); used += len(chunk)
        context = "".join(parts) or "（空文档）"
        catalog = "\n".join(json.dumps({"block_id": b.block_id, "asset_id": b.asset_id, "page": b.page, "paragraph": b.paragraph, "line_start": b.line_start, "line_end": b.line_end}, ensure_ascii=False) for b in blocks) or "（无证据块）"
        rubric = self.rubric_lookup(job.rubric_profile_id)
        meta = {"context_truncated": truncated, "block_count": len(blocks), "rubric": getattr(rubric, "id", job.rubric_profile_id)}
        return context, catalog, meta

    def _rubric_context(self, rubric: Any) -> str:
        if rubric is None:
            return "（未提供）"
        criteria = getattr(rubric, "criteria", [])
        return json.dumps({"name": getattr(rubric, "name", ""), "version": getattr(rubric, "version", ""), "criteria": [getattr(c, "model_dump", lambda: c)() for c in criteria]}, ensure_ascii=False)

    @staticmethod
    def _safe_endpoint(endpoint: Any) -> str | None:
        """Keep only a non-sensitive endpoint origin/path in snapshots."""
        if endpoint is None:
            return None
        try:
            parsed = urlsplit(str(endpoint))
            host = parsed.hostname or ""
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
        except Exception:
            return None

    def _save(
        self,
        job: ReviewJob,
        summary: RunSummary,
        results: dict[str, StageResult],
        *,
        clear_stage_ids: tuple[str, ...] = (),
        context_meta: dict[str, Any] | None = None,
    ) -> ReviewJob:
        snap = dict(job.state_snapshot or {})
        snap["stage_results"] = {key: value.model_dump(mode="json") for key, value in results.items()}
        stale = dict(snap.get("stage_stale") or {})
        for stage_id in clear_stage_ids:
            stale[stage_id] = False
        snap["stage_stale"] = stale
        if context_meta is not None:
            snap["context"] = dict(context_meta)
        snap["run"] = summary.to_dict()
        snap["run_id"] = summary.run_id
        snap["run_status"] = summary.run_status.value
        snap["prompt_version"] = self.prompt_version
        snap["model_metadata"] = self.adapter.safe_metadata() if hasattr(self.adapter, "safe_metadata") else {"model": getattr(getattr(self.adapter, "settings", None), "openai_compatible_model", None)}
        state = job.state
        if summary.run_status is RunStatus.DEGRADED:
            state = ReviewJobStatus.DEGRADED
        updated = job.model_copy(update={"state": state, "state_snapshot": snap, "updated_at": datetime.now(timezone.utc)})
        self.store.update(updated)
        if results:
            evidence = []; obligations = []; claims = []; findings = []; scores = []
            for stage in results.values():
                evidence.extend(stage.evidence); obligations.extend(stage.obligations); claims.extend(stage.claims); findings.extend(stage.findings); scores.append(stage.criterion_score())
            # de-duplicate by protocol id while preserving stage order
            uniq = lambda xs: list({x.id: x for x in xs}.values())
            rr = ReviewResult(review_id=job.id, evidence=uniq(evidence), obligations=uniq(obligations), claims=uniq(claims), findings=uniq(findings), diagnostic_scores=scores, metadata={"run": summary.to_dict(), "prompt_version": self.prompt_version, "model_metadata": snap.get("model_metadata", {})})
            self.result_service.save(rr)
        return updated

    def run(
        self,
        review_id: str,
        *,
        run_id: str | None = None,
        stage_ids: list[str] | None = None,
        start_stage: str | None = None,
        force_rerun: bool = False,
    ) -> RunSummary:
        job = self._job(review_id)
        selected = list(stage_ids or self.stage_ids)
        force_rerun = force_rerun or start_stage is not None
        if start_stage:
            if start_stage not in self.stage_ids: raise AutomaticRunnerError(f"unknown stage: {start_stage}")
            selected = list(self.stage_ids[self.stage_ids.index(start_stage):])
        if any(stage not in self.stage_ids for stage in selected): raise AutomaticRunnerError("unknown diagnostic stage")
        context, catalog, context_meta = self.build_context(review_id)
        asset = self.asset_lookup(job.asset_id)
        block_by_id = {str(block.block_id): block for block in getattr(asset, "blocks", ())}
        rubric = self.rubric_lookup(job.rubric_profile_id)
        run_key = run_id or f"run-{uuid4().hex}"
        stage_results: dict[str, StageResult] = {}
        for stage_id, payload in (job.state_snapshot or {}).get("stage_results", {}).items():
            if not (job.state_snapshot or {}).get("stage_stale", {}).get(stage_id, False):
                try:
                    stage_results[stage_id] = StageResult.model_validate(payload)
                except Exception:
                    continue
        completed = [stage for stage in self.stage_ids if stage in stage_results]
        failed = []
        previous_run = dict((job.state_snapshot or {}).get("run") or {})
        stage_runs = dict(previous_run.get("stage_runs") or {})
        prior: list[dict[str, Any]] = [
            {"stage_id": stage, "score": stage_results[stage].raw_score_0_10, "rationale": stage_results[stage].rationale}
            for stage in self.stage_ids
            if stage in stage_results
        ]
        last_error = None
        summary = RunSummary(run_key, RunStatus.RUNNING, None, completed, failed, 0.0, None, "partial", stage_runs)
        self._save(job, summary, stage_results, context_meta=context_meta)
        current_job = self._job(review_id)
        for stage_id in selected:
            if stage_id in stage_results and not force_rerun:
                # Completed, non-stale stages are reused unless explicitly invalidated.
                continue
            summary = RunSummary(run_key, RunStatus.RUNNING, stage_id, completed, failed, sum(DIAGNOSTIC_STAGE_WEIGHTS[s] for s in completed), None, "partial", stage_runs, last_error)
            prior_text = json.dumps(prior, ensure_ascii=False)
            try:
                result, meta = self.adapter.evaluate_stage(stage_id, paper_context=context, evidence_catalog=catalog, rubric_context=self._rubric_context(rubric), prior_results=prior_text)
                for evidence in result.evidence:
                    if evidence.asset_id != job.asset_id: raise AutomaticRunnerError("stage evidence must reference review asset")
                    if not evidence.block_id and evidence.page is None and evidence.paragraph is None and evidence.line_start is None and not evidence.quote_hash and not evidence.source_locator:
                        raise AutomaticRunnerError("stage evidence requires a stable location")
                    if evidence.block_id:
                        block = block_by_id.get(evidence.block_id)
                        if block is None or block.asset_id != job.asset_id:
                            raise AutomaticRunnerError("stage evidence references an unknown document block")
                        if evidence.page is not None and evidence.page != block.page:
                            raise AutomaticRunnerError("stage evidence page does not match the document block")
                        if evidence.paragraph is not None and evidence.paragraph != block.paragraph:
                            raise AutomaticRunnerError("stage evidence paragraph does not match the document block")
                        if evidence.line_start is not None and evidence.line_start != block.line_start:
                            raise AutomaticRunnerError("stage evidence line_start does not match the document block")
                        if evidence.line_end is not None and evidence.line_end != block.line_end:
                            raise AutomaticRunnerError("stage evidence line_end does not match the document block")
                stage_results[stage_id] = result
                if stage_id not in completed:
                    completed.append(stage_id)
                prior = [
                    {"stage_id": stage, "score": stage_results[stage].raw_score_0_10, "rationale": stage_results[stage].rationale}
                    for stage in self.stage_ids
                    if stage in stage_results
                ]
                stage_runs[stage_id] = {"status": "COMPLETED", "attempts": meta.attempts, "model": meta.model, "endpoint": self._safe_endpoint(getattr(meta, "endpoint", None)), "verdict": result.criterion_score().verdict.value, "completed_at": datetime.now(timezone.utc).isoformat()}
            except Exception as exc:
                failed.append(stage_id)
                code = getattr(exc, "code", "stage_failed")
                last_error = {"code": code, "message": "阶段评审未能生成有效的结构化结果"}
                stage_runs[stage_id] = {"status": "FAILED", "verdict": Verdict.INCONCLUSIVE.value, "error_code": code, "completed_at": datetime.now(timezone.utc).isoformat()}
            current_job = self._job(review_id)
            status = RunStatus.DEGRADED if failed else RunStatus.RUNNING
            interim = RunSummary(run_key, status, stage_id, completed, failed, sum(DIAGNOSTIC_STAGE_WEIGHTS[s] for s in completed), None, "partial", stage_runs, last_error)
            self._save(current_job, interim, stage_results, clear_stage_ids=(stage_id,) if stage_id in stage_results else ())
        total = None
        total_status = "complete" if len(completed) == len(self.stage_ids) and not failed else "partial"
        if total_status == "complete":
            total = diagnostic_total([stage_results[s].criterion_score() for s in self.stage_ids])
        final = RunSummary(run_key, RunStatus.DEGRADED if failed else RunStatus.COMPLETED, None, completed, failed, sum(DIAGNOSTIC_STAGE_WEIGHTS[s] for s in completed), total, total_status, stage_runs, last_error)
        self._save(self._job(review_id), final, stage_results)
        return final


__all__ = ["AutomaticReviewRunner", "AutomaticRunnerError", "RunStatus", "RunSummary"]
