from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings


def test_health_reports_ok_and_timezone(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, app_timezone="Asia/Shanghai"))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "timezone": "Asia/Shanghai"}


def test_health_uses_configured_timezone(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, app_timezone="UTC"))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["timezone"] == "UTC"
