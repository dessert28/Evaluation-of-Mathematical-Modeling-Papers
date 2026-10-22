from __future__ import annotations

import pytest

from backend.app.domain.rubrics import RubricCriterion, RubricDraft, RubricStatus
from backend.app.services.rubric_importer import RubricImportError, RubricImporter


def test_import_json_normalizes_weights_and_preserves_source_binding() -> None:
    payload = {
        "name": "竞赛官方评分",
        "version": "2026-v1",
        "criteria": [
            {"id": "model", "label": "模型", "description": "模型质量", "weight": 2, "scale_min": 0, "scale_max": 100},
            {"id": "writing", "label": "论文", "description": "表达质量", "weight": 3, "scale_min": 0, "scale_max": 100},
        ],
    }

    draft = RubricImporter.from_json(payload, source_asset_id="asset-1", source_hash="sha256:abc")

    assert isinstance(draft, RubricDraft)
    assert draft.status is RubricStatus.DRAFT
    assert draft.source_asset_id == "asset-1"
    assert draft.source_hash == "sha256:abc"
    assert [criterion.weight for criterion in draft.criteria] == [pytest.approx(0.4), pytest.approx(0.6)]


def test_import_markdown_table_emits_warning_for_missing_weight() -> None:
    markdown = """# 官方评分\n\n| id | label | description | weight | scale_min | scale_max |\n|---|---|---|---|---|---|\n| model | 模型 | 模型质量 |  | 0 | 100 |\n"""

    draft = RubricImporter.from_markdown(markdown, source_asset_id="asset-md", source_hash="sha256:md")

    assert len(draft.criteria) == 1
    assert draft.criteria[0].id == "model"
    assert any("weight" in warning.lower() for warning in draft.warnings)


def test_import_document_blocks_supports_pdf_or_docx_extracted_tables() -> None:
    blocks = [
        {"block_type": "heading", "text": "官方评分标准"},
        {"block_type": "table", "text": "id|label|description|weight|scale_min|scale_max\nmodel|模型|质量|0.7|0|100\nwriting|论文|表达|0.3|0|100"},
    ]

    draft = RubricImporter.from_document_blocks(blocks, source_asset_id="asset-pdf", source_hash="sha256:pdf")

    assert draft.name == "官方评分标准"
    assert [item.id for item in draft.criteria] == ["model", "writing"]
    assert sum(item.weight for item in draft.criteria) == pytest.approx(1.0)


def test_import_docx_tabular_block() -> None:
    blocks = [
        {"block_type": "heading", "text": "DOCX 评分"},
        {"block_type": "table", "text": "id\tlabel\tdescription\tweight\tscale_min\tscale_max\nmodel\t模型\t质量\t1\t0\t100"},
    ]
    draft = RubricImporter.from_document_blocks(blocks, source_asset_id="asset-docx", source_hash="sha256:docx")
    assert draft.name == "DOCX 评分"
    assert draft.criteria[0].id == "model"


def test_duplicate_criteria_are_rejected() -> None:
    payload = {
        "name": "重复项",
        "version": "v1",
        "criteria": [
            {"id": "model", "label": "模型", "weight": 0.5},
            {"id": "model", "label": "模型重复", "weight": 0.5},
        ],
    }

    with pytest.raises(RubricImportError, match="duplicate"):
        RubricImporter.from_json(payload, source_asset_id="asset-1", source_hash="sha256:x")


def test_invalid_scale_and_empty_criterion_are_rejected() -> None:
    payload = {
        "name": "非法量表",
        "version": "v1",
        "criteria": [
            {"id": "", "label": "", "weight": 1, "scale_min": 10, "scale_max": 0},
        ],
    }

    with pytest.raises(RubricImportError):
        RubricImporter.from_json(payload, source_asset_id="asset-1", source_hash="sha256:x")


def test_publish_requires_human_confirmation_and_is_immutable() -> None:
    draft = RubricImporter.from_json(
        {"name": "官方评分", "version": "v1", "criteria": [{"id": "model", "label": "模型", "weight": 1}]},
        source_asset_id="asset-1",
        source_hash="sha256:x",
    )

    with pytest.raises(RubricImportError, match="human"):
        RubricImporter.publish(draft, confirmed_by="agent", rationale="自动发布")

    published, decision = RubricImporter.publish(draft, confirmed_by="human", rationale="已核对")
    assert published.status is RubricStatus.PUBLISHED
    assert decision.decided_by == "human"
    assert decision.subject_id == published.id

    with pytest.raises(RubricImportError, match="immutable"):
        RubricImporter.publish(published, confirmed_by="human", rationale="再次发布")


def test_duplicate_name_and_version_is_rejected() -> None:
    draft = RubricImporter.from_json(
        {"name": "官方评分", "version": "v1", "criteria": [{"id": "model", "label": "模型", "weight": 1}]},
        source_asset_id="asset-1",
        source_hash="sha256:x",
    )
    with pytest.raises(RubricImportError):
        RubricImporter.ensure_unique_version(draft, [("官方评分", "v1")])
