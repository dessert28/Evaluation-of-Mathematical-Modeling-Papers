from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.domain.review_protocol import Finding, FindingSeverity, Recommendation
from backend.app.domain.review_results import ReviewResult
from backend.app.services.recommendation_edits import RecommendationEditService


def test_model_config_is_encrypted_and_never_echoed(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert (tmp_path / ".model-config.key").exists()
    response = client.post(
        "/api/v1/model-config",
        json={"provider": "custom", "base_url": "https://example.test/v1", "api_key": "top-secret", "model": "demo", "is_active": True},
    )
    assert response.status_code == 201
    assert "top-secret" not in response.text
    assert "top-secret" not in (tmp_path / "app.db").read_bytes().decode("latin1")
    listed = client.get("/api/v1/model-config")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["api_key_configured"] is True
    assert "top-secret" not in listed.text


def test_missing_model_key_locks_existing_config(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    created = client.post(
        "/api/v1/model-config",
        json={"provider": "custom", "base_url": "https://example.test/v1", "api_key": "secret", "model": "demo", "is_active": True},
    )
    assert created.status_code == 201
    (tmp_path / ".model-config.key").unlink()
    restarted = TestClient(create_app(Settings(data_dir=tmp_path)))
    locked = restarted.post(
        "/api/v1/model-config",
        json={"provider": "custom", "base_url": "https://example.test/v1", "api_key": "new", "model": "demo", "is_active": True},
    )
    assert locked.status_code == 503
    assert locked.json()["error"]["code"] == "model_config_locked"


def test_assets_list_and_report_not_found_are_safe(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    uploaded = client.post("/api/v1/assets", files={"file": ("paper.md", b"# Paper\n\nEvidence", "text/markdown")})
    assert uploaded.status_code == 201
    listed = client.get("/api/v1/assets")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == uploaded.json()["id"]
    missing = client.get("/api/v1/reviews/missing/report?format=md")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "report_not_found"


def test_native_app_serves_frontend_entry(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.get("/")
    assert response.status_code == 200
    assert "数学建模论文评审智能体" in response.text


def test_recommendation_edit_preserves_override_and_decision() -> None:
    class Store:
        def __init__(self):
            self.snapshot = ReviewResult(
                review_id="review-1",
                findings=[Finding(id="finding-1", title="需要补充验证", severity=FindingSeverity.MAJOR)],
                recommendations=[Recommendation(id="recommendation-1", finding_id="finding-1", action="补充实验", acceptance="新增敏感性分析")],
            ).to_snapshot()
            self.decisions = []

        def get_result_snapshot(self, review_id):
            return self.snapshot if review_id == "review-1" else None

        def save_result_snapshot(self, review_id, snapshot):
            self.snapshot = snapshot

        def save_decision(self, decision):
            self.decisions.append(decision)

    store = Store()
    saved = RecommendationEditService(store).update(
        "review-1", "recommendation-1", action="补充独立验证", acceptance="重跑并记录误差", priority="major", owner="作者", decided_by="human", rationale="已确认",
    )
    assert saved.recommendations[0].action == "补充独立验证"
    assert saved.metadata["recommendation_overrides"]["recommendation-1"]["decided_by"] == "human"
    assert len(store.decisions) == 1
