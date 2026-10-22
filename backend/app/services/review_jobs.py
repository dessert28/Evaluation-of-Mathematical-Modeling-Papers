"""Deterministic ReviewJob creation and input snapshot calculation."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from backend.app.domain.review_jobs import ReviewJob
from backend.app.services.state_machine import ReviewJobStateMachine


class ReviewJobError(ValueError):
    pass


class ReviewJobRepository(Protocol):
    def create(self, job: ReviewJob) -> ReviewJob: ...
    def get(self, job_id: str) -> ReviewJob | None: ...
    def list(self) -> list[ReviewJob]: ...


def input_snapshot_hash(*, asset_sha256: str, rubric_source_hash: str, options: dict[str, Any] | None = None) -> str:
    payload = {
        "asset_sha256": asset_sha256.removeprefix("sha256:").lower(),
        "rubric_source_hash": rubric_source_hash.removeprefix("sha256:").lower(),
        "options": options or {},
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_review_job(*, asset: Any, rubric: Any, options: dict[str, Any] | None = None) -> ReviewJob:
    if asset is None:
        raise ReviewJobError("asset not found")
    if getattr(asset.status, "value", asset.status) != "parsed":
        raise ReviewJobError("asset must be parsed before creating a review job")
    if rubric is None:
        raise ReviewJobError("rubric not found")
    if getattr(rubric.status, "value", rubric.status) != "published":
        raise ReviewJobError("published rubric is required")
    opts = dict(options or {})
    asset_hash = str(asset.sha256)
    rubric_hash = str(rubric.source_hash)
    job = ReviewJob(
        asset_id=asset.id,
        rubric_profile_id=rubric.id,
        asset_sha256=asset_hash,
        rubric_source_hash=rubric_hash,
        input_snapshot_hash=input_snapshot_hash(asset_sha256=asset_hash, rubric_source_hash=rubric_hash, options=opts),
        options=opts,
    )
    # Persist an explicit initial snapshot so a newly created job has an
    # auditable state even before its first transition.
    return job.model_copy(update={"state_snapshot": ReviewJobStateMachine(job.id).to_dict()})
