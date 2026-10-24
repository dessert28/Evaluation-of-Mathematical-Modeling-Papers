"""Multi-agent debate review engine (v0.1).

``DebateService.run_sync`` drives a full panel debate for one review:

- Round 0 elicits a structured opinion from each expert in parallel.
- Rounds 1..max_rounds elicit debate messages (AGREE / QUALIFY / DISAGREE /
  REFUTE / WITHDRAW) from each expert, honouring the protocol evidence rules
  (every REFUTE must cite evidence, every evidence id must be known).
- A deterministic aggregation layer (``backend.app.domain.debate``) converts
  the messages into a persisted ``DebateSnapshot``.

The engine never leaks model endpoints, keys, or paper full-text: all error
messages are replaced with fixed safe phrases before they reach a snapshot.

``DebateRunManager`` runs a debate as a background task, providing idempotent
submission, snapshot reads, and crash recovery (QUEUED/RUNNING -> INTERRUPTED).
"""

from __future__ import annotations

import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from backend.app.domain.debate import (
    DebateError,
    DebateMessage,
    DebateMessageBatch,
    DebateOutcome,
    DebateRound,
    DebateSnapshot,
    DebateStatus,
    MessageDraft,
    PanelOpinion,
    PanelOpinionBatch,
    Stance,
    compute_agreement,
    evaluate_panel,
    is_converged,
)
from backend.app.services.debate_panel import DebateConfig, DebatePanelStore
from backend.app.services.llm_adapter import LLMAdapterError
from backend.app.services.prompt_templates import PromptTemplateStore

_SAFE_MESSAGES: dict[str, str] = {
    "llm_not_configured": "模型未配置，无法启动辩论",
    "llm_transport_error": "模型服务连接失败",
    "llm_http_error": "模型服务返回错误",
    "llm_http_nonretryable": "模型服务返回错误",
    "schema_validation_failed": "模型输出结构校验失败",
    "invalid_json_response": "模型返回解析失败",
    "prompt_empty": "提示词为空",
    "invalid_evidence": "引用了未知的证据",
    "invalid_target": "引用了不存在的意见",
    "debate_failed": "辩论未能产生有效结果",
}

