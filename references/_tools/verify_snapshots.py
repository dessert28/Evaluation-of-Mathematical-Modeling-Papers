"""Verify upstream snapshot manifests, hashes, and candidate skill paths."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    sources = json.loads((ROOT / "references" / "SOURCES.json").read_text(encoding="utf-8"))
    checked = 0
    failures: list[str] = []
    for source in sources:
        slug = source["repository"].replace("/", "--")
        repo_dir = ROOT / "references" / "upstream" / slug
        manifest_path = repo_dir / "SOURCE_MANIFEST.json"
        if source.get("status") not in {"downloaded", "downloaded_sparse"}:
            failures.append(f"{source['repository']}: unexpected status {source.get('status')}")
            continue
        if not manifest_path.exists():
            failures.append(f"{source['repository']}: missing SOURCE_MANIFEST.json")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("files", []):
            path = repo_dir / Path(item["path"])
            checked += 1
            if not path.exists():
                failures.append(f"{source['repository']}: missing {item['path']}")
                continue
            if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                failures.append(f"{source['repository']}: hash/size mismatch {item['path']}")

    registry = ROOT / "config" / "skill_registry.yaml"
    if not registry.exists():
        failures.append("missing config/skill_registry.yaml")
    else:
        for line in registry.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("source:"):
                relative = line.split(":", 1)[1].strip()
                if not (ROOT / "skills" / relative).exists():
                    failures.append(f"registry source missing: {relative}")

    matrix = (ROOT / "docs" / "references" / "skill-audit-matrix.md").read_text(encoding="utf-8")
    for state in ("SUPPORTED", "CONDITIONAL", "INCONCLUSIVE", "REFUTED"):
        if f"`{state}`" not in matrix:
            failures.append(f"state missing from matrix: {state}")

    if failures:
        print("FAIL")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print(f"PASS: verified {len(sources)} snapshots and {checked} file hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

