"""Domain models for imported official scoring rubrics."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .review_protocol import DecisionLedger, RubricProfile


class RubricStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    label: str
    description: str = ""
    weight: float = Field(default=0.0, ge=0, le=1)
    scale_min: float = 0
    scale_max: float = 100
    evidence_required: bool = True

    @field_validator("id", "label")
    @classmethod
    def non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("criterion id and label must be non-empty")
        return value

    @model_validator(mode="after")
    def validate_scale(self) -> "RubricCriterion":
        if self.scale_max <= self.scale_min:
            raise ValueError("scale_max must be greater than scale_min")
        return self


class RubricDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(default_factory=lambda: f"rubric-{uuid4().hex}")
    name: str
    version: str
    source_asset_id: str
    source_hash: str
    criteria: list[RubricCriterion]
    warnings: list[str] = Field(default_factory=list)
    status: RubricStatus = RubricStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None
    decision_ledger_id: str | None = None

    @field_validator("name", "version", "source_asset_id", "source_hash")
    @classmethod
    def non_empty_metadata(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rubric metadata must be non-empty")
        return value

    @model_validator(mode="after")
    def validate_criteria(self) -> "RubricDraft":
        if not self.criteria:
            raise ValueError("rubric requires at least one criterion")
        ids = [criterion.id for criterion in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate criterion ids")
        if self.status is RubricStatus.PUBLISHED:
            if any(criterion.weight <= 0 for criterion in self.criteria):
                raise ValueError("published rubric criteria must have positive weights")
            if abs(sum(criterion.weight for criterion in self.criteria) - 1.0) > 1e-6:
                raise ValueError("published rubric weights must sum to 1")
            if self.published_at is None or self.decision_ledger_id is None:
                raise ValueError("published rubric requires publication metadata")
        return self

    def to_profile(self) -> RubricProfile:
        if self.status is not RubricStatus.PUBLISHED:
            raise ValueError("only published rubric drafts map to RubricProfile")
        return RubricProfile(
            id=self.id,
            version=self.version,
            source_hash=self.source_hash,
            published=True,
            criteria={criterion.id: criterion.weight for criterion in self.criteria},
        )


class RubricPublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric: RubricDraft
    decision: DecisionLedger


def rubric_dict(draft: RubricDraft) -> dict[str, Any]:
    """Return a JSON-ready representation for API and persistence adapters."""
    return draft.model_dump(mode="json")

