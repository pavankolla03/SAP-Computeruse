"""Agent run endpoint."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sap_cua.model import get_model
from sap_cua.services.executor_router import ExecutorRouter

logger = logging.getLogger(__name__)
router = APIRouter()


class RunRequest(BaseModel):
    instruction: str
    max_steps: int = 10
    model_type: str = "mock"


class RunResponse(BaseModel):
    task_id: str
    success: bool
    steps: list[dict[str, Any]]
    duration_ms: int


@router.post("/run", response_model=RunResponse)
async def run_agent(req: RunRequest) -> RunResponse:
    model = get_model(req.model_type)
    router_exec = ExecutorRouter(api_available=False)
    start = time.time()
    steps: list[dict[str, Any]] = []
    model.reset()
    success = False
    for step_num in range(req.max_steps):
        response = model.act(
            instruction=req.instruction,
            image=None,
            history=steps,
        )
        action_data = response.model_dump() if hasattr(response, "model_dump") else response
        steps.append(action_data)
        if response.confidence > 0.9 and step_num >= 2:
            success = True
            break
    duration_ms = int((time.time() - start) * 1000)
    return RunResponse(task_id="task-001", success=success, steps=steps, duration_ms=duration_ms)
