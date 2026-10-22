"""Windows per-user runtime paths and safe data migration."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


APP_DATA_NAME = "MathModelingPaperReview"


class ProfileError(RuntimeError):
    """Raised when a local profile cannot safely be initialized or migrated."""


def user_data_dir() -> Path:
    """Return the writable per-user application data directory."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise ProfileError("无法定位 Windows 用户数据目录，请检查 LOCALAPPDATA 环境变量。")
    return Path(local_app_data) / APP_DATA_NAME / "data"


def profile_state(destination: Path | None = None) -> str:
    """Return `ready`, `empty`, or `partial` without modifying the profile."""
    path = (destination or user_data_dir()).expanduser()
    if not path.exists():
        return "empty"
    if not path.is_dir():
        return "partial"
    if (path / "app.db").is_file():
        return "ready"
    try:
        return "empty" if next(path.iterdir(), None) is None else "partial"
    except OSError:
        return "partial"


def prepare_fresh_profile(destination: Path | None = None) -> Path:
    """Create a new profile only when the destination is absent or empty."""
    path = (destination or user_data_dir()).expanduser().resolve()
    if path.exists() and (not path.is_dir() or next(path.iterdir(), None) is not None):
        raise ProfileError("目标数据目录已有内容，不能作为新数据目录覆盖。")
    path.mkdir(parents=True, exist_ok=True)
    return path


def migrate_data(source: Path, destination: Path | None = None) -> Path:
    """Copy a selected legacy DATA_DIR without changing its source.

    The copy is assembled in a sibling temporary directory and renamed into
    place only after `copytree` has completed. Existing non-empty destinations
    are never overwritten.
    """
    source_path = source.expanduser().resolve()
    destination_path = (destination or user_data_dir()).expanduser().resolve()
    if not source_path.is_dir():
        raise ProfileError("所选目录不存在或不可读取。")
    if source_path == destination_path or source_path in destination_path.parents:
        raise ProfileError("源目录和目标目录不能相同或互相嵌套。")
    if destination_path.exists():
        if not destination_path.is_dir() or next(destination_path.iterdir(), None) is not None:
            raise ProfileError("目标数据目录已有内容；为避免覆盖，迁移已取消。")
    try:
        if next(source_path.iterdir(), None) is None:
            raise ProfileError("所选目录为空，没有可迁移的数据。")
    except OSError as exc:
        raise ProfileError("无法读取所选数据目录。") from exc
    if not any((source_path / name).exists() for name in ("app.db", "assets", ".model-config.key")):
        raise ProfileError("所选目录不像工作台数据目录；请选择包含 app.db、assets 或模型密钥文件的数据目录。")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{APP_DATA_NAME}-migration-", dir=destination_path.parent))
    shutil.rmtree(staging)
    try:
        shutil.copytree(source_path, staging, copy_function=shutil.copy2, symlinks=True)
        if destination_path.exists():
            if next(destination_path.iterdir(), None) is not None:
                raise ProfileError("迁移过程中目标目录出现新数据；为避免覆盖，迁移已取消。")
            destination_path.rmdir()
        staging.rename(destination_path)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination_path


def startup_profile(mode: str, source_dir: Path | None = None, destination: Path | None = None) -> Path:
    """Prepare a fresh profile or migrate the user-selected legacy directory."""
    if mode == "fresh":
        return prepare_fresh_profile(destination)
    if mode == "migrate" and source_dir is not None:
        return migrate_data(source_dir, destination)
    raise ProfileError("请选择创建新工作区，或选择需要迁移的数据目录。")


__all__ = ["APP_DATA_NAME", "ProfileError", "migrate_data", "prepare_fresh_profile", "profile_state", "startup_profile", "user_data_dir"]
