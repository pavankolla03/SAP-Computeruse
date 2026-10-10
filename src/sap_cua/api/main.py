"""Local workbench. Loopback binding, strict host/origin checks, private session."""

from __future__ import annotations

import hmac
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from sap_cua.services.workbench import (
    RunStore,
    Workflow,
    capabilities,
    example_workflow,
    execute_workflow,
)


def create_app(data_dir: Path | None = None, *, test_mode: bool = False, rag_service=None) -> FastAPI:
    directory = data_dir or Path(os.getenv("SAP_CUA_DATA_DIR", ".sap-cua"))
    token = secrets.token_urlsafe(32)
    web = Path(__file__).parents[1] / "web"

    @asynccontextmanager
    async def lifespan(app):
        from sap_cua.runtime.sap_api.connection import ConnectionService
        app.state.sap = ConnectionService()
        app.state.store = RunStore(directory)
        app.state.store.recover_interrupted()
        from sap_cua.engineering.service import RAGService
        app.state.rag = rag_service if rag_service is not None else RAGService.from_environment(app.state.store)
        yield

    app = FastAPI(
        title="SAP-CUA Workbench", version="0.3.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )
    hosts = ["127.0.0.1", "localhost", "[::1]"] + (["testserver"] if test_mode else [])

    @app.middleware("http")
    async def local_session(request: Request, call_next):
        public = request.url.path in ("/", "/health/", "/health") or request.url.path.startswith(
            "/assets/"
        )
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are not allowed"}, 403)
        if not public:
            if not hmac.compare_digest(request.cookies.get("sap_cua_session", ""), token):
                return JSONResponse({"detail": "Open the local workbench to start a session"}, 401)
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and request.headers.get("x-sap-cua") != "workbench"
            ):
                return JSONResponse({"detail": "Missing request header"}, 403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.url.path == "/":
            response.set_cookie("sap_cua_session", token, httponly=True, samesite="strict")
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)
    app.mount("/assets", StaticFiles(directory=web), name="assets")

    @app.get("/")
    def home():
        return FileResponse(web / "index.html")

    @app.get("/health")
    @app.get("/health/")
    def health():
        return {"status": "healthy", "version": "0.3.0"}

    @app.get("/api/capabilities")
    def status():
        return capabilities()

    @app.get("/api/example")
    def example():
        return example_workflow()

    @app.get("/api/runs")
    def runs(request: Request):
        return [run for run in request.app.state.store.list() if "customer" not in run]

    @app.get("/api/runs/{run_id}")
    def run(run_id: str, request: Request):
        result = request.app.state.store.get(run_id)
        if result is None or "customer" in result:
            raise HTTPException(404, "Run not found")
        return result

    @app.post("/api/runs", status_code=201)
    def execute(workflow: Workflow, request: Request):
        try:
            return execute_workflow(workflow, request.app.state.store)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    from sap_cua.api.routes.rag import router as rag_router
    app.include_router(rag_router, prefix="/api/rag")
    from sap_cua.api.routes.sap import router as sap_router
    app.include_router(sap_router,prefix="/api/sap")
    return app


app = create_app()
