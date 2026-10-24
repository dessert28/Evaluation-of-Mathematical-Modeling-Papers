"""API tests for the multi-agent debate endpoints (v0.1, iteration 3).

The debate layer is faked behind ``app.state.debate_runner``; no real model or
database is touched.  The app is built from ``create_review_router`` exactly
like ``test_review_run_api.py`` does for the review runner.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.reviews import DebateRunRequest, ReviewRunRequest, create_review_router
from backend.app.domain.debate import DebateError


SNAPSHOT = {
    "review_id": "review-1",
    "status": "COMPLETED",
    "stale": False,
    "rounds": [
        {
            "round_number": 0,
            "speaker_order": ["expert-1", "expert-2"],
            "status": "COMPLETED",
            "opinions": [{"id": "op-0-expert-0-0"}],
            "messages": [],
        },
        {
            "round_number": 1,
            "speaker_order": ["expert-1", "expert-2"],
            "status": "COMPLETED",
            "opinions": [],
            "messages": [{"id": "msg-1-expert-0-0"}],
        },
    ],
    "outcome": {"accepted": True},
}


class DebateRunner:
    """Fake ``DebateRunManager``: canned snapshot, recorded submissions."""

    def __init__(self, snapshot=None, submit_error=None):
        self.snapshot = snapshot
        self.submit_error = submit_error
        self.submits = []

    def get(self, review_id):
        return self.snapshot

    def submit(self, review_id, *, options=None, idempotency_key=None):
        self.submits.append((review_id, dict(options or {}), idempotency_key))
        if self.submit_error is not None:
            raise self.submit_error
        return {"review_id": review_id, "debate_status": "QUEUED", "idempotency_key": idempotency_key}


class ReviewRunner:
    """Fake review runner whose ``start_run`` accepts the new ``debate`` kwarg."""

    def __init__(self):
        self.calls = []

    def start_run(self, review_id, *, stage_ids=None, start_stage=None, idempotency_key=None, debate=None):
        self.calls.append((review_id, debate, idempotency_key))
        return {"review_id": review_id, "run_status": "QUEUED"}


def _app(debate_runner=None, review_runner=None):
    app = FastAPI()
    app.state.debate_runner = debate_runner
    if review_runner is not None:
        app.state.review_runner = review_runner
    app.include_router(create_review_router())
    return app


def test_get_debate_without_record_returns_404_debate_not_found():
    client = TestClient(_app(DebateRunner(snapshot=None)))
    response = client.get("/api/v1/reviews/review-1/debate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "debate_not_found"


def test_get_debate_returns_persisted_snapshot():
    client = TestClient(_app(DebateRunner(snapshot=SNAPSHOT)))
    response = client.get("/api/v1/reviews/review-1/debate")
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["rounds"][1]["messages"][0]["id"] == "msg-1-expert-0-0"


def test_debate_endpoints_return_503_when_runner_not_configured():
    client = TestClient(_app(None))
    response = client.get("/api/v1/reviews/review-1/debate")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "debate_unavailable"
    response = client.post("/api/v1/reviews/review-1/debate/run", json={"idempotency_key": "k1"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "debate_unavailable"
    response = client.get("/api/v1/reviews/review-1/debate/rounds/0")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "debate_unavailable"


def test_debate_run_requires_idempotency_key():
    client = TestClient(_app(DebateRunner()))
    response = client.post("/api/v1/reviews/review-1/debate/run", json={})
    assert response.status_code == 422


def test_debate_run_rejects_max_rounds_out_of_bounds():
    client = TestClient(_app(DebateRunner()))
    response = client.post(
        "/api/v1/reviews/review-1/debate/run",
        json={"idempotency_key": "k1", "max_rounds": 6},
    )
    assert response.status_code == 422


def test_debate_run_rejects_unknown_fields():
    client = TestClient(_app(DebateRunner()))
    response = client.post(
        "/api/v1/reviews/review-1/debate/run",
        json={"idempotency_key": "k1", "temperature": 0.2},
    )
    assert response.status_code == 422


def test_debate_run_returns_202_and_payload_and_forwards_options():
    runner = DebateRunner()
    client = TestClient(_app(runner))
    response = client.post(
        "/api/v1/reviews/review-1/debate/run",
        json={"idempotency_key": "k1", "max_rounds": 3, "expert_ids": ["modeling", "code"]},
    )
    assert response.status_code == 202
    assert response.json() == {"review_id": "review-1", "debate_status": "QUEUED", "idempotency_key": "k1"}
    assert runner.submits == [("review-1", {"max_rounds": 3, "expert_ids": ["modeling", "code"]}, "k1")]


def test_debate_run_without_optional_fields_omits_them_from_options():
    runner = DebateRunner()
    client = TestClient(_app(runner))
    response = client.post("/api/v1/reviews/review-1/debate/run", json={"idempotency_key": "k2"})
    assert response.status_code == 202
    assert runner.submits == [("review-1", {}, "k2")]


def test_debate_run_active_conflict_returns_409():
    runner = DebateRunner(submit_error=DebateError("debate_already_active", "辩论已在进行中", status_code=409))
    client = TestClient(_app(runner))
    response = client.post("/api/v1/reviews/review-1/debate/run", json={"idempotency_key": "k1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "debate_already_active"
    assert response.json()["error"]["message"] == "辩论已在进行中"


def test_debate_round_hit_returns_that_round():
    client = TestClient(_app(DebateRunner(snapshot=SNAPSHOT)))
    response = client.get("/api/v1/reviews/review-1/debate/rounds/0")
    assert response.status_code == 200
    assert response.json()["round_number"] == 0
    assert response.json()["opinions"][0]["id"] == "op-0-expert-0-0"


def test_debate_round_out_of_range_returns_404_invalid_round():
    client = TestClient(_app(DebateRunner(snapshot=SNAPSHOT)))
    response = client.get("/api/v1/reviews/review-1/debate/rounds/2")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_round"
    response = client.get("/api/v1/reviews/review-1/debate/rounds/-1")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_round"


def test_debate_round_without_record_returns_404_debate_not_found():
    client = TestClient(_app(DebateRunner(snapshot=None)))
    response = client.get("/api/v1/reviews/review-1/debate/rounds/0")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "debate_not_found"


def test_review_run_request_accepts_debate_options_and_defaults_to_none():
    parsed = ReviewRunRequest(
        idempotency_key="k1",
        debate={"enabled": True, "max_rounds": 3, "expert_ids": ["modeling", "code"]},
    )
    assert parsed.debate == {"enabled": True, "max_rounds": 3, "expert_ids": ["modeling", "code"]}
    assert ReviewRunRequest(idempotency_key="k1").debate is None
    # extra="forbid" still applies to the new model
    with pytest.raises(ValueError):
        DebateRunRequest(idempotency_key="k1", max_rounds=1, unknown=1)


def test_review_run_forwards_debate_options_to_runner():
    runner = ReviewRunner()
    client = TestClient(_app(review_runner=runner))
    response = client.post(
        "/api/v1/reviews/review-1/run",
        json={"idempotency_key": "run-1", "debate": {"enabled": True, "max_rounds": 3}},
    )
    assert response.status_code == 202
    assert runner.calls == [("review-1", {"enabled": True, "max_rounds": 3}, "run-1")]


def test_review_run_without_debate_keeps_old_runner_contract():
    runner = ReviewRunner()
    client = TestClient(_app(review_runner=runner))
    response = client.post("/api/v1/reviews/review-1/run", json={"idempotency_key": "run-1"})
    assert response.status_code == 202
    assert runner.calls == [("review-1", None, "run-1")]
