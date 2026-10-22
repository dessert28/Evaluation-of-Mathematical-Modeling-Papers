from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.reviews import create_review_router


class _Runner:
    def __init__(self):
        self.calls = []
        self.progress_value = {"review_id": "review-1", "run_status": "QUEUED", "completed_stages": []}

    def start_run(self, review_id, *, stage_ids=None, start_stage=None, idempotency_key=None):
        self.calls.append((review_id, stage_ids, start_stage, idempotency_key))
        return self.progress_value

    def get_progress(self, review_id):
        return {**self.progress_value, "review_id": review_id, "run_status": "RUNNING", "current_stage": "assumptions"}

    def start_stage_run(self, review_id, stage_id, *, reason=None, idempotency_key=None):
        self.calls.append((review_id, [stage_id], None, idempotency_key))
        return {"review_id": review_id, "run_status": "QUEUED", "current_stage": stage_id}


def _app(runner):
    app = FastAPI()
    app.state.review_runner = runner
    app.include_router(create_review_router())
    return app


def test_start_review_run_returns_202_and_forwards_options():
    runner = _Runner()
    response = TestClient(_app(runner)).post(
        "/api/v1/reviews/review-1/run",
        json={"idempotency_key": "run-1", "stage_ids": ["problem_identification"], "start_stage": "problem_identification"},
    )
    assert response.status_code == 202
    assert response.json()["run_status"] == "QUEUED"
    assert runner.calls == [("review-1", ["problem_identification"], "problem_identification", "run-1")]


def test_progress_returns_persisted_runner_snapshot():
    response = TestClient(_app(_Runner())).get("/api/v1/reviews/review-1/progress")
    assert response.status_code == 200
    assert response.json()["current_stage"] == "assumptions"


def test_start_single_stage_run_returns_202():
    runner = _Runner()
    response = TestClient(_app(runner)).post(
        "/api/v1/reviews/review-1/stages/solving/run",
        json={"idempotency_key": "stage-1", "reason": "retry"},
    )
    assert response.status_code == 202
    assert response.json()["current_stage"] == "solving"


class _ConflictRunner(_Runner):
    def start_run(self, *args, **kwargs):
        error = RuntimeError("review already has an active run")
        error.code = "run_already_active"
        raise error


def test_duplicate_active_run_returns_conflict_error():
    response = TestClient(_app(_ConflictRunner())).post(
        "/api/v1/reviews/review-1/run", json={"idempotency_key": "run-1"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run_already_active"
