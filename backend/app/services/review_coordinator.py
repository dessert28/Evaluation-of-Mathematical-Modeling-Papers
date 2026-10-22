"""Deterministic persistence adapter for the ReviewJob state machine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.services.state_machine import ReviewJobStateMachine, ReviewState


class ReviewCoordinatorError(ValueError):
    """Raised when a persisted review cannot be advanced safely."""


class ReviewJobStore(Protocol):
    def get(self, job_id: str) -> ReviewJob | None: ...
    def update(self, job: ReviewJob) -> ReviewJob: ...


def machine_for_job(job: ReviewJob, *, timezone_name: str = "Asia/Shanghai") -> ReviewJobStateMachine:
    if job.state_snapshot and job.state_snapshot.get("job_id"):
        return ReviewJobStateMachine.from_dict(job.state_snapshot, timezone=timezone_name)
    return ReviewJobStateMachine(job.id, initial_state=job.state.value, timezone=timezone_name)


def _merged_snapshot(previous: dict[str, Any], machine: ReviewJobStateMachine) -> dict[str, Any]:
    """Keep run/result metadata while replacing the deterministic machine view."""
    machine_snapshot = machine.to_dict()
    preserved = {
        key: value
        for key, value in (previous or {}).items()
        if key not in machine_snapshot
    }
    return {**machine_snapshot, **preserved}


class ReviewCoordinator:
    """Apply state transitions and persist the resulting audit snapshot."""

    def __init__(self, store: ReviewJobStore, *, timezone_name: str = "Asia/Shanghai") -> None:
        self.store = store
        self.timezone_name = timezone_name

    def transition(self, job_id: str, target: ReviewState | str, **kwargs: Any) -> ReviewJob:
        job = self.store.get(job_id)
        if job is None:
            raise ReviewCoordinatorError("review job not found")
        machine = machine_for_job(job, timezone_name=self.timezone_name)
        try:
            machine.transition(target, **kwargs)
        except Exception as exc:
            raise ReviewCoordinatorError(str(exc)) from exc
        now = datetime.now(timezone.utc)
        updated = job.model_copy(
            update={
                "state": ReviewJobStatus(machine.state.value),
                "state_snapshot": _merged_snapshot(job.state_snapshot, machine),
                "updated_at": now,
            }
        )
        return self.store.update(updated)

    def rerun(self, job_id: str, stage: ReviewState | str, **kwargs: Any) -> ReviewJob:
        job = self.store.get(job_id)
        if job is None:
            raise ReviewCoordinatorError("review job not found")
        machine = machine_for_job(job, timezone_name=self.timezone_name)
        try:
            machine.rerun(stage, **kwargs)
        except Exception as exc:
            raise ReviewCoordinatorError(str(exc)) from exc
        updated = job.model_copy(
            update={
                "state": ReviewJobStatus(machine.state.value),
                "state_snapshot": _merged_snapshot(job.state_snapshot, machine),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self.store.update(updated)


__all__ = ["ReviewCoordinator", "ReviewCoordinatorError", "machine_for_job"]
