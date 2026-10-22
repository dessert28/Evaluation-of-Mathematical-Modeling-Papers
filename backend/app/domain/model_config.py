from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=2000)
    api_key: str = Field(default="", max_length=4000)
    model: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class ModelConfigPublic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    base_url: str
    model: str
    is_active: bool
    api_key_configured: bool
    created_at: str | None = None
    updated_at: str | None = None


PROVIDER_PRESETS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "custom": "",
}
