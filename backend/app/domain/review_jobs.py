"""Domain contracts for persisted review jobs.

The first implementation only freezes inputs.  Evaluation stages are added in
later phases, so creating a job never invokes a model or executes user code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ReviewJobStatus(str, Enum):
    CREATED = "CREATED"
    INGESTING = "INGESTING"
    ASSETS_FROZEN = "ASSETS_FROZEN"
    RUBRIC_CONFIRMATION = "RUBRIC_CONFIRMATION"
    EVALUATING = "EVALUATING"
    EVIDENCE_AUDIT = "EVIDENCE_AUDIT"
    ARBITRATING = "ARBITRATING"
    REPORT_READY = "REPORT_READY"
    FROZEN = "FROZEN"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_MAJOR_FIXES = "NEEDS_MAJOR_FIXES"
    REVIEWABLE = "REVIEWABLE"


class ReviewJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: f"review-{uuid4().hex}")
    asset_id: str
    rubric_profile_id: str
    asset_sha256: str
    rubric_source_hash: str
    input_snapshot_hash: str
    state: ReviewJobStatus = ReviewJobStatus.CREATED
    options: dict[str, Any] = Field(default_factory=dict)
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