_VALID_STATES = frozenset({"EVALUATING", "EVIDENCE_AUDIT", "ARBITRATING", "DEGRADED"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _error_code(exc: Exception) -> str:
    return str(getattr(exc, "code", None) or "debate_failed")


def _error_message(code: str) -> str:
    return _SAFE_MESSAGES.get(code, "辩论执行失败")


def _is_no_model(exc: Exception) -> bool:
    return isinstance(exc, LLMAdapterError) and exc.code == "llm_not_configured"


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_threshold(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1.0:
        return 1.0
    if number <= 0.0:
        return default
    return number


class _NoModel:  # internal sentinel namespace for abort handling
    pass


class DebateService:
    """Orchestrates a full multi-agent debate and persists a snapshot."""

    def __init__(
        self,
        store,
        *,
        asset_lookup: Callable[[Any], Any] | None = None,
        rubric_lookup: Callable[[Any], Any] | None = None,
        adapter,
        panel_store: DebatePanelStore | None = None,
        prompt_store: PromptTemplateStore | None = None,
        settings: Any | None = None,
        context_builder: Callable[[Any], tuple[str, str, str]] | None = None,
        executor: Callable[..., ThreadPoolExecutor] | None = None,
        max_workers: int = 3,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.asset_lookup = asset_lookup
        self.rubric_lookup = rubric_lookup
        self.panel_store = panel_store or DebatePanelStore()
        self.prompt_store = prompt_store or PromptTemplateStore()
        self.settings = settings
        self.context_builder = context_builder
        self._executor_factory = executor or (
            lambda max_workers: ThreadPoolExecutor(max_workers=max_workers)
        )
        self.max_workers = max_workers

    # -- public surface -----------------------------------------------------

    def snapshot(self, review_id: str) -> dict | None:
        return self.store.get_debate_snapshot(review_id)

    def run_sync(self, review_id: str, *, options: dict | None = None) -> dict:
        options = dict(options or {})
        job = self.store.get(review_id)
        if job is None:
            raise DebateError("debate_not_found", "评审不存在", status_code=404)
        if getattr(job, "state", None) not in _VALID_STATES:
            raise DebateError("review_not_ready", "评审当前状态不允许启动辩论", status_code=409)

        existing = self.store.get_debate_snapshot(review_id)
        if existing is not None:
            existing_status = existing.get("status")
            if existing_status in {"QUEUED", "RUNNING"}:
                raise DebateError("debate_already_active", "辩论已在进行中", status_code=409)
            existing_key = (existing.get("config") or {}).get("idempotency_key")
            if existing_key == options.get("idempotency_key"):
                return existing

        evidence_ids = self._collect_evidence_ids(job)
        if not evidence_ids:
            raise DebateError("debate_not_ready", "缺少证据基座，无法启动辩论", status_code=409)

        config = self.panel_store.load()
        try:
            experts = self.panel_store.resolve_experts(options.get("expert_ids"))
        except ValueError as exc:
            raise DebateError("invalid_panel", f"无效专家面板：{exc}", status_code=422) from exc

        display_ids = []
        for idx, expert in enumerate(experts, start=1):
            if config.anonymize:
                display_ids.append(f"expert-{idx}")
            else:
                display_ids.append(expert.id)
        panel = [
            {"expert_id": display_ids[idx], "lens": experts[idx].label, "weight": experts[idx].weight}
            for idx in range(len(experts))
        ]

        max_rounds = _clamp_int(options.get("max_rounds"), 1, 5, config.max_rounds)
        min_rounds = _clamp_int(options.get("min_rounds"), 1, max_rounds, config.min_rounds)
        min_rounds = min(min_rounds, max_rounds)

        cfg = {
            "idempotency_key": options.get("idempotency_key"),
            "max_rounds": max_rounds,
            "min_rounds": min_rounds,
            "agreement_threshold": _clamp_threshold(
                options.get("agreement_threshold"), config.agreement_threshold
            ),
            "accept_threshold": _clamp_threshold(options.get("accept_threshold"), config.accept_threshold),
            "fatal_bonus": config.fatal_bonus,
            "max_calls": config.max_calls,
            "reject_retry": config.reject_retry,
            "anonymize": config.anonymize,
            "expert_ids": options.get("expert_ids") or [expert.id for expert in experts],
        }

        snapshot = DebateSnapshot(
            review_id=review_id,
            status=DebateStatus.RUNNING,
            panel=panel,
            config=cfg,
            call_budget={"used": 0, "max": cfg["max_calls"]},
        )
        self._persist(snapshot)

        context = self._build_context(job)

        try:
            self._run_debate(
                snapshot,
                experts=experts,
                display_ids=display_ids,
                context=context,
                evidence_ids=evidence_ids,
                config=config,
                cfg=cfg,
                max_rounds=max_rounds,
                min_rounds=min_rounds,
            )
        except LLMAdapterError as exc:
            if _is_no_model(exc):
                snapshot.status = DebateStatus.FAILED
                snapshot.last_error = {
                    "code": "llm_not_configured",
                    "message": _error_message("llm_not_configured"),
                }
                snapshot.updated_at = _utc_now()
                self._persist(snapshot)
                raise DebateError(
                    "llm_not_configured", _error_message("llm_not_configured"), status_code=422
                ) from exc
            raise

        if snapshot.status is DebateStatus.FAILED:
            self._persist(snapshot)
            raise DebateError("debate_failed", _error_message("debate_failed"), status_code=422)

        result = snapshot.model_dump(mode="json")
        return result

    # -- internals ----------------------------------------------------------

    def _persist(self, snapshot: DebateSnapshot) -> None:
        self.store.save_debate_snapshot(snapshot.review_id, snapshot.model_dump(mode="json"))

    def _collect_evidence_ids(self, job) -> set[str]:
        ids: set[str] = set()
        state_snapshot = getattr(job, "state_snapshot", None)
        if isinstance(state_snapshot, dict):
            results = state_snapshot.get("stage_results") or {}
        else:
            results = getattr(state_snapshot, "stage_results", None) or {}
        if isinstance(results, dict):
            results = list(results.values())
        for result in results:
            evidence = result.get("evidence") if isinstance(result, dict) else getattr(result, "evidence", None)
            if not isinstance(evidence, list):
                continue
            for item in evidence:
                eid = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
                if eid:
                    ids.add(str(eid))
        if ids:
            return ids
        if self.context_builder is not None:
            try:
                built = self.context_builder(job)
            except Exception:
                return ids
            ids.update(_scan_evidence_ids(built))
        return ids

    def _stage_summary(self, job) -> str:
        state_snapshot = getattr(job, "state_snapshot", None)
        if isinstance(state_snapshot, dict):
            results = state_snapshot.get("stage_results") or {}
        else:
            results = getattr(state_snapshot, "stage_results", None) or {}
        if isinstance(results, dict):
            results = list(results.values())
        if not results:
            return "（无）"
        lines = []
        for result in results:
            sid = result.get("stage_id") if isinstance(result, dict) else getattr(result, "stage_id", None)
            evidence = result.get("evidence") if isinstance(result, dict) else getattr(result, "evidence", None)
            lines.append(f"{sid}: {len(evidence or [])} 条证据")
        return "；".join(lines)

    def _build_context(self, job) -> dict[str, str]:
        paper_context = evidence_catalog = rubric_context = "（未提供）"
        if self.context_builder is not None:
            try:
                pc, ec, rc = self.context_builder(job)
                paper_context, evidence_catalog, rubric_context = pc, ec, rc
            except Exception:
                pass
        elif self.asset_lookup is not None:
            try:
                assets = self.asset_lookup(job)
                paper_context = _friendly(assets, "paper")
                evidence_catalog = _friendly(assets, "evidence")
            except Exception:
                pass
        if self.rubric_lookup is not None:
            try:
                rubric = self.rubric_lookup(job)
                rubric_context = _friendly(rubric, "rubric")
            except Exception:
                pass
        return {
            "paper_context": paper_context,
            "evidence_catalog": evidence_catalog,
            "rubric_context": rubric_context,
            "stage_results_summary": self._stage_summary(job),
        }

    def _run_debate(
        self,
        snapshot: DebateSnapshot,
        *,
        experts,
        display_ids,
        context,
        evidence_ids,
        config: DebateConfig,
        cfg: dict,
        max_rounds: int,
        min_rounds: int,
    ) -> None:
        known = set(evidence_ids)
        opinions = self._run_round0(snapshot, experts, display_ids, context, config, known)
        messages_all: list[DebateMessage] = []
        stop_reason = "max_rounds"
        degraded = False
        debate_rounds = 0

        for r in range(1, max_rounds + 1):
            used = int(snapshot.call_budget.get("used", 0))
            if used + len(experts) > int(snapshot.call_budget.get("max", cfg["max_calls"])):
                stop_reason = "budget_exhausted"
                break
            debate_rounds = r
            round_messages, round_rejected, round_calls = self._run_message_round(
                snapshot,
                round_number=r,
                experts=experts,
                display_ids=display_ids,
                opinions=opinions,
                messages_all=messages_all,
                known=known,
                config=config,
            )
            snapshot.call_budget["used"] = int(snapshot.call_budget.get("used", 0)) + round_calls
            messages_all.extend(round_messages)

            if not round_messages:
                if messages_all:
                    degraded = True
                    stop_reason = "failed"
                else:
                    snapshot.status = DebateStatus.FAILED
                    code_counts: dict[str, int] = {}
                    for rej in round_rejected:
                        code = rej.get("code", "unknown")
                        code_counts[code] = code_counts.get(code, 0) + 1
                    snapshot.last_error = {
                        "code": "debate_failed",
                        "message": _error_message("debate_failed"),
                        "details": {"rejected_codes": code_counts},
                    }
                    snapshot.updated_at = _utc_now()
                    self._persist(snapshot)
                    raise DebateError("debate_failed", _error_message("debate_failed"), status_code=422)

            rng = random.Random(f"{snapshot.review_id}:{r}")
            speaker_order = list(display_ids)
            rng.shuffle(speaker_order)
            snapshot.rounds.append(
                DebateRound(
                    round_number=r,
                    speaker_order=speaker_order,
                    status="COMPLETED" if round_messages else "PARTIAL",
                    opinions=[],
                    messages=round_messages,
                    rejected=round_rejected,
                )
            )
            self._persist(snapshot)
            if degraded:
                break
            if is_converged(
                opinions,
                messages_all,
                rounds_run=r,
                agreement_threshold=float(cfg["agreement_threshold"]),
                min_rounds=int(cfg["min_rounds"]),
            ):
                stop_reason = "converged"
                break

        expert_weights = {
            display_ids[idx]: float(experts[idx].weight) for idx in range(len(experts))
        }
        outcome = evaluate_panel(
            opinions,
            messages_all,
            rounds_run=debate_rounds,
            accept_threshold=float(cfg["accept_threshold"]),
            fatal_bonus=float(cfg["fatal_bonus"]),
            expert_weights=expert_weights,
            stop_reason=stop_reason,  # type: ignore[arg-type]
        )
        snapshot.outcome = outcome
        if degraded:
            snapshot.status = DebateStatus.DEGRADED
        else:
            snapshot.status = DebateStatus.COMPLETED
        snapshot.call_budget["used"] = int(snapshot.call_budget.get("used", 0))
        snapshot.updated_at = _utc_now()
        self._persist(snapshot)

    def _run_round0(self, snapshot, experts, display_ids, context, config, known):
        bundle = self.prompt_store.debate_prompt(
            "panel_opinion",
            paper_context=context["paper_context"],
            evidence_catalog=context["evidence_catalog"],
            rubric_context=context["rubric_context"],
            stage_results_summary=context["stage_results_summary"],
            expert_lens="、".join(expert.lens or expert.label for expert in experts),
            max_opinions=str(config.max_opinions_per_expert),
        )
        opinions: list[PanelOpinion] = []
        rejected: list[dict] = []
        used = 0
        with self._executor_factory(self.max_workers) as executor:
            futures = {}
            for idx, expert in enumerate(experts):
                futures[executor.submit(
                    self.adapter.complete_json,
                    system_prompt=bundle.system,
                    user_prompt=bundle.user,
                    response_model=PanelOpinionBatch,
                )] = idx
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    batch, _metadata = fut.result()
                except Exception as exc:  # noqa: BLE001 - recorded per-expert
                    if _is_no_model(exc):
                        raise
                    rejected.append(
                        {"expert_id": display_ids[idx], "code": _error_code(exc), "message": _error_message(_error_code(exc))}
                    )
                    used += 1
                    continue
                used += 1
                overlaps = []
                overflow = []
                for n, draft in enumerate(batch.opinions):
                    if n >= config.max_opinions_per_expert:
                        overflow.append(
                            {"expert_id": display_ids[idx], "code": "too_many_opinions", "message": "意见数超过限制"}
                        )
                        continue
                    if not set(draft.evidence_ids) <= known:
                        overlaps.append(
                            {
                                "expert_id": display_ids[idx],
                                "code": "invalid_evidence",
                                "message": "引用了未知的证据",
                                "evidence_ids": draft.evidence_ids,
                            }
                        )
                        continue
                    opinions.append(
                        PanelOpinion(
                            id=f"op-0-expert-{idx}-{n}",
                            expert_id=display_ids[idx],
                            stage_id=draft.stage_id,
                            lens=experts[idx].label,
                            title=draft.title,
                            detail=draft.detail,
                            severity=draft.severity,
                            evidence_ids=draft.evidence_ids,
                            confidence=draft.confidence,
                        )
                    )
                rejected.extend(overlaps)
                rejected.extend(overflow)
        snapshot.call_budget["used"] = used
        if not opinions:
            snapshot.status = DebateStatus.FAILED
            # Keep triage-safe diagnostics: fixed code vocabulary only
            # (no endpoint, key, or paper content).
            code_counts: dict[str, int] = {}
            for rej in rejected:
                code = rej.get("code", "unknown")
                code_counts[code] = code_counts.get(code, 0) + 1
            snapshot.last_error = {
                "code": "debate_failed",
                "message": _error_message("debate_failed"),
                "details": {"rejected_codes": code_counts},
            }
            snapshot.updated_at = _utc_now()
            self._persist(snapshot)
            raise DebateError("debate_failed", _error_message("debate_failed"), status_code=422)

        snapshot.rounds.append(
            DebateRound(
                round_number=0,
                speaker_order=list(display_ids),
                status="COMPLETED",
                opinions=opinions,
                messages=[],
                rejected=rejected,
            )
        )
        self._persist(snapshot)
        return opinions

    def _run_message_round(
        self, snapshot, *, round_number, experts, display_ids, opinions, messages_all, known, config
    ):
        valid_target_ids = {opinion.id for opinion in opinions}
        opinions_json = json.dumps([o.model_dump(mode="json") for o in opinions], ensure_ascii=False)
        previous_json = json.dumps(
            [m.model_dump(mode="json") for m in messages_all], ensure_ascii=False
        )
        known_json = json.dumps(sorted(known), ensure_ascii=False)
        results: list[tuple[list, list, int]] = []
        with self._executor_factory(self.max_workers) as executor:
            futures = {}
            for idx, expert in enumerate(experts):
                futures[executor.submit(
                    self._produce_messages,
                    idx,
                    expert,
                    round_number,
                    opinions_json,
                    previous_json,
                    known,
                    known_json,
                    valid_target_ids,
                    display_ids,
                    config,
                )] = idx
            for fut in as_completed(futures):
                results.append(fut.result())
        round_messages: list[DebateMessage] = []
        round_rejected: list[dict] = []
        round_calls = 0
        for valid, rejected, calls in results:
            round_messages.extend(valid)
            round_rejected.extend(rejected)
            round_calls += calls
        return round_messages, round_rejected, round_calls

    def _produce_messages(
        self, idx, expert, round_number, opinions_json, previous_json, known, known_json,
        valid_target_ids, display_ids, config,
    ):
        valid: list[DebateMessage] = []
        rejected: list[dict] = []
        calls = 0
        attempts = int(config.reject_retry) + 1
        last_reason = None
        for _ in range(attempts):
            valid = []
            values = {
                "round_number": str(round_number),
                "opinions_json": opinions_json,
                "previous_messages_json": previous_json,
                "own_expert_id": display_ids[idx],
                "known_evidence_ids": known_json,
                "expert_lens": expert.lens or expert.label,
            }
            if last_reason is not None:
                values["previous_messages_json"] = (
                    previous_json + "\n[上一次被拒绝原因] " + last_reason
                )
            bundle = self.prompt_store.debate_prompt("debate_message", **values)
            try:
                batch, _metadata = self.adapter.complete_json(
                    system_prompt=bundle.system,
                    user_prompt=bundle.user,
                    response_model=DebateMessageBatch,
                )
            except Exception as exc:  # noqa: BLE001
                calls += 1
                if _is_no_model(exc):
                    raise
                rejected.append(
                    {"expert_id": display_ids[idx], "code": _error_code(exc), "message": _error_message(_error_code(exc))}
                )
                break
            calls += 1
            had_invalid = False
            for draft in batch.messages:
                reason = self._validate_message_draft(draft, valid_target_ids, known)
                if reason is not None:
                    rejected.append(
                        {"expert_id": display_ids[idx], "code": reason, "message": _error_message(reason)}
                    )
                    had_invalid = True
                    continue
                valid.append(
                    DebateMessage(
                        id=f"msg-{round_number}-expert-{idx}-{len(valid)}",
                        round=round_number,
                        expert_id=display_ids[idx],
                        target_opinion_id=draft.target_opinion_id,
                        stance=draft.stance,
                        evidence_ids=draft.evidence_ids,
                        confidence=draft.confidence,
                        rationale=draft.rationale,
                        revised_title=draft.revised_title,
                        revised_detail=draft.revised_detail,
                        revised_severity=draft.revised_severity,
                    )
                )
            if not had_invalid:
                last_reason = None
                break
            last_reason = "部分消息未通过论证校验，请仅引用已提供证据并指向有效意见"
        return valid, rejected, calls

    @staticmethod
    def _validate_message_draft(draft: MessageDraft, valid_target_ids, known) -> str | None:
        if draft.target_opinion_id not in valid_target_ids:
            return "invalid_target"
        if not set(draft.evidence_ids) <= known:
            return "invalid_evidence"
        if draft.stance is Stance.REFUTE and not draft.evidence_ids:
            return "invalid_evidence"
        return None


class DebateRunManager:
    """Runs debates on a background executor with idempotent submission."""

    def __init__(self, service: DebateService, *, max_workers: int = 1) -> None:
        self.service = service
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="debate")
        self._lock = threading.Lock()

    def submit(
        self, review_id: str, *, options: dict | None = None, idempotency_key: str
    ) -> dict:
        options = dict(options or {})
        options.setdefault("idempotency_key", idempotency_key)
        existing = self.store().get_debate_snapshot(review_id)
        if existing is not None:
            existing_status = existing.get("status")
            if existing_status in {"QUEUED", "RUNNING"}:
                raise DebateError("debate_already_active", "辩论已在进行中", status_code=409)
            existing_key = (existing.get("config") or {}).get("idempotency_key")
            if existing_key == idempotency_key:
                return {
                    "review_id": review_id,
                    "debate_status": existing_status,
                    "idempotency_key": idempotency_key,
                }
        self._executor.submit(self._run, review_id, options, idempotency_key)
        return {
            "review_id": review_id,
            "debate_status": "QUEUED",
            "idempotency_key": idempotency_key,
        }

    def store(self):
        return self.service.store

    def get(self, review_id: str) -> dict | None:
        return self.service.store.get_debate_snapshot(review_id)

    def recover_one(self, review_id: str) -> None:
        snap = self.service.store.get_debate_snapshot(review_id)
        if snap is not None and snap.get("status") in {"QUEUED", "RUNNING"}:
            snap["status"] = "INTERRUPTED"
            snap["updated_at"] = _utc_now().isoformat()
            self.service.store.save_debate_snapshot(review_id, snap)

    def _run(self, review_id: str, options: dict, idempotency_key: str) -> None:
        try:
            self.service.run_sync(review_id, options=options)
        except Exception as exc:  # noqa: BLE001 - never let a future die loudly
            code = _error_code(exc)
            snap = self.service.store.get_debate_snapshot(review_id)
            if snap is not None:
                snap["status"] = "FAILED"
                snap["last_error"] = {"code": code, "message": _error_message(code)}
                snap["updated_at"] = _utc_now().isoformat()
                self.service.store.save_debate_snapshot(review_id, snap)


def _scan_evidence_ids(value: Any, found: set[str] | None = None) -> set[str]:
    found = found if found is not None else set()
    if isinstance(value, dict):
        evidence = value.get("evidence")
        if isinstance(evidence, list):
            for item in evidence:
                eid = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
                if eid:
                    found.add(str(eid))
        for v in value.values():
            _scan_evidence_ids(v, found)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _scan_evidence_ids(v, found)
    else:
        eid = getattr(value, "id", None)
        if value is not None and eid:
            found.add(str(eid))
    return found


def _friendly(value: Any, key: str) -> str:
    if isinstance(value, dict) and key in value and value[key]:
        return str(value[key])
    return "（未提供）"


__all__ = ["DebateRunManager", "DebateService"]
