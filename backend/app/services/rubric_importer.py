"""Deterministic import and publication helpers for official rubrics."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from backend.app.domain.rubrics import (
    RubricCriterion,
    RubricDraft,
    RubricPublishResult,
    RubricStatus,
)
from backend.app.domain.review_protocol import DecisionLedger


class RubricImportError(ValueError):
    """Raised when an imported rubric cannot satisfy the draft contract."""


def _text(value: Any, default: str = "") -> str:
    return default if value is None else str(value).strip()


def _number(value: Any, *, default: float | None = None) -> float | None:
    if value is None or _text(value) == "":
        return default
    try:
        return float(str(value).strip().replace("%", ""))
    except (TypeError, ValueError) as exc:
        raise RubricImportError(f"invalid numeric value: {value!r}") from exc


def _parse_criterion(item: Mapping[str, Any], index: int) -> tuple[dict[str, Any], bool]:
    criterion_id = _text(item.get("id", item.get("criterion_id", item.get("key"))))
    label = _text(item.get("label", item.get("name", item.get("criterion"))))
    if not criterion_id:
        raise RubricImportError(f"criterion {index} is missing id")
    if not label:
        raise RubricImportError(f"criterion {criterion_id!r} is missing label")
    weight = _number(item.get("weight"), default=None)
    missing_weight = weight is None
    if missing_weight:
        weight = 0.0
    scale_min = _number(item.get("scale_min", item.get("min", 0)), default=0)
    scale_max = _number(item.get("scale_max", item.get("max", 100)), default=100)
    payload = {
        "id": criterion_id,
        "label": label,
        "description": _text(item.get("description", item.get("details", ""))),
        "weight": weight,
        "scale_min": scale_min,
        "scale_max": scale_max,
        "evidence_required": bool(item.get("evidence_required", True)),
    }
    return payload, missing_weight


def _build_draft(
    payload: Mapping[str, Any],
    *,
    source_asset_id: str,
    source_hash: str,
    default_name: str = "官方评分标准",
    extra_warnings: Iterable[str] = (),
) -> RubricDraft:
    name = _text(payload.get("name"), default_name)
    version = _text(payload.get("version"), "unversioned")
    raw_criteria = payload.get("criteria", payload.get("items"))
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise RubricImportError("rubric criteria must be a non-empty list")

    criteria_payload: list[dict[str, Any]] = []
    warnings = list(extra_warnings)
    missing_weight_ids: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_criteria, 1):
        if not isinstance(raw, Mapping):
            raise RubricImportError(f"criterion {index} must be an object")
        item, missing_weight = _parse_criterion(raw, index)
        if item["id"] in seen:
            raise RubricImportError(f"duplicate criterion id: {item['id']}")
        seen.add(item["id"])
        criteria_payload.append(item)
        if missing_weight:
            missing_weight_ids.append(item["id"])
    if missing_weight_ids:
        warnings.append("missing weight for criteria: " + ", ".join(missing_weight_ids))

    total = sum(float(item["weight"]) for item in criteria_payload)
    if total > 0 and not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-9):
        for item in criteria_payload:
            item["weight"] = round(float(item["weight"]) / total, 12)
        warnings.append(f"weights normalized from total {total:g} to 1")
    elif total <= 0:
        warnings.append("weights total is zero; publication requires positive weights summing to 1")

    try:
        criteria = [RubricCriterion.model_validate(item) for item in criteria_payload]
        return RubricDraft(
            name=name,
            version=version,
            source_asset_id=source_asset_id,
            source_hash=source_hash,
            criteria=criteria,
            warnings=warnings,
        )
    except (ValidationError, ValueError) as exc:
        raise RubricImportError(str(exc)) from exc


def _split_markdown_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [part.strip().replace("\\|", "|") for part in line.split("|")]


def _markdown_table_rows(markdown: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or "|" not in lines[index + 1]:
            continue
        headers = _split_markdown_row(lines[index])
        separator = _split_markdown_row(lines[index + 1])
        if headers and all(set(value.replace(":", "").strip()) <= {"-"} for value in separator):
            rows: list[list[str]] = []
            for row in lines[index + 2 :]:
                if "|" in row:
                    rows.append(_split_markdown_row(row))
            return headers, rows
    raise RubricImportError("no markdown rubric table found")


def _pipe_table_rows(markdown: str) -> tuple[list[str], list[list[str]]]:
    """Accept tables emitted by PDF/DOCX extractors without a separator row."""
    lines = [line.strip() for line in markdown.splitlines() if line.strip() and "|" in line]
    if len(lines) < 2:
        raise RubricImportError("no table rows found")
    headers = _split_markdown_row(lines[0])
    rows = [_split_markdown_row(line) for line in lines[1:]]
    return headers, rows


def _tab_table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Accept DOCX table extraction where cells are separated by tabs."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows = [[cell.strip() for cell in line.split("\t")] for line in lines]
    if len(rows) < 2 or len(rows[0]) < 2:
        raise RubricImportError("no tabular rows found")
    width = len(rows[0])
    if any(len(row) != width for row in rows[1:]):
        raise RubricImportError("inconsistent tabular row width")
    return rows[0], rows[1:]


def _rows_to_payload(headers: list[str], rows: list[list[str]]) -> dict[str, Any]:
    normalized_headers = [header.strip().lower().replace(" ", "_") for header in headers]
    criteria: list[dict[str, Any]] = []
    for row in rows:
        if not any(row):
            continue
        values = row + [""] * (len(normalized_headers) - len(row))
        criteria.append(dict(zip(normalized_headers, values)))
    return {"name": "官方评分标准", "version": "unversioned", "criteria": criteria}


class RubricImporter:
    @staticmethod
    def from_json(
        payload: str | Mapping[str, Any], *, source_asset_id: str, source_hash: str
    ) -> RubricDraft:
        try:
            data = json.loads(payload) if isinstance(payload, str) else dict(payload)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RubricImportError("invalid rubric JSON") from exc
        if not isinstance(data, Mapping):
            raise RubricImportError("rubric JSON must be an object")
        return _build_draft(data, source_asset_id=source_asset_id, source_hash=source_hash)

    @staticmethod
    def from_markdown(
        markdown: str, *, source_asset_id: str, source_hash: str
    ) -> RubricDraft:
        headers, rows = _markdown_table_rows(markdown)
        return _build_draft(
            _rows_to_payload(headers, rows),
            source_asset_id=source_asset_id,
            source_hash=source_hash,
        )

    @staticmethod
    def from_document_blocks(
        blocks: Iterable[Mapping[str, Any]], *, source_asset_id: str, source_hash: str
    ) -> RubricDraft:
        block_list = list(blocks)
        heading = next(
            (_text(block.get("text")) for block in block_list if block.get("block_type") in {"heading", "title"} and _text(block.get("text"))),
            "官方评分标准",
        )
        table_lines = [
            _text(block.get("text"))
            for block in block_list
            if "|" in _text(block.get("text")) or block.get("block_type") == "table"
        ]
        table = "\n".join(line for line in table_lines if line) or None
        if table is None:
            raise RubricImportError("no table block found in rubric document")
        try:
            headers, rows = _markdown_table_rows(table)
        except RubricImportError:
            try:
                headers, rows = _pipe_table_rows(table)
            except RubricImportError:
                headers, rows = _tab_table_rows(table)
        payload = _rows_to_payload(headers, rows)
        payload["name"] = heading
        return _build_draft(payload, source_asset_id=source_asset_id, source_hash=source_hash)

    @staticmethod
    def ensure_unique_version(draft: RubricDraft, existing: Iterable[Any]) -> None:
        for item in existing:
            if isinstance(item, tuple):
                name, version = item[0], item[1]
            else:
                name, version = getattr(item, "name", None), getattr(item, "version", None)
            if name == draft.name and version == draft.version:
                raise RubricImportError(f"rubric name and version already exist: {draft.name} {draft.version}")

    @staticmethod
    def publish(
        draft: RubricDraft,
        *,
        confirmed_by: str,
        rationale: str,
        decision: str = "publish",
    ) -> tuple[RubricDraft, DecisionLedger]:
        if draft.status is RubricStatus.PUBLISHED:
            raise RubricImportError("published rubric is immutable")
        if confirmed_by != "human":
            raise RubricImportError("rubric publication requires human confirmation")
        if decision != "publish":
            raise RubricImportError("publication decision must be publish")
        if not rationale.strip():
            raise RubricImportError("publication rationale is required")
        if any(criterion.weight <= 0 for criterion in draft.criteria):
            raise RubricImportError("published rubric criteria must have positive weights")
        if not math.isclose(sum(criterion.weight for criterion in draft.criteria), 1.0, rel_tol=0, abs_tol=1e-6):
            raise RubricImportError("published rubric weights must sum to 1")

        decision_ledger = DecisionLedger(
            id=f"decision-{uuid4().hex}",
            subject_id=draft.id,
            decision=decision,
            rationale=rationale.strip(),
            decided_by=confirmed_by,
        )
        published = draft.model_copy(
            deep=True,
            update={
                "status": RubricStatus.PUBLISHED,
                "published_at": datetime.now(timezone.utc),
                "decision_ledger_id": decision_ledger.id,
            },
        )
        # Exercise the existing protocol contract before returning the draft.
        try:
            published.to_profile()
        except (ValidationError, ValueError) as exc:
            raise RubricImportError(str(exc)) from exc
        return published, decision_ledger
