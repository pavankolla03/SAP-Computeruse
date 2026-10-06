"""Recorder API endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def recorder_status() -> dict[str, Any]:
    return {"status": "idle", "recording": False, "mode": "human_demonstration"}
