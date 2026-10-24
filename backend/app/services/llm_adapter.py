"""OpenAI-compatible structured-output adapter.

The adapter performs one narrow operation: send a prompt and validate the JSON
reply against a Pydantic model. It never exposes tools, executes user code, or
changes ReviewJob state.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.app.services.prompt_templates import PromptTemplateStore
from backend.app.services.stage_orchestrator import StageResult
from backend.app.settings import Settings


T = TypeVar("T", bound=BaseModel)
_DECODE_ERROR_CODES = {"schema_validation_failed", "invalid_json_response"}
_WRAPPER_KEYS = ("result", "data", "output")
_CODE_FENCE = chr(96) * 3


class LLMAdapterError(RuntimeError):
    """Safe, non-secret error raised by the model transport or decoder."""

    def __init__(self, code: str, message: str, *, detail: str | None = None):
        super().__init__(message)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LLMCallMetadata:
    model: str
    attempts: int
    endpoint: str


class OpenAICompatibleAdapter:
    """Call a chat-completions compatible endpoint and validate its JSON."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[..., httpx.Client] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        settings_provider: Callable[[], Settings] | None = None,
        metadata_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or httpx.Client
        self._sleep = sleep
        self._settings_provider = settings_provider
        self._metadata_provider = metadata_provider

    def safe_metadata(self) -> dict[str, Any]:
        if self._metadata_provider:
            value = dict(self._metadata_provider())
            value.pop("api_key", None)
            value.pop("encrypted_api_key", None)
            return value
        settings = self._settings_provider() if self._settings_provider else self.settings
        return {"provider": "environment", "model": settings.openai_compatible_model or None}

    @property
    def endpoint(self) -> str:
        settings = self._settings_provider() if self._settings_provider else self.settings
        base = settings.openai_compatible_base_url.strip().rstrip("/")
        if not base:
            raise LLMAdapterError("llm_not_configured", "OPENAI_COMPATIBLE_BASE_URL 未配置")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.0,
    ) -> tuple[T, LLMCallMetadata]:
        settings = self._settings_provider() if self._settings_provider else self.settings
        model = settings.openai_compatible_model.strip()
        if not model:
            raise LLMAdapterError("llm_not_configured", "OPENAI_COMPATIBLE_MODEL 未配置")
        if not system_prompt.strip() or not user_prompt.strip():
            raise LLMAdapterError("prompt_empty", "system_prompt 和 user_prompt 不能为空")

        endpoint = self.endpoint
        schema = response_model.model_json_schema()
        system_with_contract = (
            system_prompt.rstrip()
            + "\n\n输出必须严格符合下面的 JSON Schema。不要增加 Schema 未定义的字段；"
            + "所有必填对象都要填写，引用 ID 必须指向本次输出中真实存在的对象。\n"
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        )
        current_user_prompt = user_prompt
        max_attempts = settings.llm_max_retries + 1
        last_error: LLMAdapterError | None = None

        for attempt in range(1, max_attempts + 1):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_with_contract},
                    {"role": "user", "content": current_user_prompt},
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
            headers = {"Content-Type": "application/json"}
            if settings.openai_compatible_api_key.strip():
                headers["Authorization"] = f"Bearer {settings.openai_compatible_api_key.strip()}"

            try:
                with self._client_factory(timeout=settings.llm_timeout_seconds) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
                last_error = LLMAdapterError(
                    "llm_transport_error",
                    f"模型服务连接失败：{exc.__class__.__name__}",
                )
                if attempt >= max_attempts:
                    raise last_error from exc
            else:
                if response.status_code >= 400:
                    retryable = response.status_code in {408, 409, 425, 429} or response.status_code >= 500
                    last_error = LLMAdapterError(
                        "llm_http_error" if retryable else "llm_http_nonretryable",
                        f"模型服务返回 HTTP {response.status_code}",
                    )
                    if not retryable or attempt >= max_attempts:
                        raise last_error
                else:
                    try:
                        parsed = self._decode_response(response, response_model)
                    except LLMAdapterError as exc:
                        last_error = exc
                        if exc.code in _DECODE_ERROR_CODES and attempt < max_attempts:
                            detail = (exc.detail or "JSON 结构或字段不符合 Schema").strip()
                            current_user_prompt = (
                                user_prompt.rstrip()
                                + "\n\n上一次回复未通过结构校验。请保留原评审结论，修正以下结构问题后，"
                                + "重新输出完整的 JSON 对象，不要输出解释或 Markdown：\n"
                                + detail
                            )
                        else:
                            raise
                    else:
                        return parsed, LLMCallMetadata(model=model, attempts=attempt, endpoint=endpoint)

            if attempt < max_attempts:
                self._sleep(settings.llm_retry_backoff_seconds * (2 ** (attempt - 1)))

        raise last_error or LLMAdapterError("llm_failed", "模型调用失败")

    @staticmethod
    def _content_from_response(response: httpx.Response) -> Any:
        body = response.json()
        message = body["choices"][0]["message"]
        content = message.get("content")
        if content is None:
            function_call = message.get("function_call") or {}
            content = function_call.get("arguments")
        if content is None:
            # Reasoning-capable models (e.g. DeepSeek V4 style) may emit the
            # assistant payload in ``message.reasoning`` and leave ``content``
            # empty.  Accept that field when it holds the actual answer.
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                content = reasoning
            elif isinstance(reasoning, (dict, list)) and reasoning:
                content = reasoning
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        if not isinstance(content, (str, dict)):
            raise TypeError("message content is not text or an object")
        return content

    @staticmethod
    def _loads_json(text: str) -> Any:
        stripped = text.strip()
        if stripped.startswith(_CODE_FENCE):
            first_newline = stripped.find("\n")
            if first_newline >= 0:
                stripped = stripped[first_newline + 1 :]
            else:
                stripped = stripped[len(_CODE_FENCE) :]
            if stripped.rstrip().endswith(_CODE_FENCE):
                stripped = stripped.rstrip()[: -len(_CODE_FENCE)].rstrip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as original_error:
            start = stripped.find("{")
            if start < 0:
                raise original_error
            try:
                value, _ = json.JSONDecoder().raw_decode(stripped[start:])
                return value
            except json.JSONDecodeError:
                raise original_error

    @staticmethod
    def _normalize_stage_aliases(data: Any) -> Any:
        """Normalize common OpenAI-compatible model aliases deterministically."""
        if not isinstance(data, dict):
            return data
        if len(data) == 1:
            for candidate in _WRAPPER_KEYS:
                nested = data.get(candidate)
                if isinstance(nested, dict) and "stage_id" in nested:
                    data = nested
                    break
        if "stage_id" not in data:
            return data

        payload = dict(data)
        evidence_items = payload.get("evidence")
        if isinstance(evidence_items, list):
            payload["evidence"] = [
                OpenAICompatibleAdapter._normalize_alias_item(
                    item,
                    {
                        "block_ref": "block_id",
                        "asset_ref": "asset_id",
                        "source_quote": "quote",
                    },
                )
                for item in evidence_items
            ]

        obligation_items = payload.get("obligations")
        if isinstance(obligation_items, list):
            normalized_obligations = []
            for item in obligation_items:
                item = OpenAICompatibleAdapter._normalize_alias_item(
                    item,
                    {"description": "text", "evidence_refs": "evidence_ids"},
                )
                if isinstance(item, dict) and "fulfilled" not in item and "status" in item:
                    status = str(item.get("status", "")).strip().lower()
                    positive = {"fulfilled", "satisfied", "met", "completed", "yes", "true"}
                    negative = {"unfulfilled", "unsatisfied", "unmet", "missing", "failed", "no", "false"}
                    if status in positive | negative:
                        item = dict(item)
                        item["fulfilled"] = status in positive
                        item.pop("status", None)
                normalized_obligations.append(item)
            payload["obligations"] = normalized_obligations

        claim_items = payload.get("claims")
        if isinstance(claim_items, list):
            normalized_claims = []
            for item in claim_items:
                item = OpenAICompatibleAdapter._normalize_alias_item(
                    item,
                    {
                        "statement": "exact_text",
                        "evidence_refs": "evidence_ids",
                        "obligation_refs": "obligation_ids",
                        "countercheck_refs": "countercheck_ids",
                    },
                )
                if isinstance(item, dict):
                    item = dict(item)
                    # Compatibility fallback: some models repeat prose under a non-schema rationale key.
                    item.pop("rationale", None)
                if isinstance(item, dict) and "verdict" not in item and "conclusion" in item:
                    conclusion = str(item.get("conclusion", "")).strip().upper()
                    verdict_aliases = {
                        "PASS": "SUPPORTED",
                        "VALID": "SUPPORTED",
                        "TRUE": "SUPPORTED",
                        "FAIL": "REFUTED",
                        "INVALID": "REFUTED",
                        "FALSE": "REFUTED",
                        "PARTIAL": "CONDITIONAL",
                        "UNKNOWN": "INCONCLUSIVE",
                    }
                    mapped = verdict_aliases.get(conclusion, conclusion)
                    if mapped in {"SUPPORTED", "CONDITIONAL", "INCONCLUSIVE", "REFUTED"}:
                        item = dict(item)
                        item["verdict"] = mapped
                        item.pop("conclusion", None)
                normalized_claims.append(item)
            payload["claims"] = normalized_claims

        finding_items = payload.get("findings")
        if isinstance(finding_items, list):
            payload["findings"] = [
                OpenAICompatibleAdapter._normalize_alias_item(
                    item,
                    {
                        "description": "detail",
                        "evidence_refs": "evidence_ids",
                        "claim_refs": "claim_ids",
                    },
                )
                for item in finding_items
            ]
        return payload

    @staticmethod
    def _normalize_alias_item(item: Any, aliases: dict[str, str]) -> Any:
        if not isinstance(item, dict):
            return item
        normalized = dict(item)
        for alias, canonical in aliases.items():
            if canonical not in normalized and alias in normalized:
                normalized[canonical] = normalized.pop(alias)
        return normalized

    @staticmethod
    def _format_validation_error(exc: ValidationError) -> str:
        labels = {
            "missing": "缺少必填字段",
            "extra_forbidden": "出现 Schema 未定义字段",
            "enum": "值不在允许范围",
            "greater_than_equal": "数值低于允许范围",
            "less_than_equal": "数值高于允许范围",
            "string_type": "应为字符串",
            "float_parsing": "应为数字",
            "int_parsing": "应为整数",
            "list_type": "应为数组",
        }
        details = []
        for error in exc.errors()[:16]:
            location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
            error_type = str(error.get("type", "validation_error"))
            message = labels.get(error_type, str(error.get("msg", "字段不符合 Schema")))
            details.append(f"{location}: {message}")
        if len(exc.errors()) > 16:
            details.append(f"另有 {len(exc.errors()) - 16} 个结构错误")
        return "；".join(details)

    @staticmethod
    def _decode_response(response: httpx.Response, response_model: type[T]) -> T:
        try:
            content = OpenAICompatibleAdapter._content_from_response(response)
            data = content if isinstance(content, dict) else OpenAICompatibleAdapter._loads_json(content)
            data = OpenAICompatibleAdapter._normalize_stage_aliases(data)
            return response_model.model_validate(data)
        except ValidationError as exc:
            detail = OpenAICompatibleAdapter._format_validation_error(exc)
            raise LLMAdapterError(
                "schema_validation_failed",
                f"模型 JSON 不符合目标 Schema：{detail}",
                detail=detail,
            ) from exc
        except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMAdapterError(
                "invalid_json_response",
                "模型返回不是可解析的结构化 JSON",
                detail="回复中没有可解析的 JSON 对象",
            ) from exc

    def evaluate_stage(
        self,
        stage_id: str,
        *,
        paper_context: str,
        evidence_catalog: str,
        rubric_context: str = "（未提供）",
        prior_results: str = "（无）",
        prompts: PromptTemplateStore | None = None,
    ) -> tuple[StageResult, LLMCallMetadata]:
        bundle = (prompts or PromptTemplateStore()).stage_prompt(
            stage_id,
            paper_context=paper_context,
            evidence_catalog=evidence_catalog,
            rubric_context=rubric_context,
            prior_results=prior_results,
        )
        return self.complete_json(
            system_prompt=bundle.system,
            user_prompt=bundle.user,
            response_model=StageResult,
        )


__all__ = ["LLMAdapterError", "LLMCallMetadata", "OpenAICompatibleAdapter"]
