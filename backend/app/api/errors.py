"""Uniform API error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _json_safe(value: Any) -> Any:
    """Convert validation context values (including exceptions) to JSON-safe data."""

    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": _json_safe(details or {})}}


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, exc.details))


async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = dict(exc.detail) if isinstance(exc.detail, dict) else {"detail": exc.detail}
    nested_error = detail.get("error")
    if isinstance(nested_error, dict):
        return JSONResponse(status_code=exc.status_code, content={"error": _json_safe(nested_error)})
    code = str(detail.pop("code", "http_error")) if isinstance(detail, dict) else "http_error"
    message = str(detail.pop("message", exc.detail)) if isinstance(detail, dict) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, content=error_payload(code, message, detail))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if request.url.path.startswith('/api/v1/model-config'):
        # Pydantic includes rejected input, including secrets, in validation details.
        errors = [{'loc': error['loc'], 'type': error['type']} for error in errors]
    return JSONResponse(status_code=422, content=error_payload("validation_error", "请求参数校验失败", _json_safe(errors)))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
