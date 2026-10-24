"""FastAPI application factory for native local execution."""

from __future__ import annotations

import hmac
import json
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .api.assets import router as assets_router
from .api.errors import register_error_handlers
from .api.health import router as health_router
from .api.rubrics import create_rubric_router
from .api.reviews import create_review_router
from .api.model_config import create_model_config_router
from .api.reports import create_report_router
from .db import init_db
from .db import SqlAlchemyAssetStore, SqlAlchemyRubricRepository, SqlAlchemyReviewJobRepository, SqlAlchemyModelConfigRepository
from .services.asset_inventory import AssetInventory
from .services.debate_engine import DebateRunManager, DebateService
from .services.debate_panel import DebatePanelStore
from .services.prompt_templates import PromptTemplateStore
from .services.review_run_manager import ReviewRunManager
from .services.model_config import ModelConfigService
from .services.llm_adapter import OpenAICompatibleAdapter
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    app = FastAPI(title="Math Modeling Paper Review Agent", version="0.1.0")
    app.state.settings = config
    app.state.engine = init_db(config)
    register_error_handlers(app)
    app.include_router(health_router)

    app.state.asset_inventory = AssetInventory(config.data_dir, max_bytes=config.max_upload_bytes)
    app.state.asset_store = SqlAlchemyAssetStore(config)
    app.state.rubric_repository = SqlAlchemyRubricRepository(config)
    app.state.review_job_repository = SqlAlchemyReviewJobRepository(config)
    app.state.model_config_repository = SqlAlchemyModelConfigRepository(config)
    app.state.model_config_service = ModelConfigService(config, app.state.model_config_repository)
    app.state.model_config_service.initialize()
    app.state.llm_adapter = OpenAICompatibleAdapter(
        config,
        settings_provider=app.state.model_config_service.runtime_settings,
        metadata_provider=app.state.model_config_service.runtime_metadata,
    )
    # Multi-agent debate (v0.1): the service performs the synchronous debate and
    # the run manager submits it as a background, idempotent task.  Both are
    # built before the review runner because the runner takes them as wiring.
    # The context builder mirrors AutomaticReviewRunner.build_context so the
    # debate panel sees the same paper text / evidence catalog / rubric as the
    # seven-stage review.

    def _debate_context_builder(job: Any) -> tuple[str, str, str]:
        asset = None
        paper_context = "（未提供）"
        try:
            asset = app.state.asset_store.get(job.asset_id)
            if asset is not None and getattr(getattr(asset, "status", None), "value", getattr(asset, "status", None)) == "parsed":
                blocks = sorted(getattr(asset, "blocks", ()), key=lambda b: b.block_order)
                parts: list[str] = []
                used = 0
                for block in blocks:
                    text = str(block.text or "")
                    chunk = f"[{block.block_id}] {text}\n"
                    if used + len(chunk) > 120_000:
                        remain = max(0, 120_000 - used)
                        if remain:
                            parts.append(chunk[:remain])
                        break
                    parts.append(chunk)
                    used += len(chunk)
                paper_context = "".join(parts) or "（空文档）"
        except Exception:
            paper_context = "（未提供）"
        # The engine validates each opinion's evidence_ids against the review's
        # real evidence entries (collected from stage_results), so the catalog
        # must list THOSE ids (and only those), not raw asset block ids.  Mirror
        # the same traversal DebateService._collect_evidence_ids uses.
        evidence_catalog = "（未提供）"
        try:
            snap = getattr(job, "state_snapshot", None)
            results = snap.get("stage_results") if isinstance(snap, dict) else getattr(snap, "stage_results", None)
            if isinstance(results, dict):
                results = list(results.values())
            rows: list[str] = []
            for result in results or []:
                evidence = result.get("evidence") if isinstance(result, dict) else getattr(result, "evidence", None)
                for item in evidence or []:
                    eid = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
                    if not eid:
                        continue
                    block_id = item.get("block_id") if isinstance(item, dict) else getattr(item, "block_id", None)
                    page = item.get("page") if isinstance(item, dict) else getattr(item, "page", None)
                    quote = item.get("quote") if isinstance(item, dict) else getattr(item, "quote", None)
                    row = f"[{eid}]"
                    if block_id:
                        row += f" block={block_id}"
                    if page is not None:
                        row += f" page={page}"
                    if quote:
                        row += f" quote={str(quote)[:300]}"
                    rows.append(row)
            if rows:
                evidence_catalog = "\n".join(rows)
        except Exception:
            evidence_catalog = "（未提供）"
        rubric_text = "（未提供）"
        try:
            rubric = app.state.rubric_repository.get(job.rubric_profile_id)
            if rubric is not None:
                criteria = getattr(rubric, "criteria", [])
                rubric_text = json.dumps(
                    {
                        "name": getattr(rubric, "name", ""),
                        "version": getattr(rubric, "version", ""),
                        "criteria": [
                            getattr(c, "model_dump", lambda: dict(c))() for c in criteria
                        ],
                    },
                    ensure_ascii=False,
                )
        except Exception:
            rubric_text = "（未提供）"
        return paper_context, evidence_catalog, rubric_text

    debate_service = DebateService(
        app.state.review_job_repository,
        adapter=app.state.llm_adapter,
        panel_store=DebatePanelStore(),
        prompt_store=PromptTemplateStore(),
        settings=config,
        context_builder=_debate_context_builder,
        max_workers=3,
    )
    app.state.debate_service = debate_service
    app.state.debate_runner = DebateRunManager(debate_service, max_workers=1)
    app.state.review_runner = ReviewRunManager(
        app.state.review_job_repository,
        app.state.asset_store,
        app.state.rubric_repository,
        config,
        adapter=app.state.llm_adapter,
        debate_service=debate_service,
        debate_runner=app.state.debate_runner,
    )
    app.include_router(assets_router)
    app.include_router(create_rubric_router(app.state.rubric_repository))
    app.include_router(create_review_router(app.state.review_job_repository))
    app.include_router(create_model_config_router())
    app.include_router(create_report_router())
    token = config.desktop_session_token.get_secret_value() if config.desktop_session_token else ""
    if token:
        @app.middleware("http")
        async def require_desktop_session(request, call_next):
            if request.url.path.startswith("/api/"):
                supplied = request.headers.get("X-Desktop-Token", "")
                if not hmac.compare_digest(supplied, token):
                    return JSONResponse(status_code=401, content={"error": {"code": "desktop_session_required", "message": "桌面应用会话已失效，请重新启动应用。", "details": {}}})
            return await call_next(request)

    frontend_root = Path(__file__).resolve().parents[2] / "frontend"
    dist_root = config.frontend_dist_dir.expanduser().resolve() if config.frontend_dist_dir else frontend_root / "dist"
    fallback_root = frontend_root / "static"
    desktop_mode = bool(token and config.desktop_api_base and dist_root.is_dir())
    if desktop_mode:
        @app.get("/", include_in_schema=False)
        def desktop_index():
            index_path = dist_root / "index.html"
            html = index_path.read_text(encoding="utf-8")
            bootstrap = "<script>window.__DESKTOP_API_BASE__=" + json.dumps(config.desktop_api_base) + ";window.__DESKTOP_SESSION_TOKEN__=" + json.dumps(token) + ";</script>"
            if "<!-- desktop-runtime -->" in html:
                html = html.replace("<!-- desktop-runtime -->", bootstrap, 1)
            else:
                html = html.replace("</head>", bootstrap + "</head>", 1)
            return HTMLResponse(html, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

        assets_root = dist_root / "assets"
        if assets_root.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_root), name="desktop-assets")
    elif dist_root.is_dir():
        app.mount("/", StaticFiles(directory=dist_root, html=True), name="frontend")
    elif fallback_root.is_dir():
        # Keep the local-first app usable when npm dependencies are unavailable.
        # The React/Vite source remains the primary development UI; this small
        # dependency-free shell is only a native preview fallback.
        app.mount("/", StaticFiles(directory=fallback_root, html=True), name="frontend-fallback")
    return app


app = create_app()
