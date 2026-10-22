from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.db import (
    AssetRecord,
    DecisionLedgerRecord,
    DocumentBlockRecord,
    RubricProfileRecord,
    SqlAlchemyAssetStore,
    SqlAlchemyRubricRepository,
    init_db,
    session_scope,
)
from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.domain.rubrics import RubricCriterion, RubricDraft, RubricStatus
from backend.app.services.rubric_importer import RubricImportError, RubricImporter
from backend.app.settings import Settings


def _asset(asset_id: str, *, block_id: str, sha256: str, error_code: str | None = None) -> Asset:
    block = DocumentBlock(
        block_id=block_id,
        asset_id=asset_id,
        block_type="table",
        text="x",
        paragraph=2,
        line_start=4,
        line_end=6,
        block_order=0,
        metadata={"table_index": 1, "cells": [["x"]]},
    )
    parsed = ParsedDocument(status=ParseStatus.FAILED if error_code else ParseStatus.PARSED, blocks=(block,), error_code=error_code, error_message="bad" if error_code else None)
    return Asset(
        id=asset_id,
        filename="paper.md",
        media_type="text/markdown",
        size_bytes=1,
        sha256=sha256,
        status=parsed.status,
        storage_path=Path("paper.md"),
        parsed_document=parsed,
        parse_error=parsed.error_message,
        created_at="2026-10-04T10:20:30+08:00",
    )


def test_asset_store_deduplicates_by_sha_and_preserves_block_owner(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)
    store = SqlAlchemyAssetStore(settings)

    first = store.save(_asset("asset-first", block_id="block-first", sha256="same-sha"))
    duplicate = store.save(_asset("asset-second", block_id="block-second", sha256="same-sha"))

    assert first.id == "asset-first"
    assert duplicate.id == "asset-first"
    assert [block.block_id for block in duplicate.blocks] == ["block-first"]
    with session_scope(settings) as session:
        assert session.query(AssetRecord).count() == 1
        assert session.query(DocumentBlockRecord).count() == 1
        row = session.query(DocumentBlockRecord).one()
        assert row.asset_id == "asset-first"
        assert row.block_metadata == {"table_index": 1, "cells": [["x"]]}


def test_asset_store_round_trip_persists_error_code_and_created_at(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)
    store = SqlAlchemyAssetStore(settings)

    saved = store.save(_asset("asset-error", block_id="block-error", sha256="error-sha", error_code="empty_file"))
    loaded = store.get(saved.id)

    assert loaded is not None
    assert loaded.error_code == "empty_file"
    assert loaded.created_at == "2026-10-04T10:20:30+08:00"
    assert loaded.blocks[0].location["line_start"] == 4
    assert loaded.blocks[0].metadata["table_index"] == 1


def _draft(rubric_id: str = "rubric-1") -> RubricDraft:
    return RubricDraft(
        id=rubric_id,
        name="官方评分",
        version="v1",
        source_asset_id="asset-rubric",
        source_hash="sha256:rubric",
        criteria=[RubricCriterion(id="model", label="模型", description="旧说明", weight=1.0)],
    )


def test_rubric_repository_updates_draft_and_rejects_published_edit(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    init_db(settings)
    SqlAlchemyAssetStore(settings).save(_asset("asset-rubric", block_id="block-rubric", sha256="rubric-source"))
    repository = SqlAlchemyRubricRepository(settings)
    draft = repository.create(_draft())
    edited = draft.model_copy(update={"name": "官方评分新版", "criteria": [RubricCriterion(id="model", label="新模型", description="新说明", weight=1.0)]})

    repository.update(edited)
    loaded = repository.get(draft.id)
    assert loaded is not None
    assert loaded.name == "官方评分新版"
    assert loaded.criteria[0].label == "新模型"

    published, decision = RubricImporter.publish(loaded, confirmed_by="human", rationale="已核对")
    repository.publish(published, decision)
    with pytest.raises(RubricImportError, match="published rubric cannot be edited"):
        repository.update(published.model_copy(update={"name": "禁止修改"}))
    with session_scope(settings) as session:
        profile = session.get(RubricProfileRecord, draft.id)
        assert profile.decision_ledger_id == decision.id
        assert session.get(DecisionLedgerRecord, decision.id).decided_by == "human"
