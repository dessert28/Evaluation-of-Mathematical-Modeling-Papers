"""Deterministic review-job state machine.

The service deliberately contains no model calls or persistence code.  It
guards lifecycle transitions and emits an immutable in-memory event ledger;
the API/database layers can persist the returned events later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping
from zoneinfo import ZoneInfo


class ReviewState(str, Enum):
    """All externally visible states of a review job."""

    CREATED = "CREATED"
    INGESTING = "INGESTING"
    ASSETS_FROZEN = "ASSETS_FROZEN"
    RUBRIC_CONFIRMATION = "RUBRIC_CONFIRMATION"
    EVALUATING = "EVALUATING"
    EVIDENCE_AUDIT = "EVIDENCE_AUDIT"
    ARBITRATING = "ARBITRATING"
    REPORT_READY = "REPORT_READY"

    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_MAJOR_FIXES = "NEEDS_MAJOR_FIXES"
    REVIEWABLE = "REVIEWABLE"
    FROZEN = "FROZEN"


class InvalidTransitionError(ValueError):
    """Raised when a caller attempts a transition outside the protocol."""


LIFECYCLE_STATES: tuple[ReviewState, ...] = (
    ReviewState.CREATED,
    ReviewState.INGESTING,
    ReviewState.ASSETS_FROZEN,
    ReviewState.RUBRIC_CONFIRMATION,
    ReviewState.EVALUATING,
    ReviewState.EVIDENCE_AUDIT,
    ReviewState.ARBITRATING,
    ReviewState.REPORT_READY,
)


# Only deterministic, forward lifecycle moves are accepted by transition().
# Reruns are explicit and use rerun(), so a model cannot silently jump over a
# gate by issuing an ordinary transition request.
_TRANSITIONS: Mapping[ReviewState, frozenset[ReviewState]] = MappingProxyType(
    {
        ReviewState.CREATED: frozenset(
            {ReviewState.INGESTING, ReviewState.DEGRADED, ReviewState.FAILED}
        ),
        ReviewState.INGESTING: frozenset(
            {ReviewState.ASSETS_FROZEN, ReviewState.DEGRADED, ReviewState.FAILED}
        ),
        ReviewState.ASSETS_FROZEN: frozenset(
            {
                ReviewState.RUBRIC_CONFIRMATION,
                ReviewState.DEGRADED,
                ReviewState.FAILED,
            }
        ),
        ReviewState.RUBRIC_CONFIRMATION: frozenset(
            {ReviewState.EVALUATING, ReviewState.DEGRADED, ReviewState.FAILED}
        ),
        ReviewState.EVALUATING: frozenset(
            {
                ReviewState.EVIDENCE_AUDIT,
                ReviewState.DEGRADED,
                ReviewState.FAILED,
            }
        ),
        ReviewState.EVIDENCE_AUDIT: frozenset(
            {
                ReviewState.ARBITRATING,
                ReviewState.DEGRADED,
                ReviewState.FAILED,
            }
        ),
        ReviewState.ARBITRATING: frozenset(
            {
                ReviewState.REPORT_READY,
                ReviewState.DEGRADED,
                ReviewState.FAILED,
                ReviewState.BLOCKED,
                ReviewState.NEEDS_MAJOR_FIXES,
                ReviewState.REVIEWABLE,
            }
        ),
        ReviewState.REPORT_READY: frozenset(
            {ReviewState.FROZEN, ReviewState.NEEDS_MAJOR_FIXES, ReviewState.REVIEWABLE}
        ),
        # Exception states are resumed by rerun() or the BLOCKED evidence gate.
        ReviewState.DEGRADED: frozenset(),
        ReviewState.FAILED: frozenset(),
        ReviewState.BLOCKED: frozenset(),
        ReviewState.NEEDS_MAJOR_FIXES: frozenset(),
        ReviewState.REVIEWABLE: frozenset({ReviewState.FROZEN}),
        ReviewState.FROZEN: frozenset(),
    }
)


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    """One append-only state-machine ledger entry."""

    job_id: str
    event_type: str
    from_state: ReviewState
    to_state: ReviewState
    reason: str
    timestamp: datetime
    input_hash: str | None = None
    evidence_fingerprint: str | None = None
    dependency: str | None = None
    stale_cleared: bool = False
    actor: str = "deterministic-coordinator"
    metadata: Mapping[str, Any] = MappingProxyType({})

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "event_type": self.event_type,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "input_hash": self.input_hash,
            "evidence_fingerprint": self.evidence_fingerprint,
            "dependency": self.dependency,
            "stale_cleared": self.stale_cleared,
            "actor": self.actor,
            "metadata": dict(self.metadata),
        }


class ReviewJobStateMachine:
    """Guard transitions for one review job.

    ``transition`` accepts only protocol transitions.  ``rerun`` is the
    explicit escape hatch for recomputing a previously completed stage, and
    ``mark_stale`` records invalidation caused by changed inputs.
    """

    def __init__(
        self,
        job_id: str,
        *,
        initial_state: ReviewState | str = ReviewState.CREATED,
        timezone: str = "Asia/Shanghai",
    ) -> None:
        if not job_id or not job_id.strip():
            raise ValueError("job_id must be a non-empty string")
        try:
            initial_state = self._coerce_state(initial_state)
        except InvalidTransitionError as exc:
            raise ValueError("initial_state must be a valid ReviewState") from exc
        self.job_id = job_id
        self.state = initial_state
        self._timezone = ZoneInfo(timezone)
        self._events: list[ReviewEvent] = []
        self._stale = False
        self._stale_reason: str | None = None
        self._current_input_hash: str | None = None
        self._rerun_keys: set[str] = set()
        self._stale_dependencies: set[str] = set()
        self._blocked_evidence_ids: frozenset[str] = frozenset()
        # Findings are cumulative so later report/freeze requests cannot hide
        # a fatal or major issue by omitting it from their arguments.
        self._findings: frozenset[str] = frozenset()

    @property
    def events(self) -> tuple[ReviewEvent, ...]:
        """A tuple prevents callers from mutating the event ledger in place."""

        return tuple(self._events)

    @property
    def stale(self) -> bool:
        return self._stale

    @property
    def stale_reason(self) -> str | None:
        return self._stale_reason

    @property
    def current_input_hash(self) -> str | None:
        return self._current_input_hash

    @classmethod
    def from_dict(
        cls,
        snapshot: Mapping[str, Any],
        *,
        timezone: str = "Asia/Shanghai",
    ) -> "ReviewJobStateMachine":
        """Restore a machine from its persisted, JSON-safe snapshot."""

        job_id = str(snapshot.get("job_id") or "")
        machine = cls(job_id, initial_state=snapshot.get("state", ReviewState.CREATED), timezone=timezone)
        machine._stale = bool(snapshot.get("stale", False))
        machine._stale_reason = snapshot.get("stale_reason")
        machine._current_input_hash = snapshot.get("current_input_hash")
        machine._stale_dependencies = set(str(item) for item in snapshot.get("stale_dependencies", []))
        machine._findings = frozenset(str(item) for item in snapshot.get("findings", []))
        machine._blocked_evidence_ids = frozenset(str(item) for item in snapshot.get("blocked_evidence_ids", []))
        for item in snapshot.get("events", []):
            if not isinstance(item, Mapping):
                continue
            try:
                event = ReviewEvent(
                    job_id=str(item.get("job_id") or job_id),
                    event_type=str(item["event_type"]),
                    from_state=machine._coerce_state(item["from_state"]),
                    to_state=machine._coerce_state(item["to_state"]),
                    reason=str(item["reason"]),
                    timestamp=datetime.fromisoformat(str(item["timestamp"])),
                    input_hash=item.get("input_hash"),
                    evidence_fingerprint=item.get("evidence_fingerprint"),
                    dependency=item.get("dependency"),
                    stale_cleared=bool(item.get("stale_cleared", False)),
                    actor=str(item.get("actor", "deterministic-coordinator")),
                    metadata=MappingProxyType(dict(item.get("metadata") or {})),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise InvalidTransitionError("invalid persisted review event") from exc
            machine._events.append(event)
            if event.event_type == "RERUN" and event.metadata.get("idempotency_key"):
                machine._rerun_keys.add(str(event.metadata["idempotency_key"]))
        return machine

    def transition(
        self,
        target: ReviewState,
        *,
        reason: str,
        input_hash: str | None = None,
        evidence_fingerprint: str | None = None,
        new_verified_evidence: bool = False,
        verified_evidence_ids: tuple[str, ...] = (),
        verified_evidence_bundle: tuple[Mapping[str, Any], ...] = (),
        evidence_level: str | None = None,
        findings: tuple[str, ...] = (),
        actor: str = "deterministic-coordinator",
        assets_frozen: bool = False,
        rubric_published: bool = False,
        human_confirmed: bool = False,
        final_confirmed: bool = False,
    ) -> ReviewState:
        """Move to ``target`` after applying deterministic protocol gates.

        Repeating the current transition is idempotent and does not append a
        duplicate event.  A BLOCKED job can resume only through a new,
        verified evidence fingerprint and only at EVIDENCE_AUDIT.
        """

        self._validate_reason(reason)
        self._validate_actor(actor)
        target = self._coerce_state(target)

        if self._current_input_hash and input_hash and input_hash != self._current_input_hash:
            self.mark_stale(
                reason="input snapshot hash changed",
                dependency="input_snapshot",
                input_hash=input_hash,
            )
            self._current_input_hash = input_hash

        if target is self.state:
            return self.state
        if self.state is ReviewState.FROZEN:
            raise InvalidTransitionError("FROZEN is terminal")
        if self._stale:
            raise InvalidTransitionError("stale results require an explicit rerun before advancing")

        if self.state is ReviewState.CREATED and target is ReviewState.ASSETS_FROZEN:
            raise InvalidTransitionError("assets must be frozen after ingestion")
        if target is ReviewState.ASSETS_FROZEN and not assets_frozen:
            raise InvalidTransitionError("ASSETS_FROZEN requires an asset freeze confirmation")
        if (
            self.state is ReviewState.RUBRIC_CONFIRMATION
            and target is ReviewState.EVALUATING
            and (not rubric_published or not human_confirmed)
        ):
            raise InvalidTransitionError(
                "EVALUATING requires a published rubric and human confirmation"
            )
        if target is ReviewState.FROZEN and not final_confirmed:
            raise InvalidTransitionError("FROZEN requires final human confirmation")

        effective_findings = self._findings | frozenset(findings)
        self._validate_result_gate(target, effective_findings)

        if self.state is ReviewState.BLOCKED:
            if target is not ReviewState.EVIDENCE_AUDIT:
                raise InvalidTransitionError(
                    "BLOCKED can resume only at EVIDENCE_AUDIT"
                )
            block_fingerprint = self._last_block_fingerprint()
            computed_fingerprint = self._validate_evidence_bundle(verified_evidence_bundle)
            new_ids = frozenset(str(item["id"]) for item in verified_evidence_bundle)
            if (
                not new_verified_evidence
                or computed_fingerprint == block_fingerprint
                or bool(new_ids & self._blocked_evidence_ids)
            ):
                raise InvalidTransitionError(
                    "BLOCKED requires a new, independently verified evidence fingerprint"
                )

        allowed = _TRANSITIONS[self.state]
        if target not in allowed and not (
            self.state is ReviewState.BLOCKED and target is ReviewState.EVIDENCE_AUDIT
        ):
            raise InvalidTransitionError(
                f"cannot transition from {self.state.value} to {target.value}"
            )

        self._append_event(
            event_type="TRANSITION",
            from_state=self.state,
            to_state=target,
            reason=reason,
            input_hash=input_hash,
            evidence_fingerprint=(
                self._validate_evidence_bundle(verified_evidence_bundle)
                if self.state is ReviewState.BLOCKED
                else evidence_fingerprint
            ),
            stale_cleared=False,
            metadata={"actor": actor},
        )
        self.state = target
        self._findings = effective_findings
        if target is ReviewState.BLOCKED:
            self._blocked_evidence_ids = frozenset(verified_evidence_ids)
        if input_hash is not None:
            self._current_input_hash = input_hash
        return self.state

    def rerun(
        self,
        stage: ReviewState,
        *,
        reason: str,
        input_hash: str | None = None,
        evidence_fingerprint: str | None = None,
        new_verified_evidence: bool = False,
        verified_evidence_ids: tuple[str, ...] = (),
        verified_evidence_bundle: tuple[Mapping[str, Any], ...] = (),
        evidence_level: str | None = None,
        idempotency_key: str | None = None,
        clear_dependency: str | None = None,
        actor: str = "deterministic-coordinator",
    ) -> ReviewState:
        """Explicitly restart a lifecycle stage.

        This operation is intentionally separate from ``transition`` so a
        rerun is visible in the ledger and cannot bypass the BLOCKED gate.
        Rerunning an otherwise valid stage clears its stale marker.
        """

        self._validate_reason(reason)
        self._validate_actor(actor)
        if not idempotency_key or not idempotency_key.strip():
            raise InvalidTransitionError("rerun requires a non-empty idempotency_key")
        stage = self._coerce_state(stage)
        if stage not in LIFECYCLE_STATES:
            raise InvalidTransitionError("rerun target must be a lifecycle stage")
        if self.state is ReviewState.FROZEN:
            raise InvalidTransitionError("FROZEN is terminal")
        if self.state in LIFECYCLE_STATES:
            current_index = LIFECYCLE_STATES.index(self.state)
            target_index = LIFECYCLE_STATES.index(stage)
            if target_index > current_index:
                raise InvalidTransitionError(
                    "rerun cannot skip an unreached predecessor stage"
                )
        elif not any(event.to_state is stage for event in self._events):
            raise InvalidTransitionError(
                "rerun target must have been reached before an exception-state recovery"
            )
        if self.state is ReviewState.BLOCKED:
            block_fingerprint = self._last_block_fingerprint()
            computed_fingerprint = self._validate_evidence_bundle(verified_evidence_bundle)
            new_ids = frozenset(str(item["id"]) for item in verified_evidence_bundle)
            if (
                stage is not ReviewState.EVIDENCE_AUDIT
                or not new_verified_evidence
                or computed_fingerprint == block_fingerprint
                or bool(new_ids & self._blocked_evidence_ids)
            ):
                raise InvalidTransitionError(
                    "BLOCKED rerun requires new verified evidence at EVIDENCE_AUDIT"
                )

        if self._stale_dependencies and clear_dependency not in self._stale_dependencies:
            raise InvalidTransitionError(
                "rerun must name the dependency it clears when stale dependencies exist"
            )

        if idempotency_key in self._rerun_keys:
            return self.state
        self._rerun_keys.add(idempotency_key)

        previous = self.state
        self._append_event(
            event_type="RERUN",
            from_state=previous,
            to_state=stage,
            reason=reason,
            input_hash=input_hash,
            evidence_fingerprint=(
                self._validate_evidence_bundle(verified_evidence_bundle)
                if self.state is ReviewState.BLOCKED
                else evidence_fingerprint
            ),
            stale_cleared=self._stale,
            metadata={"rerun_from": previous.value, "idempotency_key": idempotency_key},
            actor=actor,
        )
        self.state = stage
        if clear_dependency is not None:
            self._stale_dependencies.discard(clear_dependency)
        self._stale = bool(self._stale_dependencies)
        self._stale_reason = None if not self._stale else self._stale_reason
        if input_hash is not None:
            self._current_input_hash = input_hash
        return self.state

    def mark_stale(
        self,
        *,
        reason: str,
        dependency: str,
        input_hash: str | None = None,
    ) -> None:
        """Invalidate downstream results after an input or assumption change."""

        self._validate_reason(reason)
        if not dependency or not dependency.strip():
            raise ValueError("dependency must be a non-empty string")
        self._stale = True
        self._stale_reason = reason
        self._stale_dependencies.add(dependency)
        self._append_event(
            event_type="STALE_MARKED",
            from_state=self.state,
            to_state=self.state,
            reason=reason,
            input_hash=input_hash,
            dependency=dependency,
            metadata={"stale": True},
        )

    def unblock(
        self,
        *,
        reason: str,
        evidence_fingerprint: str,
        input_hash: str | None = None,
        verified_evidence_ids: tuple[str, ...] = (),
        verified_evidence_bundle: tuple[Mapping[str, Any], ...] = (),
        evidence_level: str | None = None,
    ) -> ReviewState:
        """Resume a BLOCKED job after independently verified new evidence."""

        return self.transition(
            ReviewState.EVIDENCE_AUDIT,
            reason=reason,
            input_hash=input_hash,
            evidence_fingerprint=evidence_fingerprint,
            new_verified_evidence=True,
            verified_evidence_ids=verified_evidence_ids,
            verified_evidence_bundle=verified_evidence_bundle,
            evidence_level=evidence_level,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a persistence-friendly snapshot of the machine."""

        return {
            "job_id": self.job_id,
            "state": self.state.value,
            "stale": self.stale,
            "stale_reason": self.stale_reason,
            "current_input_hash": self.current_input_hash,
            "stale_dependencies": sorted(self._stale_dependencies),
            "findings": sorted(self._findings),
            "blocked_evidence_ids": sorted(self._blocked_evidence_ids),
            "events": [event.as_dict() for event in self.events],
        }

    @staticmethod
    def _coerce_state(value: ReviewState | str) -> ReviewState:
        if isinstance(value, ReviewState):
            return value
        try:
            return ReviewState(value)
        except (TypeError, ValueError) as exc:
            raise InvalidTransitionError(f"unknown review state: {value!r}") from exc

    @staticmethod
    def _validate_reason(reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")

    @staticmethod
    def _validate_actor(actor: str) -> None:
        if actor != "deterministic-coordinator":
            raise InvalidTransitionError("only the deterministic coordinator may transition state")

    @staticmethod
    def _validate_result_gate(
        target: ReviewState,
        findings: frozenset[str],
    ) -> None:
        """Apply severity gates to outcomes, reports, and final freezing."""
        if target is ReviewState.BLOCKED and "fatal" not in findings:
            raise InvalidTransitionError("BLOCKED requires at least one fatal finding")
        if target is ReviewState.NEEDS_MAJOR_FIXES and (
            "fatal" in findings or "major" not in findings
        ):
            raise InvalidTransitionError(
                "NEEDS_MAJOR_FIXES requires major findings and no fatal finding"
            )
        if target in {
            ReviewState.REPORT_READY,
            ReviewState.REVIEWABLE,
            ReviewState.FROZEN,
        } and findings & {"fatal", "major"}:
            raise InvalidTransitionError(
                f"{target.value} cannot bypass fatal or major findings"
            )

    def _last_block_fingerprint(self) -> str | None:
        for event in reversed(self._events):
            if event.to_state is ReviewState.BLOCKED:
                return event.evidence_fingerprint
        return None

    @staticmethod
    def _validate_evidence_bundle(bundle: tuple[Mapping[str, Any], ...]) -> str:
        if not bundle:
            raise InvalidTransitionError("verified evidence bundle is required")
        normalized: list[dict[str, Any]] = []
        for item in bundle:
            level = item.get("level")
            if not item.get("id") or not item.get("locator"):
                raise InvalidTransitionError("verified evidence must have id and locator")
            if level not in {"INDEPENDENTLY_VERIFIED", "EXTERNALLY_VALIDATED"}:
                raise InvalidTransitionError("verified evidence must be independently verified")
            normalized.append({"id": item["id"], "level": level, "locator": item["locator"]})
        return hashlib.sha256(
            json.dumps(sorted(normalized, key=lambda value: value["id"]), sort_keys=True).encode()
        ).hexdigest()

    def _append_event(
        self,
        *,
        event_type: str,
        from_state: ReviewState,
        to_state: ReviewState,
        reason: str,
        input_hash: str | None = None,
        evidence_fingerprint: str | None = None,
        dependency: str | None = None,
        stale_cleared: bool = False,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "deterministic-coordinator",
    ) -> ReviewEvent:
        event = ReviewEvent(
            job_id=self.job_id,
            event_type=event_type,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            timestamp=datetime.now(self._timezone),
            input_hash=input_hash,
            evidence_fingerprint=evidence_fingerprint,
            dependency=dependency,
            stale_cleared=stale_cleared,
            actor=actor,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        self._events.append(event)
        return event


__all__ = [
    "LIFECYCLE_STATES",
    "InvalidTransitionError",
    "ReviewEvent",
    "ReviewJobStateMachine",
    "ReviewState",
]
