"""SAP-CUA FastAPI main application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sap_cua.api.routes import health, agent, benchmark, recorder, models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SAP-CUA API v%s", "0.1.0")
    yield
    logger.info("Shutting down SAP-CUA API")


app = FastAPI(
    title="SAP-CUA API",
    description="SAP-Native 7B Computer-Use Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])
app.include_router(benchmark.router, prefix="/benchmark", tags=["benchmark"])
app.include_router(recorder.router, prefix="/recorder", tags=["recorder"])
app.include_router(models.router, prefix="/models", tags=["models"])
