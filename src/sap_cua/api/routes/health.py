"""Health check endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from sap_cua import __version__

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check() -> JSONResponse:
    return JSONResponse({"status": "healthy", "version": __version__})
