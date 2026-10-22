from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.domain.review_protocol import FindingSeverity
from backend.app.domain.review_results import ReviewResult


class RecommendationEditError(ValueError):
    def __init__(self, message: str, code: str = "recommendation_edit_failed"):
        super().__init__(message)
        self.code = code


class RecommendationEditService:
    def __init__(self, store: Any):
        self.store = store

    def update(self, review_id: str, recommendation_id: str, *, action: str, acceptance: str, priority: str, owner: str | None, decided_by: str, rationale: str) -> ReviewResult:
        result_payload = self.store.get_result_snapshot(review_id)
        if result_payload is None:
            raise RecommendationEditError("review result not found", "result_not_found")
        result = ReviewResult.from_snapshot(result_payload)
        recommendation = next((item for item in result.recommendations if item.id == recommendation_id), None)
        if recommendation is None:
            raise RecommendationEditError("recommendation not found", "recommendation_not_found")
        try:
            severity = FindingSeverity(priority)
        except ValueError as exc:
            raise RecommendationEditError("invalid recommendation priority", "invalid_recommendation_priority") from exc
        updated = recommendation.model_copy(update={"action": action, "acceptance": acceptance, "priority": severity, "owner": owner})
        recommendations = [updated if item.id == recommendation_id else item for item in result.recommendations]
        metadata = dict(result.metadata or {})
        originals = dict(metadata.get('recommendation_originals') or {})
        originals.setdefault(recommendation_id, recommendation.model_dump(mode='json'))
        metadata['recommendation_originals'] = originals
        overrides = dict(metadata.get("recommendation_overrides") or {})
        overrides[recommendation_id] = {"decided_by": decided_by, "rationale": rationale, "decided_at": datetime.now(timezone.utc).isoformat()}
        metadata["recommendation_overrides"] = overrides
        history = list(metadata.get('recommendation_edit_history') or [])
        history.append({'recommendation_id': recommendation_id, **overrides[recommendation_id],
                        'before': recommendation.model_dump(mode='json'), 'after': updated.model_dump(mode='json')})
        metadata['recommendation_edit_history'] = history
        saved = result.model_copy(update={"recommendations": recommendations, "metadata": metadata})
        self.store.save_result_snapshot(review_id, saved.to_snapshot())
        self.store.save_decision({"id": f"decision-{uuid4().hex}", "subject_type": "recommendation", "subject_id": recommendation_id, "decided_by": decided_by, "decision": "edit", "rationale": rationale, "evidence_refs": list(recommendation.evidence_ids), "decided_at": datetime.now(timezone.utc), "supersedes": None})
        return saved
