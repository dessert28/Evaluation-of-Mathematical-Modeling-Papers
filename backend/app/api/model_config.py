from __future__ import annotations

from typing import Any

import httpx
import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.model_config import ModelConfigInput
from backend.app.services.model_config import ModelConfigError, ModelConfigService
from backend.app.services.llm_adapter import OpenAICompatibleAdapter


class ModelConfigRequest(ModelConfigInput):
    pass


def _error(exc: ModelConfigError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": str(exc), "details": {}}})


def create_model_config_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/model-config", tags=["model-config"])

    def service(request: Request) -> ModelConfigService:
        item = getattr(request.app.state, "model_config_service", None)
        if item is None:
            raise ModelConfigError("model_config_unavailable", "模型配置服务未配置", 503)
        return item

    @router.get("")
    def list_configs(request: Request):
        try:
            item = service(request)
            return {"presets": item.presets(), "items": item.list_public()}
        except ModelConfigError as exc:
            return _error(exc)

    @router.post("", status_code=201)
    def create_config(body: ModelConfigRequest, request: Request):
        try:
            return service(request).create(body)
        except ModelConfigError as exc:
            return _error(exc)

    @router.put("/{config_id}")
    def update_config(config_id: str, body: ModelConfigRequest, request: Request):
        try:
            value = service(request).update(config_id, body)
            if value is None:
                return JSONResponse(status_code=404, content={"error": {"code": "model_config_not_found", "message": "模型配置不存在", "details": {}}})
            return value
        except ModelConfigError as exc:
            return _error(exc)

    @router.delete("/{config_id}")
    def delete_config(config_id: str, request: Request):
        try:
            if not service(request).delete(config_id):
                return JSONResponse(status_code=404, content={"error": {"code": "model_config_not_found", "message": "模型配置不存在", "details": {}}})
            return {"deleted": True}
        except ModelConfigError as exc:
            return _error(exc)

    @router.post("/{config_id}/test")
    def test_config(config_id: str, request: Request):
        try:
            item = service(request)
            public = item.get_public(config_id)
            if public is None:
                return JSONResponse(status_code=404, content={"error": {"code": "model_config_not_found", "message": "模型配置不存在", "details": {}}})
            secret = item.repository.get_secret(config_id)
            key = item._decrypt(secret) if secret else ""
            endpoint = OpenAICompatibleAdapter(item.settings.model_copy(update={'openai_compatible_base_url': public['base_url']})).endpoint
            payload = {"model": public["model"], "messages": [{"role": "user", "content": "Return JSON: {\"ok\":true}"}], "temperature": 0, "response_format": {"type": "json_object"}}
            headers = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            with httpx.Client(timeout=item.settings.llm_timeout_seconds) as client:
                response = client.post(endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                return JSONResponse(status_code=502, content={"error": {"code": "model_connection_failed", "message": f"模型服务返回 HTTP {response.status_code}", "details": {}}})
            try:
                content = response.json()['choices'][0]['message']['content']
                if not isinstance(content, str) or not isinstance(json.loads(content), dict):
                    raise ValueError('invalid JSON object')
            except (ValueError, TypeError, KeyError, IndexError):
                return JSONResponse(status_code=502, content={'error': {'code': 'model_response_invalid', 'message': '模型未返回兼容格式的 JSON 对象', 'details': {}}})
            return {"ok": True, "provider": public["provider"], "model": public["model"]}
        except ModelConfigError as exc:
            return _error(exc)
        except (httpx.HTTPError, TimeoutError):
            return JSONResponse(status_code=502, content={"error": {"code": "model_connection_failed", "message": "模型服务连接失败", "details": {}}})

    return router


router = create_model_config_router()
