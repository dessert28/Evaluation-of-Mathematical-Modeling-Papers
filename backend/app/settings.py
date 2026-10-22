"""Application configuration for the local-first review service."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings with safe local defaults.

    Secrets are intentionally represented only in memory.  The project never writes
    them to logs or the SQLite database.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    openai_compatible_base_url: str = Field(default="", validation_alias="OPENAI_COMPATIBLE_BASE_URL")
    openai_compatible_api_key: str = Field(default="", validation_alias="OPENAI_COMPATIBLE_API_KEY")
    openai_compatible_model: str = Field(default="", validation_alias="OPENAI_COMPATIBLE_MODEL")
    openagent_skills_root: str = Field(default="", validation_alias="OPENAGENT_SKILLS_ROOT")
    search_base_url: str = Field(default="", validation_alias="SEARCH_BASE_URL")
    data_dir: Path = Field(default=Path("data"), validation_alias="DATA_DIR")
    frontend_dist_dir: Path | None = Field(default=None, validation_alias="FRONTEND_DIST_DIR")
    desktop_api_base: str = Field(default="", validation_alias="DESKTOP_API_BASE")
    desktop_session_token: SecretStr | None = Field(default=None, validation_alias="DESKTOP_SESSION_TOKEN")
    app_timezone: str = Field(default="Asia/Shanghai", validation_alias="APP_TIMEZONE")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, validation_alias="MAX_UPLOAD_BYTES", gt=0)
    llm_timeout_seconds: float = Field(default=60.0, validation_alias="LLM_TIMEOUT_SECONDS", gt=0)
    llm_max_retries: int = Field(default=2, validation_alias="LLM_MAX_RETRIES", ge=0, le=6)
    llm_retry_backoff_seconds: float = Field(default=1.0, validation_alias="LLM_RETRY_BACKOFF_SECONDS", ge=0, le=60)

    @property
    def database_path(self) -> Path:
        """Return the SQLite path and create the parent directory when needed."""

        return self.data_dir.expanduser().resolve() / "app.db"

    @property
    def assets_dir(self) -> Path:
        """Return the content-addressed upload directory."""

        return self.data_dir.expanduser().resolve() / "assets"
