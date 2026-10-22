"""Local in-process lifecycle manager for automatic review runs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from backend.app.domain.review_jobs import ReviewJobStatus
from backend.app.services.automatic_runner import AutomaticReviewRunner, RunStatus
from backend.app.services.llm_adapter import OpenAICompatibleAdapter
from backend.app.services.review_coordinator import ReviewCoordinator
from backend.app.services.state_machine import ReviewState


class ReviewRunManagerError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ReviewRunManager:
    """Serialize runs per review while persisting progress in ReviewJob JSON."""

    ACTIVE = {RunStatus.QUEUED.value, RunStatus.RUNNING.value}

    def __init__(self, store: Any, asset_store: Any, rubric_store: Any, settings: Any, *, adapter: Any | None = None):
        self.store = store
        self.asset_store = asset_store
        self.rubric_store = rubric_store
        self.settings = settings
        self.adapter = adapter or OpenAICompatibleAdapter(settings)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="review-run")
        self._lock = RLock()
        self._futures: dict[str, Future[Any]] = {}
        self._recover_interrupted()

    def _recover_interrupted(self) -> None:
        for job in self.store.list():
            run = dict((job.state_snapshot or {}).get("run") or {})
            if run.get("run_status") in self.ACTIVE:
                run["run_status"] = RunStatus.INTERRUPTED.value
                run["last_error"] = {"code": "process_interrupted", "message": "服务重启时运行尚未完成"}
                snapshot = dict(job.state_snapshot or {})
                snapshot["run"] = run
                snapshot["run_status"] = run["run_status"]
                # The coordinator owns lifecycle state changes and its event ledger.
                job = self.store.update(job.model_copy(update={"state_snapshot": snapshot}))
                try:
                    recovered = ReviewCoordinator(self.store, timezone_name=self.settings.app_timezone).transition(
                        job.id, ReviewState.DEGRADED, reason="服务重启时自动评审运行中断"
                    )
                    recovered_snapshot = dict(recovered.state_snapshot or {})
                    recovered_snapshot["run"] = run
                    recovered_snapshot["run_status"] = run["run_status"]
                    self.store.update(recovered.model_copy(update={"state_snapshot": recovered_snapshot, "updated_at": datetime.now(timezone.utc)}))
                except Exception:
                    # A malformed historical lifecycle snapshot remains visible
                    # as INTERRUPTED; do not fabricate a state-machine transition.
                    continue

    def _job(self, review_id: str):
        job = self.store.get(review_id)
        if job is None:
            raise ReviewRunManagerError("review_not_found", "评审任务不存在", 404)
        if job.state not in {
            ReviewJobStatus.EVALUATING,
            ReviewJobStatus.DEGRADED,
            ReviewJobStatus.EVIDENCE_AUDIT,
        }:
            raise ReviewRunManagerError("review_not_ready", "评审任务必须先通过人工确认并进入 EVALUATING", 409)
        asset = self.asset_store.get(job.asset_id)
        rubric = self.rubric_store.get(job.rubric_profile_id)
        if asset is None or rubric is None:
            raise ReviewRunManagerError("review_dependencies_missing", "评审资产或量表不存在", 409)
        if getattr(asset.status, "value", asset.status) != "parsed" or getattr(rubric.status, "value", rubric.status) != "published":
            raise ReviewRunManagerError("review_dependencies_missing", "评审资产未解析或官方量表未发布", 409)
        if str(getattr(asset, "sha256", "")) != str(job.asset_sha256) or str(getattr(rubric, "source_hash", "")) != str(job.rubric_source_hash):
            raise ReviewRunManagerError("input_snapshot_changed", "评审输入哈希已变化，必须重新创建评审任务", 409)
        return job

    @staticmethod
    def _snapshot(job: Any) -> dict[str, Any]:
        return dict((job.state_snapshot or {}).get("run") or {})

    def _queue(self, job: Any, run_id: str, idempotency_key: str, selected: list[str], *, force_rerun: bool) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "run_status": RunStatus.QUEUED.value,
            "current_stage": None,
            "completed_stages": [],
            "failed_stages": [],
            "completed_weight": 0.0,
            "diagnostic_total": None,
            "diagnostic_total_status": "partial",
            "stage_runs": {},
            "requested_stages": selected,
            "force_rerun": force_rerun,
            "idempotency_key": idempotency_key,
            "last_error": None,
        }
        state_snapshot = dict(job.state_snapshot or {})
        state_snapshot["run"] = payload
        state_snapshot.update({"run_id": run_id, "run_status": payload["run_status"]})
        updated = job.model_copy(update={"state_snapshot": state_snapshot, "updated_at": datetime.now(timezone.utc)})
        self.store.update(updated)
        return {"review_id": job.id, **payload}

    def _ensure_evaluating(self, job: Any, *, idempotency_key: str, clear_dependency: str | None = None) -> Any:
        """Resume an exception/audit state through the deterministic coordinator."""
        if job.state is ReviewJobStatus.EVALUATING and clear_dependency is None:
            return job
        coordinator = ReviewCoordinator(self.store, timezone_name=self.settings.app_timezone)
        try:
            return coordinator.rerun(
                job.id,
                ReviewState.EVALUATING,
                reason="自动评审运行恢复",
                idempotency_key=idempotency_key,
                clear_dependency=clear_dependency,
            )
        except Exception as exc:
            raise ReviewRunManagerError("review_not_ready", "评审任务无法恢复到 EVALUATING", 409) from exc

    def start_run(self, review_id: str, *, stage_ids: list[str] | None = None, start_stage: str | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
        key = (idempotency_key or "").strip()
        if not key:
            raise ReviewRunManagerError("idempotency_required", "必须提供幂等键", 422)
        selected = list(stage_ids or AutomaticReviewRunner.stage_ids)
        if start_stage:
            if start_stage not in AutomaticReviewRunner.stage_ids:
                raise ReviewRunManagerError("invalid_stage", "阶段标识无效", 422)
            selected = list(AutomaticReviewRunner.stage_ids[AutomaticReviewRunner.stage_ids.index(start_stage):])
        if any(stage not in AutomaticReviewRunner.stage_ids for stage in selected):
            raise ReviewRunManagerError("invalid_stage", "阶段标识无效", 422)
        if len(selected) != len(set(selected)):
            raise ReviewRunManagerError("invalid_stage", "阶段标识不能重复", 422)
        with self._lock:
            job = self._job(review_id)
            current = self._snapshot(job)
            if current.get("idempotency_key") == key:
                if current.get("requested_stages") == selected:
                    return {"review_id": job.id, **current}
                raise ReviewRunManagerError("idempotency_conflict", "幂等键已用于其他运行请求", 409)
            if current.get("run_status") in self.ACTIVE:
                raise ReviewRunManagerError("run_already_active", "评审任务已有运行中的任务", 409)
            job = self._ensure_evaluating(job, idempotency_key=key)
            run_id = f"run-{uuid4().hex}"
            force_rerun = stage_ids is not None or start_stage is not None
            queued = self._queue(job, run_id, key, selected, force_rerun=force_rerun)
            future = self._executor.submit(self._execute, review_id, run_id, selected, force_rerun, key)
            self._futures[review_id] = future
            return queued

    def start_stage_run(self, review_id: str, stage_id: str, *, reason: str = "manual stage run", idempotency_key: str | None = None) -> dict[str, Any]:
        if stage_id not in AutomaticReviewRunner.stage_ids:
            raise ReviewRunManagerError("invalid_stage", "阶段标识无效", 422)
        key = (idempotency_key or "").strip()
        if not key:
            raise ReviewRunManagerError("idempotency_required", "必须提供幂等键", 422)
        from backend.app.services.stage_orchestrator import StageOrchestrator, StageOrchestratorError

        with self._lock:
            job = self._job(review_id)
            current = self._snapshot(job)
            if current.get("idempotency_key") == key:
                if current.get("requested_stages") == [stage_id]:
                    return {"review_id": review_id, **current}
                raise ReviewRunManagerError("idempotency_conflict", "幂等键已用于其他运行请求", 409)
            if current.get("run_status") in self.ACTIVE:
                raise ReviewRunManagerError("run_already_active", "评审任务已有运行中的任务", 409)
            try:
                StageOrchestrator(self.store, self.asset_store, timezone_name=self.settings.app_timezone).mark_stage_stale(
                    review_id, stage_id, reason=reason
                )
            except StageOrchestratorError as exc:
                raise ReviewRunManagerError("stage_rerun_rejected", str(exc), 409) from exc
            job = self._job(review_id)
            self._ensure_evaluating(job, idempotency_key=key, clear_dependency=f"stage:{stage_id}")
            return self.start_run(review_id, stage_ids=[stage_id], idempotency_key=key)

    def get_progress(self, review_id: str) -> dict[str, Any]:
        job = self.store.get(review_id)
        if job is None:
            raise ReviewRunManagerError("review_not_found", "评审任务不存在", 404)
        run = self._snapshot(job)
        if not run:
            return {"review_id": review_id, "run_status": None, "completed_stages": [], "failed_stages": []}
        return {"review_id": review_id, **run}

    def _execute(self, review_id: str, run_id: str, selected: list[str], force_rerun: bool = False, idempotency_key: str | None = None) -> None:
        runner = AutomaticReviewRunner(self.store, self.asset_store.get, self.rubric_store.get, self.adapter)
        try:
            runner.run(review_id, run_id=run_id, stage_ids=selected, force_rerun=force_rerun)
            job = self.store.get(review_id)
            run = self._snapshot(job)
            if run.get("run_status") == RunStatus.COMPLETED.value and len(run.get("completed_stages", [])) == len(AutomaticReviewRunner.stage_ids):
                coordinator = ReviewCoordinator(self.store, timezone_name=self.settings.app_timezone)
                coordinator.transition(review_id, ReviewState.EVIDENCE_AUDIT, reason="七阶段自动评审完成")
            job = self.store.get(review_id)
            if job is not None:
                run = self._snapshot(job)
                run["idempotency_key"] = idempotency_key
                run["requested_stages"] = selected
                run["force_rerun"] = force_rerun
                snap = dict(job.state_snapshot or {})
                snap["run"] = run
                self.store.update(job.model_copy(update={"state_snapshot": snap, "updated_at": datetime.now(timezone.utc)}))
        except Exception as exc:
            job = self.store.get(review_id)
            if job is None:
                return
            run = self._snapshot(job)
            code = str(getattr(exc, "code", "run_failed"))
            run.update({"run_id": run_id, "run_status": RunStatus.FAILED.value, "requested_stages": selected, "force_rerun": force_rerun, "idempotency_key": idempotency_key, "last_error": {"code": code, "message": "评审运行失败"}})
            snap = dict(job.state_snapshot or {})
            snap["run"] = run
            snap["run_status"] = RunStatus.FAILED.value
            self.store.update(job.model_copy(update={"state": ReviewJobStatus.FAILED, "state_snapshot": snap, "updated_at": datetime.now(timezone.utc)}))


__all__ = ["ReviewRunManager", "ReviewRunManagerError"]
