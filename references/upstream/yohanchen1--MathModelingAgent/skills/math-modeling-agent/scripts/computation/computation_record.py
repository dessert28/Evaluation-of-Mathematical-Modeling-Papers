#!/usr/bin/env python3
"""Initialize and validate reproducible mathematics/science computation records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
BACKENDS = {"mathematica", "primecount", "sagemath", "python", "other"}
AVAILABILITY = {"available", "unavailable", "unknown", "not-applicable"}
PRECISION_MODES = {"exact", "machine", "arbitrary", "interval", "mixed"}
EVIDENCE_LEVELS = {
    "proof-certificate",
    "formal-verification",
    "exact-check",
    "bounded-check",
    "numerical-evidence",
}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RecordError(ValueError):
    """A computation record is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            Path(temporary_name).unlink()
        except FileNotFoundError:
            pass
        raise


def relative_inside(path: Path, base_dir: Path, label: str) -> str:
    resolved_path = path.resolve()
    resolved_base = base_dir.resolve()
    try:
        relative = resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise RecordError(f"{label} must be inside the record base directory") from exc
    return relative.as_posix()


def resolve_safe_relative(base_dir: Path, raw_path: Any, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RecordError(f"{label} must be a nonempty relative path")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise RecordError(f"{label} must not be absolute")
    resolved_base = base_dir.resolve()
    resolved = (resolved_base / candidate).resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise RecordError(f"{label} escapes the base directory") from exc
    return resolved


def require_mapping(parent: dict[str, Any], key: str, label: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RecordError(f"{label}.{key} must be an object")
    return value


def require_nonempty_string(parent: dict[str, Any], key: str, label: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RecordError(f"{label}.{key} must be a nonempty string")
    return value.strip()


def require_string_list(parent: dict[str, Any], key: str, label: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RecordError(f"{label}.{key} must be a list of strings")
    return value


def validate_hash(raw_hash: Any, label: str) -> str:
    if not isinstance(raw_hash, str) or not HEX_SHA256.fullmatch(raw_hash):
        raise RecordError(f"{label} must be a lowercase SHA-256 hex digest")
    return raw_hash


def init_record(task_file: Path, record_path: Path, force: bool) -> None:
    task_file = task_file.resolve()
    record_path = record_path.resolve()
    if not task_file.is_file():
        raise RecordError(f"task file does not exist: {task_file}")
    record_path.parent.mkdir(parents=True, exist_ok=True)
    if record_path.exists() and not force:
        raise RecordError(f"record already exists: {record_path}; pass --force to replace it")
    task_relative = relative_inside(task_file, record_path.parent, "task file")

    record = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": {
            "file": task_relative,
            "sha256": sha256_file(task_file),
            "object": "",
            "deliverables": [],
        },
        "mathematical_context": {
            "assumptions": [],
            "domain": "",
            "precision": {
                "mode": "exact",
                "working_digits": None,
                "target_tolerance": "",
            },
        },
        "implementation_discovery": {
            backend: {
                "candidate_implementations": [],
                "existence_evidence": "",
                "local_availability": "unknown",
                "availability_evidence": "",
            }
            for backend in ("mathematica", "primecount", "sagemath", "python")
        },
        "decision": {
            "selected_backend": "",
            "backend_version": "",
            "selection_reason": "",
            "fallback_reason": "",
        },
        "execution": {
            "status": "planned",
            "interface": "",
            "command_or_input": "",
            "code_artifact": "",
        },
        "artifacts": [],
        "result": {
            "status": "pending",
            "summary": "",
            "result_artifact": "",
        },
        "verification": {
            "methods": [],
            "evidence_level": "",
            "residual_or_error": "",
            "limitations": [],
        },
    }
    write_json(record_path, record)
    print(json.dumps({"ok": True, "record": str(record_path)}, ensure_ascii=False))


def validate_record(record_path: Path, base_dir: Path | None) -> dict[str, Any]:
    record_path = record_path.resolve()
    if not record_path.is_file():
        raise RecordError(f"record does not exist: {record_path}")
    base = (base_dir or record_path.parent).resolve()
    if not base.is_dir():
        raise RecordError(f"base directory does not exist: {base}")

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordError(f"cannot read record JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise RecordError("record root must be an object")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise RecordError(f"schema_version must be {SCHEMA_VERSION}")

    task = require_mapping(record, "task", "record")
    require_nonempty_string(task, "object", "task")
    deliverables = require_string_list(task, "deliverables", "task")
    if not deliverables:
        raise RecordError("task.deliverables must contain at least one item")
    task_path = resolve_safe_relative(base, task.get("file"), "task.file")
    if not task_path.is_file():
        raise RecordError(f"task.file does not exist: {task_path}")
    task_hash = validate_hash(task.get("sha256"), "task.sha256")
    if sha256_file(task_path) != task_hash:
        raise RecordError("task.sha256 does not match task.file")

    context = require_mapping(record, "mathematical_context", "record")
    require_string_list(context, "assumptions", "mathematical_context")
    require_nonempty_string(context, "domain", "mathematical_context")
    precision = require_mapping(context, "precision", "mathematical_context")
    mode = require_nonempty_string(precision, "mode", "mathematical_context.precision")
    if mode not in PRECISION_MODES:
        raise RecordError(f"mathematical_context.precision.mode must be one of {sorted(PRECISION_MODES)}")
    working_digits = precision.get("working_digits")
    if working_digits is not None and (not isinstance(working_digits, int) or working_digits <= 0):
        raise RecordError("mathematical_context.precision.working_digits must be null or a positive integer")
    target_tolerance = precision.get("target_tolerance")
    if not isinstance(target_tolerance, str):
        raise RecordError("mathematical_context.precision.target_tolerance must be a string")
    if mode != "exact" and not target_tolerance.strip():
        raise RecordError("numerical precision modes require mathematical_context.precision.target_tolerance")

    discovery = require_mapping(record, "implementation_discovery", "record")
    for backend in ("mathematica", "primecount", "sagemath", "python"):
        entry = require_mapping(discovery, backend, "implementation_discovery")
        candidates = entry.get("candidate_implementations")
        if not isinstance(candidates, list) or any(not isinstance(item, str) for item in candidates):
            raise RecordError(
                f"implementation_discovery.{backend}.candidate_implementations must be a list of strings"
            )
        require_nonempty_string(entry, "existence_evidence", f"implementation_discovery.{backend}")
        availability = require_nonempty_string(
            entry, "local_availability", f"implementation_discovery.{backend}"
        )
        if availability not in AVAILABILITY:
            raise RecordError(
                f"implementation_discovery.{backend}.local_availability must be one of {sorted(AVAILABILITY)}"
            )
        require_nonempty_string(
            entry, "availability_evidence", f"implementation_discovery.{backend}"
        )

    decision = require_mapping(record, "decision", "record")
    selected_backend = require_nonempty_string(decision, "selected_backend", "decision")
    if selected_backend not in BACKENDS:
        raise RecordError(f"decision.selected_backend must be one of {sorted(BACKENDS)}")
    require_nonempty_string(decision, "backend_version", "decision")
    require_nonempty_string(decision, "selection_reason", "decision")
    require_nonempty_string(decision, "fallback_reason", "decision")
    if selected_backend in discovery:
        selected_entry = discovery[selected_backend]
        if selected_entry.get("local_availability") != "available":
            raise RecordError("the selected backend must have local_availability=available")

    execution = require_mapping(record, "execution", "record")
    if require_nonempty_string(execution, "status", "execution") != "complete":
        raise RecordError("execution.status must be complete")
    require_nonempty_string(execution, "interface", "execution")
    require_nonempty_string(execution, "command_or_input", "execution")
    code_artifact = require_nonempty_string(execution, "code_artifact", "execution")

    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RecordError("artifacts must be a nonempty list")
    roles: set[str] = set()
    artifact_paths: set[str] = set()
    verified_artifacts = []
    for index, artifact in enumerate(artifacts):
        label = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            raise RecordError(f"{label} must be an object")
        role = require_nonempty_string(artifact, "role", label)
        raw_path = require_nonempty_string(artifact, "path", label)
        expected_hash = validate_hash(artifact.get("sha256"), f"{label}.sha256")
        artifact_path = resolve_safe_relative(base, raw_path, f"{label}.path")
        if not artifact_path.is_file():
            raise RecordError(f"{label}.path does not exist: {artifact_path}")
        actual_hash = sha256_file(artifact_path)
        if actual_hash != expected_hash:
            raise RecordError(f"{label}.sha256 does not match {raw_path}")
        roles.add(role)
        artifact_paths.add(Path(raw_path).as_posix())
        verified_artifacts.append(
            {"role": role, "path": Path(raw_path).as_posix(), "sha256": actual_hash}
        )
    if "code" not in roles or "result" not in roles:
        raise RecordError("artifacts must include both code and result roles")
    if Path(code_artifact).as_posix() not in artifact_paths:
        raise RecordError("execution.code_artifact must name a hashed artifact")

    result = require_mapping(record, "result", "record")
    if require_nonempty_string(result, "status", "result") != "complete":
        raise RecordError("result.status must be complete")
    require_nonempty_string(result, "summary", "result")
    result_artifact = require_nonempty_string(result, "result_artifact", "result")
    if Path(result_artifact).as_posix() not in artifact_paths:
        raise RecordError("result.result_artifact must name a hashed artifact")

    verification = require_mapping(record, "verification", "record")
    methods = require_string_list(verification, "methods", "verification")
    if not methods or any(not method.strip() for method in methods):
        raise RecordError("verification.methods must contain at least one nonempty method")
    evidence_level = require_nonempty_string(
        verification, "evidence_level", "verification"
    )
    if evidence_level not in EVIDENCE_LEVELS:
        raise RecordError(f"verification.evidence_level must be one of {sorted(EVIDENCE_LEVELS)}")
    residual_or_error = verification.get("residual_or_error")
    if not isinstance(residual_or_error, str):
        raise RecordError("verification.residual_or_error must be a string")
    if mode != "exact" and not residual_or_error.strip():
        raise RecordError("numerical precision modes require verification.residual_or_error")
    require_string_list(verification, "limitations", "verification")

    return {
        "ok": True,
        "record": str(record_path),
        "base_dir": str(base),
        "selected_backend": selected_backend,
        "evidence_level": evidence_level,
        "verified_artifacts": verified_artifacts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize or validate a computation-record.json file."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize a record from a task file")
    init_parser.add_argument("--task-file", required=True, type=Path)
    init_parser.add_argument("--record", required=True, type=Path)
    init_parser.add_argument("--force", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="validate a completed record")
    validate_parser.add_argument("--record", required=True, type=Path)
    validate_parser.add_argument("--base-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            init_record(args.task_file, args.record, args.force)
            return 0
        result = validate_record(args.record, args.base_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, RecordError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
