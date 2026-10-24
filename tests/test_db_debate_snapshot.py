"""Tests for the debate_snapshot persistence column (v0.1 iteration 2a)."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from backend.app.db import ReviewJobRecord, SqlAlchemyReviewJobRepository, init_db, session_scope
from backend.app.services.review_results import ReviewResultError
from backend.app.settings import Settings


def _new_repo(tmp_path: Path, settings: Settings | None = None) -> tuple[SqlAlchemyReviewJobRepository, Settings]:
    settings = settings or Settings(data_dir=tmp_path)
    init_db(settings)
    return SqlAlchemyReviewJobRepository(settings), settings


def _insert_job(settings: Settings, job_id: str = "job-1") -> None:
    with session_scope(settings) as session:
        session.add(ReviewJobRecord(id=job_id, state="CREATED"))


def test_save_and_get_debate_snapshot_round_trip(tmp_path: Path) -> None:
    repo, settings = _new_repo(tmp_path)
    _insert_job(settings)

    snapshot = {
        "review_id": "job-1",
        "status": "COMPLETED",
        "rounds": [{"round_number": 0}],
        "outcome": {"converged": True, "stop_reason": "converged"},
    }
    repo.save_debate_snapshot("job-1", snapshot)
    assert repo.get_debate_snapshot("job-1") == snapshot

    replacement = {"review_id": "job-1", "status": "FAILED", "last_error": {"code": "debate_failed"}}
    repo.save_debate_snapshot("job-1", replacement)
    assert repo.get_debate_snapshot("job-1") == replacement


def test_get_missing_review_returns_none_and_save_raises(tmp_path: Path) -> None:
    repo, _ = _new_repo(tmp_path)
    assert repo.get_debate_snapshot("missing") is None
    with pytest.raises(ReviewResultError):
        repo.save_debate_snapshot("missing", {"status": "RUNNING"})


def test_create_all_includes_debate_snapshot_column(tmp_path: Path) -> None:
    _, settings = _new_repo(tmp_path)
    with sqlite3.connect(settings.database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(review_jobs)")}
    assert "debate_snapshot" in columns


def test_legacy_review_jobs_table_gains_debate_snapshot_column(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE review_jobs (
                id VARCHAR(128) PRIMARY KEY,
                asset_id VARCHAR(128),
                rubric_profile_id VARCHAR(128),
                state VARCHAR(64) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO review_jobs VALUES (?, ?, ?, ?, ?, ?)",
            (
                "legacy-job",
                None,
                None,
                "CREATED",
                "2026-01-01 00:00:00.000000+00:00",
                "2026-01-01 00:00:00.000000+00:00",
            ),
        )

    settings = Settings(data_dir=tmp_path)
    init_db(settings)

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(review_jobs)")}
    assert "debate_snapshot" in columns

    repo = SqlAlchemyReviewJobRepository(settings)
    snapshot = {"status": "RUNNING", "rounds": []}
    repo.save_debate_snapshot("legacy-job", snapshot)
    assert repo.get_debate_snapshot("legacy-job") == snapshot
