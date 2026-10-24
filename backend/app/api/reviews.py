"""ReviewJob creation and retrieval endpoints.

This API freezes review inputs and accepts validated, evidence-bound stage and
result snapshots. It never invokes a model or executes uploaded code.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.debate import DebateError
from backend.app.domain.review_jobs import ReviewJob
from backend.app.services.review_jobs import ReviewJobError, build_review_job
from backend.app.services.review_coordinator import ReviewCoordinator, ReviewCoordinatorError
from backend.app.domain.review_results import ReviewResult
from backend.app.services.review_results import ReviewResultError, ReviewResultService
from backend.app.services.stage_orchestrator import StageOrchestrator, StageOrchestratorError, StageResult


class ReviewJobRepository(Protocol):
    def create(self, job: ReviewJob) -> ReviewJob: ...
    def get(self, job_id: str) -> ReviewJob | None: ...
    def list(self) -> list[ReviewJob]: ...
    def update(self, job: ReviewJob) -> ReviewJob: ...


class ReviewJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1)
    rubric_profile_id: str = Field(min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)


class ReviewTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    reason: str = Field(min_length=1)
    input_hash: str | None = None
    evidence_fingerprint: str | None = None
    findings: list[str] = Field(default_factory=list)
    assets_frozen: bool = False
    rubric_published: bool = False
    human_confirmed: bool = False
    final_confirmed: bool = False
    new_verified_evidence: bool = False
    verified_evidence_ids: list[str] = Field(default_factory=list)
    verified_evidence_bundle: list[dict[str, Any]] = Field(default_factory=list)


class ReviewRerunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    reason: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    input_hash: str | None = None
    evidence_fingerprint: str | None = None
    clear_dependency: str | None = None


class StageRerunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class ReviewRunRequest(BaseModel):
    """Start an asynchronous seven-stage run for a frozen ReviewJob."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    stage_ids: list[str] | None = None
    start_stage: str | None = None
    # Optional multi-agent debate options (enabled/max_rounds/expert_ids/...).
    # Omitted for backwards compatibility; the runner merges it into job.options.
    debate: dict[str, Any] | None = None


