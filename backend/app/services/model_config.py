from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any
from uuid import uuid4
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

from backend.app.domain.model_config import ModelConfigInput, PROVIDER_PRESETS
from backend.app.settings import Settings


class ModelConfigError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ModelConfigService:
    def __init__(self, settings: Settings, repository: Any):
        self.settings = settings
        self.repository = repository
        self.key_path = settings.data_dir.expanduser().resolve() / ".model-config.key"
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self._startup_error: ModelConfigError | None = None

    def initialize(self) -> None:
        """Create the local key at startup, while keeping a lost-key app usable."""
        try:
            self._fernet()
        except ModelConfigError as exc:
            self._startup_error = exc

    def _ensure_unlocked(self) -> None:
        if self._startup_error is not None:
            raise self._startup_error

    def _fernet(self) -> Fernet:
        if self.key_path.exists():
            try:
                return Fernet(self.key_path.read_bytes().strip())
            except Exception as exc:
                raise ModelConfigError("model_config_locked", "模型配置主密钥不可读取", 503) from exc
        if self.repository.has_any():
            raise ModelConfigError("model_config_locked", "模型配置主密钥丢失，无法解密已有配置", 503)
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return Fernet(key)

    def _decrypt(self, token: str) -> str:
        try:
            return self._fernet().decrypt(token.encode()).decode()
        except (InvalidToken, UnicodeError) as exc:
            raise ModelConfigError("model_config_locked", "模型配置无法解密", 503) from exc

    def list_public(self) -> list[dict[str, Any]]:
        self._ensure_unlocked()
        return self.repository.list()

    def get_public(self, config_id: str) -> dict[str, Any] | None:
        self._ensure_unlocked()
        return self.repository.get(config_id)

    def create(self, data: ModelConfigInput) -> dict[str, Any]:
        self._ensure_unlocked()
        base = data.base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ModelConfigError("invalid_base_url", "API URL 必须以 http:// 或 https:// 开头")
        self._validate_url(base)
        token = self._fernet().encrypt(data.api_key.encode()).decode()
        payload = {"id": f"model-config-{uuid4().hex}", "provider": data.provider.strip(), "base_url": base, "model": data.model.strip(), "encrypted_api_key": token, "is_active": data.is_active}
        return self.repository.create(payload)

    def update(self, config_id: str, data: ModelConfigInput) -> dict[str, Any] | None:
        self._ensure_unlocked()
        current = self.repository.get(config_id)
        if current is None:
            return None
        api_key = data.api_key
        if not api_key:
            secret = self.repository.get_secret(config_id)
            if secret:
                api_key = self._decrypt(secret)
        base = data.base_url.strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ModelConfigError("invalid_base_url", "API URL 必须以 http:// 或 https:// 开头")
        self._validate_url(base)
        token = self._fernet().encrypt(api_key.encode()).decode()
        return self.repository.update(config_id, {"provider": data.provider.strip(), "base_url": base, "model": data.model.strip(), "encrypted_api_key": token, "is_active": data.is_active})

    def delete(self, config_id: str) -> bool:
        self._ensure_unlocked()
        return self.repository.delete(config_id)

    @staticmethod
    def _validate_url(base: str) -> None:
        try:
            url = urlsplit(base)
            if not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('unsafe URL')
            _ = url.port
        except ValueError as exc:
            raise ModelConfigError('invalid_base_url', 'API URL 必须是无用户名、密码、查询参数或片段的服务地址；密钥请填写在 API Key 中') from exc

    def runtime_settings(self) -> Settings:
        self._ensure_unlocked()
        active = self.repository.get_active()
        if not active:
            return self.settings
        encrypted = self.repository.get_secret(active["id"])
        api_key = self._decrypt(encrypted) if encrypted else ""
        return self.settings.model_copy(update={"openai_compatible_base_url": active["base_url"], "openai_compatible_model": active["model"], "openai_compatible_api_key": api_key})

    def runtime_metadata(self) -> dict[str, Any]:
        """Return safe provider metadata for snapshots and reports."""
        self._ensure_unlocked()
        active = self.repository.get_active()
        if not active:
            return {"provider": "environment", "model": self.settings.openai_compatible_model or None}
        return {"provider": active["provider"], "model": active["model"], "base_url": active["base_url"]}

    def presets(self) -> dict[str, str]:
        return dict(PROVIDER_PRESETS)


__all__ = ["ModelConfigError", "ModelConfigService"]
