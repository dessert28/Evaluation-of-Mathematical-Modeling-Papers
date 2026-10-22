from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import IntegrityError

from backend.app.db import (
    AssetRecord,
    DocumentBlockRecord,
    RubricCriterionRecord,
    RubricProfileRecord,
    ReviewJobRecord,
    init_db,
    session_scope,
)
from backend.app.settings import Settings


def test_create_all_and_round_trip_records(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)

    with session_scope(settings) as session:
        session.add(
            AssetRecord(
                id="asset-1",
                filename="paper.md",
                media_type="text/markdown",
                size_bytes=10,
                sha256="sha256-asset-1",
                status="parsed",
                storage_path=str(tmp_path / "assets" / "asset-1" / "paper.md"),
            )
        )
        session.flush()
        session.add(
            DocumentBlockRecord(
                id="block-1",
                asset_id="asset-1",
                block_type="paragraph",
                text="模型目标",
                paragraph=1,
                line_start=1,
                line_end=1,
                block_order=0,
            )
        )
        session.add(
            RubricProfileRecord(
                id="rubric-1",
                name="官方量表",
                version="2026-v1",
                source_hash="sha256-rubric-1",
                status="draft",
                warnings=[],
            )
        )
        session.flush()
        session.add(
            RubricCriterionRecord(
                id="criterion-row-1",
                rubric_id="rubric-1",
                criterion_id="criterion-1",
                label="创新性",
                description="创新程度",
                weight=1.0,
                scale_min=0.0,
                scale_max=100.0,
                evidence_required=True,
            )
        )
        session.add(
            ReviewJobRecord(
                id="job-1",
                asset_id="asset-1",
                rubric_profile_id="rubric-1",
                state="CREATED",
            )
        )

    with session_scope(settings) as session:
        assert session.get(AssetRecord, "asset-1").filename == "paper.md"
        assert session.get(DocumentBlockRecord, "block-1").text == "模型目标"
        assert session.get(RubricProfileRecord, "rubric-1").warnings == []
        assert session.get(RubricCriterionRecord, "criterion-row-1").weight == 1.0
        assert session.get(ReviewJobRecord, "job-1").state == "CREATED"


def test_init_db_upgrades_legacy_asset_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE assets (
                id VARCHAR(128) PRIMARY KEY,
                filename VARCHAR(512) NOT NULL,
                media_type VARCHAR(255) NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL,
                storage_path TEXT NOT NULL,
                parse_error TEXT,
                warnings JSON NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE document_blocks (
                id VARCHAR(160) PRIMARY KEY,
                asset_id VARCHAR(128) NOT NULL,
                block_type VARCHAR(64) NOT NULL,
                text TEXT NOT NULL,
                page INTEGER,
                paragraph INTEGER,
                line_start INTEGER,
                line_end INTEGER,
                block_order INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-asset",
                "paper.md",
                "text/markdown",
                10,
                "sha256-legacy",
                "parsed",
                str(tmp_path / "paper.md"),
                None,
                "[]",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT INTO document_blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-block", "legacy-asset", "paragraph", "Evidence", 1, 1, 1, 1, 0),
        )

    settings = Settings(data_dir=tmp_path)
    init_db(settings)

    with sqlite3.connect(db_path) as connection:
        asset_columns = {row[1] for row in connection.execute("PRAGMA table_info(assets)")}
        block_columns = {row[1] for row in connection.execute("PRAGMA table_info(document_blocks)")}
    assert "error_code" in asset_columns
    assert "metadata" in block_columns

    with session_scope(settings) as session:
        asset = session.get(AssetRecord, "legacy-asset")
        block = session.get(DocumentBlockRecord, "legacy-block")
        assert asset is not None and asset.error_code is None
        assert block is not None and block.block_metadata == {}


def test_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)

    with pytest.raises(RuntimeError):
        with session_scope(settings) as session:
            session.add(
                AssetRecord(
                    id="asset-rollback",
                    filename="broken.md",
                    media_type="text/markdown",
                    size_bytes=1,
                    sha256="sha256-rollback",
                    status="failed",
                    storage_path="/tmp/broken.md",
                )
            )
            raise RuntimeError("force rollback")

    with session_scope(settings) as session:
        assert session.get(AssetRecord, "asset-rollback") is None


def test_asset_sha256_is_unique(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)

    with pytest.raises(IntegrityError):
        with session_scope(settings) as session:
            session.add(
                AssetRecord(
                    id="asset-a",
                    filename="a.md",
                    media_type="text/markdown",
                    size_bytes=1,
                    sha256="same-hash",
                    status="parsed",
                    storage_path="a.md",
                )
            )
            session.flush()
            session.add(
                AssetRecord(
                    id="asset-b",
                    filename="b.md",
                    media_type="text/markdown",
                    size_bytes=1,
                    sha256="same-hash",
                    status="parsed",
                    storage_path="b.md",
                )
            )
            session.flush()

    with session_scope(settings) as session:
        assert session.get(AssetRecord, "asset-a") is None
        assert session.get(AssetRecord, "asset-b") is None