class DebateRunRequest(BaseModel):
    """Submit a multi-agent debate for a review (background, idempotent)."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    max_rounds: int | None = Field(default=None, ge=1, le=5)
    expert_ids: list[str] | None = None


class StageRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    reason: str = Field(default="manual stage run", min_length=1)


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "details": {}}})


def _runner_error(exc: Exception) -> JSONResponse:
    """Convert runner failures to a safe, uniform response.

    Runner implementations expose a stable ``code`` attribute where possible;
    messages are intentionally reduced for unknown failures so model payloads,
    credentials, and paper text never leak through the API.
    """

    code = str(getattr(exc, "code", "run_failed"))
    status = int(getattr(exc, "status_code", 409 if code in {"run_already_active", "idempotency_conflict"} else 422))
    safe_messages = {
        "review_not_found": "评审任务不存在",
        "review_not_ready": "评审任务尚未通过人工确认或不在可执行状态",
        "review_dependencies_missing": "评审资产或量表不存在",
        "input_snapshot_changed": "评审输入哈希已变化，必须重新创建评审任务",
        "idempotency_required": "必须提供幂等键",
        "run_already_active": "评审任务已有运行中的任务",
        "idempotency_conflict": "幂等键已用于其他运行",
        "runner_unavailable": "评审运行器未配置",
        "invalid_stage": "阶段标识无效",
        "stage_rerun_rejected": "阶段重跑请求被拒绝",
        "run_failed": "评审运行启动失败",
    }
    return _error(code, safe_messages.get(code, "评审运行失败"), status)


def _job_dict(job: ReviewJob) -> dict[str, Any]:
    return job.model_dump(mode="json")


def create_review_router(repository: ReviewJobRepository | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

    def _repo(request: Request) -> ReviewJobRepository:
        return repository or request.app.state.review_job_repository

    @router.post("", status_code=201)
    def create_review(request: Request, body: ReviewJobCreateRequest):
        asset_store = getattr(request.app.state, "asset_store", None)
        rubric_repo = getattr(request.app.state, "rubric_repository", None)
        if asset_store is None or rubric_repo is None:
            return _error("review_dependencies_unavailable", "评审任务依赖未配置", 503)
        asset = asset_store.get(body.asset_id)
        rubric = rubric_repo.get(body.rubric_profile_id)
        try:
            job = build_review_job(asset=asset, rubric=rubric, options=body.options)
            created = _repo(request).create(job)
            return _job_dict(created)
        except ReviewJobError as exc:
            msg = str(exc)
            if "asset not found" in msg:
                return _error("asset_not_found", msg, 404)
            if "rubric not found" in msg:
                return _error("rubric_not_found", msg, 404)
            if "published rubric" in msg:
                return _error("rubric_not_published", msg, 409)
            if "already exists" in msg:
                return _error("review_exists", msg, 409)
            return _error("review_create_failed", msg, 422)
        except Exception:
            return _error("review_persistence_failed", "评审任务保存失败", 422)

    @router.post("/{review_id}/run", status_code=202)
    def start_review_run(review_id: str, body: ReviewRunRequest, request: Request):
        runner = getattr(request.app.state, "review_runner", None)
        if runner is None or not hasattr(runner, "start_run"):
            return _error("runner_unavailable", "评审运行器未配置", 503)
        try:
            # Only forward ``debate`` when supplied so runners predating the
            # debate iteration (and fakes in tests) keep their old signature.
            kwargs: dict[str, Any] = {
                "stage_ids": body.stage_ids,
                "start_stage": body.start_stage,
                "idempotency_key": body.idempotency_key,
            }
            if body.debate is not None:
                kwargs["debate"] = body.debate
            snapshot = runner.start_run(review_id, **kwargs)
            return snapshot
        except Exception as exc:
            return _runner_error(exc)

    @router.get("/{review_id}/progress")
    def review_progress(review_id: str, request: Request):
        runner = getattr(request.app.state, "review_runner", None)
        if runner is None or not hasattr(runner, "get_progress"):
            return _error("runner_unavailable", "评审运行器未配置", 503)
        try:
            return runner.get_progress(review_id)
        except Exception as exc:
            return _runner_error(exc)

    @router.post("/{review_id}/stages/{stage_id}/run", status_code=202)
    def start_stage_run(review_id: str, stage_id: str, body: StageRunRequest, request: Request):
        runner = getattr(request.app.state, "review_runner", None)
        if runner is None or not hasattr(runner, "start_stage_run"):
            return _error("runner_unavailable", "评审运行器未配置", 503)
        try:
            return runner.start_stage_run(
                review_id,
                stage_id,
                reason=body.reason,
                idempotency_key=body.idempotency_key,
            )
        except Exception as exc:
            return _runner_error(exc)

    @router.get("/{review_id}/debate")
    def get_debate(review_id: str, request: Request):
        debate_runner = getattr(request.app.state, "debate_runner", None)
        if debate_runner is None:
            return _error("debate_unavailable", "辩论服务未配置", 503)
        snap = debate_runner.get(review_id)
        if snap is None:
            return _error("debate_not_found", "该评审没有辩论记录", 404)
        return snap

    @router.post("/{review_id}/debate/run", status_code=202)
    def run_debate(review_id: str, body: DebateRunRequest, request: Request):
        debate_runner = getattr(request.app.state, "debate_runner", None)
        if debate_runner is None:
            return _error("debate_unavailable", "辩论服务未配置", 503)
        options: dict[str, Any] = {}
        if body.max_rounds is not None:
            options["max_rounds"] = body.max_rounds
        if body.expert_ids is not None:
            options["expert_ids"] = body.expert_ids
        try:
            # Idempotency and active-run conflicts are handled inside
            # DebateRunManager.submit; pass the result through untouched.
            payload = debate_runner.submit(review_id, options=options, idempotency_key=body.idempotency_key)
        except DebateError as exc:
            # DebateError messages are fixed safe phrases produced by the engine.
            return _error(exc.code, str(exc), exc.status_code)
        return JSONResponse(status_code=202, content=payload)

    @router.get("/{review_id}/debate/rounds/{round_number}")
    def get_debate_round(review_id: str, round_number: int, request: Request):
        debate_runner = getattr(request.app.state, "debate_runner", None)
        if debate_runner is None:
            return _error("debate_unavailable", "辩论服务未配置", 503)
        snap = debate_runner.get(review_id)
        if snap is None:
            return _error("debate_not_found", "该评审没有辩论记录", 404)
        rounds = snap.get("rounds") or []
        if round_number < 0 or round_number >= len(rounds):
            return _error("invalid_round", "轮次不存在", 404)
        return rounds[round_number]

    @router.get("")
    def list_reviews(request: Request):
        return [_job_dict(job) for job in _repo(request).list()]

    @router.get("/{review_id}")
    def get_review(review_id: str, request: Request):
        job = _repo(request).get(review_id)
        if job is None:
            return _error("review_not_found", "评审任务不存在", 404)
        return _job_dict(job)

    @router.post("/{review_id}/transition")
    def transition_review(review_id: str, body: ReviewTransitionRequest, request: Request):
        if not hasattr(_repo(request), "update"):
            return _error("review_transition_unavailable", "评审状态持久化未配置", 503)
        coordinator = ReviewCoordinator(_repo(request), timezone_name=getattr(request.app.state, "settings", None).app_timezone if getattr(request.app.state, "settings", None) else "Asia/Shanghai")
        try:
            job = coordinator.transition(
                review_id,
                body.target,
                reason=body.reason,
                input_hash=body.input_hash,
                evidence_fingerprint=body.evidence_fingerprint,
                findings=tuple(body.findings),
                assets_frozen=body.assets_frozen,
                rubric_published=body.rubric_published,
                human_confirmed=body.human_confirmed,
                final_confirmed=body.final_confirmed,
                new_verified_evidence=body.new_verified_evidence,
                verified_evidence_ids=tuple(body.verified_evidence_ids),
                verified_evidence_bundle=tuple(body.verified_evidence_bundle),
            )
            return _job_dict(job)
        except ReviewCoordinatorError as exc:
            code = "review_not_found" if "not found" in str(exc) else "invalid_review_transition"
            return _error(code, str(exc), 404 if code == "review_not_found" else 409)

    @router.post("/{review_id}/rerun")
    def rerun_review(review_id: str, body: ReviewRerunRequest, request: Request):
        if not hasattr(_repo(request), "update"):
            return _error("review_rerun_unavailable", "评审状态持久化未配置", 503)
        settings = getattr(request.app.state, "settings", None)
        coordinator = ReviewCoordinator(_repo(request), timezone_name=settings.app_timezone if settings else "Asia/Shanghai")
        try:
            job = coordinator.rerun(
                review_id,
                body.stage,
                reason=body.reason,
                idempotency_key=body.idempotency_key,
                input_hash=body.input_hash,
                evidence_fingerprint=body.evidence_fingerprint,
                clear_dependency=body.clear_dependency,
            )
            return _job_dict(job)
        except ReviewCoordinatorError as exc:
            code = "review_not_found" if "not found" in str(exc) else "invalid_review_rerun"
            return _error(code, str(exc), 404 if code == "review_not_found" else 409)

    @router.post("/{review_id}/stages")
    def write_stage_result(review_id: str, body: dict[str, Any], request: Request):
        repository = _repo(request)
        asset_store = getattr(request.app.state, "asset_store", None)
        if asset_store is None or not hasattr(repository, "update"):
            return _error("stage_execution_unavailable", "阶段结果存储未配置", 503)
        settings = getattr(request.app.state, "settings", None)
        orchestrator = StageOrchestrator(
            repository,
            asset_store,
            timezone_name=settings.app_timezone if settings else "Asia/Shanghai",
        )
        try:
            job = orchestrator.write_result(review_id, body)
            return _job_dict(job)
        except StageOrchestratorError as exc:
            code = "review_not_found" if "not found" in str(exc) else "stage_result_rejected"
            return _error(code, str(exc), 404 if code == "review_not_found" else 422)

    @router.put("/{review_id}/result")
    def save_review_result(review_id: str, body: dict[str, Any], request: Request):
        repository = _repo(request)
        try:
            payload = dict(body)
            payload["review_id"] = review_id
            result = ReviewResult.model_validate(payload)
            saved = ReviewResultService(repository).save(result)
            return saved.to_snapshot()
        except ReviewResultError as exc:
            code = "review_not_found" if "not found" in str(exc) else "result_save_failed"
            return _error(code, str(exc), 404 if code == "review_not_found" else 422)
        except Exception as exc:
            return _error("result_validation_failed", str(exc), 422)

    @router.get("/{review_id}/result")
    def get_review_result(review_id: str, request: Request):
        try:
            result = ReviewResultService(_repo(request)).load(review_id)
        except Exception as exc:
            return _error("result_load_failed", str(exc), 422)
        if result is None:
            return _error("result_not_found", "评审结果不存在", 404)
        return result.to_snapshot()

    @router.post("/{review_id}/stages/{stage_id}", status_code=200)
    def write_stage_result(review_id: str, stage_id: str, body: StageResult, request: Request):
        asset_store = getattr(request.app.state, "asset_store", None)
        if asset_store is None:
            return _error("review_dependencies_unavailable", "评审资产依赖未配置", 503)
        if body.stage_id != stage_id:
            return _error("stage_mismatch", "路径阶段与结果阶段不一致", 422)
        orchestrator = StageOrchestrator(
            _repo(request), asset_store,
            timezone_name=getattr(getattr(request.app.state, "settings", None), "app_timezone", "Asia/Shanghai"),
        )
        try:
            return _job_dict(orchestrator.write_result(review_id, body))
        except StageOrchestratorError as exc:
            code = "review_not_found" if "not found" in str(exc) else "stage_result_rejected"
            return _error(code, str(exc), 404 if code == "review_not_found" else 422)

    @router.post("/{review_id}/stages/{stage_id}/rerun", status_code=200)
    def rerun_stage(review_id: str, stage_id: str, body: StageRerunRequest, request: Request):
        asset_store = getattr(request.app.state, "asset_store", None)
        if asset_store is None:
            return _error("review_dependencies_unavailable", "评审资产依赖未配置", 503)
        orchestrator = StageOrchestrator(
            _repo(request), asset_store,
            timezone_name=getattr(getattr(request.app.state, "settings", None), "app_timezone", "Asia/Shanghai"),
        )
        try:
            return _job_dict(orchestrator.rerun_stage(review_id, stage_id, reason=body.reason))
        except StageOrchestratorError as exc:
            code = "review_not_found" if "not found" in str(exc) else "stage_rerun_rejected"
            return _error(code, str(exc), 404 if code == "review_not_found" else 409)

    return router


router = create_review_router()

__all__ = ["router", "create_review_router", "ReviewJobCreateRequest", "ReviewRunRequest", "DebateRunRequest"]
