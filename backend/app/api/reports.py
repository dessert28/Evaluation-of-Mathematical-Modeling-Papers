from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.recommendation_edits import RecommendationEditError, RecommendationEditService
from backend.app.services.report_builder import ReportBuilder
from backend.app.services.review_results import ReviewResultService


class RecommendationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1)
    acceptance: str = Field(min_length=1)
    priority: str = Field(default="minor")
    owner: str | None = None
    decided_by: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


def create_report_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/reviews", tags=["reports"])

    def store(request: Request):
        return request.app.state.review_job_repository

    @router.get("/{review_id}/report")
    def report(review_id: str, request: Request, format: str = "json"):
        builder = ReportBuilder(ReviewResultService(store(request)))
        try:
            if format == "md":
                return PlainTextResponse(builder.as_markdown(review_id), media_type="text/markdown; charset=utf-8")
            if format != "json":
                return JSONResponse(status_code=422, content={"error": {"code": "invalid_report_format", "message": "format 必须是 md 或 json", "details": {}}})
            return builder.as_json(review_id)
        except ValueError as exc:
            return JSONResponse(status_code=404, content={"error": {"code": "report_not_found", "message": str(exc), "details": {}}})

    @router.get("/{review_id}/evidence/{evidence_id}")
    def evidence(review_id: str, evidence_id: str, request: Request):
        result = ReviewResultService(store(request)).load(review_id)
        if result is None:
            return JSONResponse(status_code=404, content={"error": {"code": "result_not_found", "message": "评审结果不存在", "details": {}}})
        item = next((value for value in result.evidence if value.id == evidence_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": {"code": "evidence_not_found", "message": "证据不存在", "details": {}}})
        payload = item.model_dump(mode="json")
        asset_store = getattr(request.app.state, "asset_store", None)
        if asset_store is not None and item.asset_id and item.block_id:
            asset = asset_store.get(item.asset_id)
            block = next((block for block in (asset.blocks if asset else ()) if block.block_id == item.block_id), None)
            if block is not None:
                payload["document_block"] = block.as_dict()
        return payload

    @router.put("/{review_id}/recommendations/{recommendation_id}")
    def edit_recommendation(review_id: str, recommendation_id: str, body: RecommendationUpdate, request: Request):
        try:
            result = RecommendationEditService(store(request)).update(review_id, recommendation_id, **body.model_dump())
            return result.to_snapshot()
        except RecommendationEditError as exc:
            code = exc.code
            return JSONResponse(status_code=404 if code.endswith("not_found") else 422, content={"error": {"code": code, "message": str(exc), "details": {}}})

    return router


router = create_report_router()
