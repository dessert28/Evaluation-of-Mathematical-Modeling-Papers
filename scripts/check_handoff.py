"""Check that HANDOFF_LOG.md has a complete latest entry.

This is intentionally small and dependency-free so it can run before Git
commits on a native Windows Python installation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED = (
    "操作者",
    "目标",
    "修改项目/文件",
    "验证",
    "未决风险",
    "下一步",
    "交接对象",
)


def main() -> int:
    log = Path(__file__).resolve().parents[1] / "HANDOFF_LOG.md"
    if not log.exists():
        print(f"FAIL: missing {log}")
        return 1
    text = log.read_text(encoding="utf-8")
    entries = re.split(r"(?m)^##\s+", text)
    latest = next((item for item in reversed(entries) if item.strip()), "")
    missing = [label for label in REQUIRED if f"**{label}**" not in latest]
    timestamp_ok = bool(re.search(r"202\d-\d\d-\d\d\s+\d\d:\d\d:\d\d\s+\+08:00", latest))
    if missing or not timestamp_ok:
        print("FAIL: incomplete latest handoff entry")
        if missing:
            print("missing:", ", ".join(missing))
        if not timestamp_ok:
            print("missing Asia/Shanghai timestamp")
        return 1
    print("PASS: latest HANDOFF_LOG.md entry contains required fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())

