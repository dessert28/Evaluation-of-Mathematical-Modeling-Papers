#!/usr/bin/env python3
"""Cross-platform local backend probe for math-science-computation."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def resolve_command(name: str) -> str | None:
    candidate = Path(name).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    return shutil.which(name)


def version_probe(executable: str, arguments: list[str]) -> dict:
    try:
        process = subprocess.run(
            [executable, *arguments],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        output = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
        return {
            "status": "available" if process.returncode == 0 else "probe_failed",
            "version_output": output,
            "exit_code": process.returncode,
            "error": "",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "probe_failed",
            "version_output": "",
            "exit_code": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def known_wolfram_installations(system: str) -> list[dict]:
    candidates: list[Path] = []
    if system == "Windows":
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(variable)
            if root:
                candidates.extend(Path(root, "Wolfram Research", "Wolfram").glob("*/Wolfram.exe"))
    elif system == "Darwin":
        applications = Path("/Applications")
        for pattern in ("Mathematica*.app/Contents/MacOS/WolframKernel", "Wolfram*.app/Contents/MacOS/WolframKernel"):
            candidates.extend(applications.glob(pattern))
    elif system == "Linux":
        for root in (Path("/usr/local/Wolfram"), Path("/opt/Wolfram")):
            candidates.extend(root.glob("Mathematica/*/Executables/WolframKernel"))
            candidates.extend(root.glob("Wolfram/*/Executables/WolframKernel"))

    for command in ("WolframKernel", "wolfram", "math"):
        path = resolve_command(command)
        if path:
            candidates.append(Path(path))

    installations: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate.is_file():
            continue
        resolved = str(candidate.resolve())
        key = os.path.normcase(resolved)
        if key in seen:
            continue
        seen.add(key)
        installations.append(
            {
                "version_directory": candidate.parent.name,
                "executable": resolved,
                "file_version": None,
            }
        )
    return installations


def probe_wolframscript(system: str) -> dict:
    path = resolve_command("wolframscript")
    if not path and system == "Windows":
        root = os.environ.get("ProgramFiles")
        candidate = Path(root, "Wolfram Research", "WolframScript", "wolframscript.exe") if root else None
        if candidate and candidate.is_file():
            path = str(candidate.resolve())
    if not path:
        return {"status": "unavailable", "path": None, "version_output": "", "exit_code": None, "error": ""}
    result = version_probe(path, ["-version"])
    return {"path": path, **result}


def probe_primecount(explicit: str) -> dict:
    if explicit:
        requested, source = explicit, "explicit"
    elif os.environ.get("PRIMECOUNT_EXE"):
        requested, source = os.environ["PRIMECOUNT_EXE"], "environment"
    else:
        requested, source = "primecount", "path"
    path = resolve_command(requested)
    if not path and source == "path" and platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        candidate = Path(local_app_data, "Programs", "primecount", "primecount.exe") if local_app_data else None
        if candidate and candidate.is_file():
            path, source = str(candidate.resolve()), "known_user_location"
    base = {"requested_command": requested, "discovery_source": source, "path": path}
    if not path:
        return {"status": "unavailable", **base, "version_output": "", "exit_code": None, "error": ""}
    return {**base, **version_probe(path, ["--version"])}


def probe_sage(command: str, wsl_distro: str, wsl_sage_command: str, system: str) -> dict:
    requested = command or "sage"
    path = resolve_command(requested)
    native = {"requested_command": requested, "path": path}
    if path:
        native.update(version_probe(path, ["--version"]))
    else:
        native.update({"status": "unavailable", "version_output": "", "exit_code": None, "error": ""})

    wsl = {
        "status": "not_requested",
        "distro": wsl_distro,
        "requested_command": wsl_sage_command,
        "version_output": "",
        "exit_code": None,
        "error": "",
    }
    if wsl_distro:
        if system != "Windows":
            wsl["status"] = "unsupported_platform"
        else:
            wsl_path = resolve_command("wsl.exe")
            if not wsl_path:
                wsl["status"] = "wsl_unavailable"
            else:
                result = version_probe(wsl_path, ["-d", wsl_distro, "--", wsl_sage_command, "--version"])
                wsl.update(result)
    return {"native": native, "wsl": wsl}


def probe_python(command: str) -> dict:
    path = resolve_command(command)
    base = {"requested_command": command, "path": path}
    if not path:
        return {"status": "unavailable", **base, "version": "", "libraries": {}, "exit_code": None, "error": ""}
    probe_code = r'''
import importlib.metadata, importlib.util, json, sys
modules = {"numpy":"numpy","sympy":"sympy","scipy":"scipy","mpmath":"mpmath","sage":"sagemath-standard","sageall":"sagemath-standard"}
libraries = {}
for module_name, distribution_name in modules.items():
    available = importlib.util.find_spec(module_name) is not None
    version = None
    if available:
        try: version = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError: pass
    libraries[module_name] = {"available": available, "version": version}
print(json.dumps({"python_version":sys.version.split()[0],"executable":sys.executable,"libraries":libraries}, ensure_ascii=False))
'''
    try:
        process = subprocess.run([path, "-c", probe_code], text=True, capture_output=True, check=False, timeout=20)
        if process.returncode != 0:
            return {"status": "probe_failed", **base, "version": "", "libraries": {}, "exit_code": process.returncode, "error": (process.stderr or process.stdout).strip()}
        data = json.loads(process.stdout)
        return {"status": "available", "requested_command": command, "path": data["executable"], "version": data["python_version"], "libraries": data["libraries"], "exit_code": 0, "error": ""}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {"status": "probe_failed", **base, "version": "", "libraries": {}, "exit_code": None, "error": f"{type(exc).__name__}: {exc}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-command", default=sys.executable)
    parser.add_argument("--sage-command", default="")
    parser.add_argument("--wsl-distro", default="")
    parser.add_argument("--wsl-sage-command", default="sage")
    parser.add_argument("--primecount-command", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    system = platform.system()
    result = {
        "schema_version": "1.0",
        "probed_at_utc": utc_now(),
        "host": {"system": system, "architecture": normalized_architecture(), "python_implementation": platform.python_implementation()},
        "mathematica": {
            "installations": known_wolfram_installations(system),
            "wolframscript": probe_wolframscript(system),
            "mcp": {"status": "requires_agent_probe", "evidence": "Call the configured Mathematica MCP from the agent and record the returned Wolfram Language version."},
        },
        "primecount": probe_primecount(args.primecount_command),
        "sagemath": probe_sage(args.sage_command, args.wsl_distro, args.wsl_sage_command, system),
        "python": probe_python(args.python_command),
    }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
