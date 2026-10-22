#!/usr/bin/env python3
"""Read, refresh, or invalidate the cross-platform backend inventory."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


BACKENDS = ("mathematica", "primecount", "sagemath", "python")
REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
MCP_PROTOCOL_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_architecture() -> str:
    value = platform.machine().lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
    }.get(value, value or "unknown")


def default_state_file() -> Path:
    override = os.environ.get("MATH_SCIENCE_BACKEND_INVENTORY")
    if override:
        return Path(override).expanduser()
    return Path(tempfile.gettempdir(), "DSH", "math-science-computation", "backend-inventory.json")


def read_inventory(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        local = data.get("local") if isinstance(data, dict) else None
        mcp = data.get("mcp") if isinstance(data, dict) else None
        if (
            not isinstance(data, dict)
            or not isinstance(local, dict)
            or not isinstance(mcp, dict)
            or data.get("inventory_schema_version") != "1.0"
            or local.get("schema_version") != "1.0"
        ):
            return None
        return data
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def invoke_probe(args: argparse.Namespace) -> dict:
    if args.probe_json_file:
        return json.loads(Path(args.probe_json_file).read_text(encoding="utf-8"))
    probe_script = Path(args.probe_script)
    if not probe_script.is_file():
        raise RuntimeError("Backend probe script is unavailable.")
    command = [
        sys.executable,
        str(probe_script),
        "--python-command",
        args.python_command,
        "--wsl-sage-command",
        args.wsl_sage_command,
    ]
    for option, value in (
        ("--sage-command", args.sage_command),
        ("--wsl-distro", args.wsl_distro),
        ("--primecount-command", args.primecount_command),
    ):
        if value:
            command.extend([option, value])
    process = subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)
    if process.returncode != 0:
        message = (process.stderr or process.stdout).strip()
        raise RuntimeError(f"Backend probe failed with exit code {process.returncode}: {message}")
    return json.loads(process.stdout)


def new_inventory(local: dict) -> dict:
    now = utc_now()
    return {
        "inventory_schema_version": "1.0",
        "created_at_utc": now,
        "updated_at_utc": now,
        "local": local,
        "mcp": {
            "authority": "current_session_tool_discovery_and_call",
            "persisted_status": "historical_only",
            "required_action": "Build a current-session overlay and live-check only the selected MCP backend.",
        },
        "invalidations": [],
    }


def mcp_observation(args: argparse.Namespace) -> dict:
    values = {
        "server_name": args.mcp_server_name,
        "protocol_version": args.mcp_protocol_version,
        "server_version": args.mcp_server_version,
        "wolfram_language_version": args.mcp_wolfram_language_version,
    }
    missing = [name for name, value in values.items() if not value.strip()]
    if missing:
        raise SystemExit("RecordMcp requires: " + ", ".join(missing))
    if not MCP_PROTOCOL_PATTERN.fullmatch(values["protocol_version"]):
        raise SystemExit("MCP protocol version must use the negotiated YYYY-MM-DD form.")
    observed_at = args.mcp_observed_at_utc or utc_now()
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit("MCP observation time must be an ISO-8601 timestamp.") from exc
    return {
        **values,
        "observed_at_utc": observed_at,
        "evidence": "initialize_handshake_and_evaluator",
    }


def write_inventory_atomic(inventory: dict, path: Path) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".backend-inventory-{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def missing_backend_paths(inventory: dict) -> list[str]:
    local = inventory["local"]
    missing: set[str] = set()
    for installation in local.get("mathematica", {}).get("installations", []):
        executable = installation.get("executable")
        if executable and not Path(executable).is_file():
            missing.add("mathematica")
    checks = (
        ("mathematica", local.get("mathematica", {}).get("wolframscript", {}).get("path")),
        ("primecount", local.get("primecount", {}).get("path")),
        ("sagemath", local.get("sagemath", {}).get("native", {}).get("path")),
        ("python", local.get("python", {}).get("path")),
    )
    for name, value in checks:
        if value and not Path(value).is_file():
            missing.add(name)
    return [name for name in BACKENDS if name in missing]


def inventory_expired(inventory: dict, max_age_hours: int) -> bool:
    if max_age_hours <= 0:
        return False
    try:
        updated = datetime.fromisoformat(inventory["updated_at_utc"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds() >= max_age_hours * 3600
    except (KeyError, TypeError, ValueError):
        return True


def host_changed(inventory: dict) -> bool:
    host = inventory.get("local", {}).get("host")
    if not isinstance(host, dict):
        return True
    return host.get("system") != platform.system() or host.get("architecture") != normalized_architecture()


def selected_backends(names: list[str]) -> list[str]:
    if "all" in names:
        return list(BACKENDS)
    return [name for name in BACKENDS if name in names]


def merge_backends(inventory: dict, fresh_local: dict, names: list[str]) -> dict:
    for name in selected_backends(names):
        inventory["local"][name] = fresh_local[name]
    inventory["local"]["probed_at_utc"] = fresh_local["probed_at_utc"]
    inventory["local"]["host"] = fresh_local.get("host", {})
    inventory["updated_at_utc"] = utc_now()
    return inventory


def emit_result(
    inventory: dict,
    state_file: Path,
    started: float,
    cache_status: str,
    refreshed: list[str] | None = None,
    invalid_paths: list[str] | None = None,
    backend_started: bool = False,
    write_error: str = "",
) -> None:
    output = {
        "inventory_schema_version": inventory["inventory_schema_version"],
        "snapshot_updated_at_utc": inventory["updated_at_utc"],
        "cache": {
            "status": cache_status,
            "state_file": str(state_file),
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "backend_started": backend_started,
            "refreshed_backends": refreshed or [],
            "invalid_path_backends": invalid_paths or [],
            "write_error": write_error,
        },
        "local": inventory["local"],
        "mcp": {
            "status": "session_probe_required",
            "authority": "current_session_tool_discovery_and_call",
            "note": "The persisted snapshot is not evidence that an MCP tool is callable in this session.",
            "recorded_mathematica_observation": inventory.get("mcp", {}).get("mathematica"),
        },
    }
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("ReadOrCreate", "Refresh", "Invalidate", "RecordMcp"), default="ReadOrCreate")
    parser.add_argument("--state-file", default="")
    parser.add_argument("--backend", choices=("all", *BACKENDS), nargs="+", default=["all"])
    parser.add_argument("--reason-code", default="")
    parser.add_argument("--max-age-hours", type=int, default=168)
    parser.add_argument("--probe-script", default=str(Path(__file__).with_name("probe_backends.py")))
    parser.add_argument("--probe-json-file", default="")
    parser.add_argument("--python-command", default=sys.executable)
    parser.add_argument("--sage-command", default="")
    parser.add_argument("--wsl-distro", default="")
    parser.add_argument("--wsl-sage-command", default="sage")
    parser.add_argument("--primecount-command", default="")
    parser.add_argument("--mcp-server-name", default="")
    parser.add_argument("--mcp-protocol-version", default="")
    parser.add_argument("--mcp-server-version", default="")
    parser.add_argument("--mcp-wolfram-language-version", default="")
    parser.add_argument("--mcp-observed-at-utc", default="")
    return parser


def main() -> int:
    started = time.perf_counter()
    args = build_parser().parse_args()
    if args.mode == "Invalidate" and not REASON_PATTERN.fullmatch(args.reason_code):
        raise SystemExit("Invalidate mode requires a bounded lowercase reason code.")
    state_file = Path(args.state_file).expanduser() if args.state_file else default_state_file()
    state_file = state_file.resolve()
    inventory = read_inventory(state_file)
    missing: list[str] = []

    if args.mode == "RecordMcp":
        observation = mcp_observation(args)
        backend_started = False
        if inventory is None:
            fresh_local = invoke_probe(args)
            if fresh_local.get("schema_version") != "1.0":
                raise SystemExit("Unsupported backend probe schema.")
            fresh_local.get("mathematica", {}).pop("mcp", None)
            inventory = new_inventory(fresh_local)
            backend_started = True
        inventory["mcp"]["mathematica"] = observation
        inventory["updated_at_utc"] = utc_now()
        write_inventory_atomic(inventory, state_file)
        emit_result(inventory, state_file, started, "mcp_recorded", backend_started=backend_started)
        return 0

    if args.mode == "ReadOrCreate" and inventory:
        missing = missing_backend_paths(inventory)
        if not missing and not inventory_expired(inventory, args.max_age_hours) and not host_changed(inventory):
            emit_result(inventory, state_file, started, "hit")
            return 0

    fresh_local = invoke_probe(args)
    if fresh_local.get("schema_version") != "1.0":
        raise SystemExit("Unsupported backend probe schema.")
    fresh_local.get("mathematica", {}).pop("mcp", None)

    refreshed = list(BACKENDS)
    cache_status = "created"
    if inventory is None:
        inventory = new_inventory(fresh_local)
    else:
        cache_status = "refreshed"
        if args.mode in {"Refresh", "Invalidate"}:
            refreshed = selected_backends(args.backend)
        elif missing and not host_changed(inventory):
            refreshed = missing
        if args.mode == "Invalidate":
            inventory["invalidations"] = (inventory.get("invalidations", []) + [
                {"backend": name, "reason": args.reason_code, "recorded_at_utc": utc_now()}
                for name in refreshed
            ])[-20:]
        inventory = merge_backends(inventory, fresh_local, refreshed)

    write_error = ""
    try:
        write_inventory_atomic(inventory, state_file)
    except OSError as exc:
        write_error = type(exc).__name__
        cache_status = "write_failed"
    emit_result(inventory, state_file, started, cache_status, refreshed, missing, True, write_error)
    return 1 if write_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
