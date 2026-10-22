from __future__ import annotations

import httpx
import pytest
import json

from backend.app.services.llm_adapter import LLMAdapterError, OpenAICompatibleAdapter
from backend.app.services.stage_orchestrator import StageResult
from backend.app.settings import Settings


def _settings(**kwargs) -> Settings:
    return Settings(
        openai_compatible_base_url="http://model.local/v1",
        openai_compatible_api_key="secret-key",
        openai_compatible_model="local-model",
        llm_max_retries=kwargs.pop("llm_max_retries", 0),
        llm_retry_backoff_seconds=0,
        **kwargs,
    )


def _stage_payload():
    return {
        "stage_id": "problem_identification",
        "raw_score_0_10": 8,
        "rationale": "evidence reviewed",
        "evidence": [{"id": "e-1", "kind": "document", "asset_id": "asset-1", "block_id": "block-1", "evidence_level": "VERIFIED"}],
    }


def test_adapter_validates_structured_stage_json_without_exposing_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(_stage_payload())}}]})

    transport = httpx.MockTransport(handler)
    adapter = OpenAICompatibleAdapter(_settings(), client_factory=lambda **kw: httpx.Client(transport=transport, **kw))
    result, metadata = adapter.complete_json(system_prompt="system", user_prompt="user", response_model=StageResult)
    assert result.stage_id == "problem_identification"
    assert metadata.attempts == 1


def test_adapter_retries_transient_http_errors():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(_stage_payload())}}]})

    transport = httpx.MockTransport(handler)
    adapter = OpenAICompatibleAdapter(_settings(llm_max_retries=1), client_factory=lambda **kw: httpx.Client(transport=transport, **kw))
    result, metadata = adapter.complete_json(system_prompt="system", user_prompt="user", response_model=StageResult)
    assert result.stage_id == "problem_identification"
    assert calls["count"] == 2
    assert metadata.attempts == 2


def test_adapter_does_not_retry_non_retryable_http_errors():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    transport = httpx.MockTransport(handler)
    adapter = OpenAICompatibleAdapter(_settings(llm_max_retries=3), client_factory=lambda **kw: httpx.Client(transport=transport, **kw))
    with pytest.raises(LLMAdapterError) as error:
        adapter.complete_json(system_prompt="system", user_prompt="user", response_model=StageResult)
    assert error.value.code == "llm_http_nonretryable"
    assert calls["count"] == 1


def test_adapter_rejects_invalid_json_schema():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}))
    adapter = OpenAICompatibleAdapter(_settings(), client_factory=lambda **kw: httpx.Client(transport=transport, **kw))
    with pytest.raises(LLMAdapterError) as error:
        adapter.complete_json(system_prompt="system", user_prompt="user", response_model=StageResult)
    assert error.value.code == "schema_validation_failed"
    assert "secret-key" not in str(error.value)


def test_adapter_injects_schema_and_repairs_invalid_structured_output():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append(payload)
        if len(calls) == 1:
            content = "{}"
        else:
            content = json.dumps(_stage_payload())
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    transport = httpx.MockTransport(handler)
    adapter = OpenAICompatibleAdapter(
        _settings(llm_max_retries=1),
        client_factory=lambda **kw: httpx.Client(transport=transport, **kw),
        sleep=lambda _: None,
    )
    result, metadata = adapter.complete_json(
        system_prompt="system",
        user_prompt="original task",
        response_model=StageResult,
    )

    assert result.stage_id == "problem_identification"
    assert metadata.attempts == 2
    assert len(calls) == 2
    assert "JSON Schema" in calls[0]["messages"][0]["content"]
    assert "上一次回复未通过结构校验" in calls[1]["messages"][1]["content"]
    assert "原始论文内容" not in calls[1]["messages"][1]["content"]


def test_adapter_normalizes_common_nested_contract_aliases():
    payload = _stage_payload()
    payload["obligations"] = [{
        "id": "o-1",
        "description": "check goal",
        "status": "fulfilled",
        "evidence_refs": ["e-1"],
    }]
    payload["claims"] = [{
        "id": "c-1",
        "statement": "the goal is identified",
        "conclusion": "SUPPORTED",
        "rationale": "redundant model prose",
        "obligation_refs": ["o-1"],
        "evidence_refs": ["e-1"],
    }]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )
    )
    adapter = OpenAICompatibleAdapter(
        _settings(),
        client_factory=lambda **kw: httpx.Client(transport=transport, **kw),
    )

    result, _ = adapter.complete_json(
        system_prompt="system",
        user_prompt="user",
        response_model=StageResult,
    )

    assert result.obligations[0].text == "check goal"
    assert result.obligations[0].fulfilled is True
    assert result.claims[0].exact_text == "the goal is identified"
    assert result.claims[0].requested_verdict.value == "SUPPORTED"
