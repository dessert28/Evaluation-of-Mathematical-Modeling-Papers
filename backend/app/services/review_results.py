"""Persistence service for validated review result snapshots."""

from __future__ import annotations

from typing import Any, Protocol

from backend.app.domain.review_results import ReviewResult
from backend.app.domain.review_protocol import Recommendation


class ReviewResultStore(Protocol):
    def save_result_snapshot(self, review_id: str, snapshot: dict[str, Any]) -> None: ...
    def get_result_snapshot(self, review_id: str) -> dict[str, Any] | None: ...


class ReviewResultError(ValueError):
    pass


class ReviewResultService:
    """Validate, resolve and persist a result without invoking an LLM."""

    def __init__(self, store: ReviewResultStore) -> None:
        self.store = store

    def save(self, result: ReviewResult, *, resolve_claims: bool = True) -> ReviewResult:
        checked = result.resolve_claims() if resolve_claims else result
        old_payload = self.store.get_result_snapshot(result.review_id)
        if old_payload:
            previous = ReviewResult.from_snapshot(old_payload)
            old_meta = previous.metadata or {}
            metadata = dict(checked.metadata or {})
            for field in ('recommendation_originals', 'recommendation_overrides', 'recommendation_edit_history', 'recommendation_archive'):
                if field in old_meta:
                    metadata[field] = old_meta[field]
            protected_ids = set(old_meta.get('recommendation_overrides') or {})
            evidence_ids = {item.id for item in checked.evidence}
            finding_ids = {item.id for item in checked.findings}
            recommendations = {item.id: item for item in checked.recommendations}
            archived = dict(metadata.get('recommendation_archive') or {})
            candidates = {item.id: item for item in previous.recommendations}
            for item_id, payload in archived.items():
                try:
                    candidates.setdefault(item_id, Recommendation.model_validate(payload))
                except ValueError:
                    continue
            for item in candidates.values():
                if item.id not in protected_ids:
                    continue
                if item.finding_id in finding_ids and set(item.evidence_ids).issubset(evidence_ids):
                    recommendations[item.id] = item
                    archived.pop(item.id, None)
                else:
                    # Keep confirmed human text, but do not fabricate links to new evidence.
                    recommendations.pop(item.id, None)
                    archived[item.id] = item.model_dump(mode='json')
            metadata['recommendation_archive'] = archived
            checked = checked.model_copy(update={'recommendations': list(recommendations.values()), 'metadata': metadata})
        self.store.save_result_snapshot(checked.review_id, checked.to_snapshot())
        return checked

    def load(self, review_id: str) -> ReviewResult | None:
        payload = self.store.get_result_snapshot(review_id)
        return ReviewResult.from_snapshot(payload) if payload is not None else None


__all__ = ["ReviewResultError", "ReviewResultService", "ReviewResultStore"]
