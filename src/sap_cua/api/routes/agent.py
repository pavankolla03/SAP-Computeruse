"""Agent API using the same execution and verification loop as evaluation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from sap_cua.agent.agent_loop import AgentLoop

router = APIRouter()


class RunRequest(BaseModel):
    instruction: str = Field(min_length=1)
    max_steps: int = Field(10, ge=1, le=100)
    model_type: str = "mock"
    verification: dict[str, Any] | None = None


class RunResponse(BaseModel):
    task_id: str
    success: bool
    steps: list[dict[str, Any]]
    duration_ms: int
    verification: dict[str, Any]
    backend: str
    error: str | None = None


@router.post("/run", response_model=RunResponse)
def run_agent(req: RunRequest) -> RunResponse:
    # Synchronous handler runs in FastAPI's thread pool instead of blocking its event loop.
    loop = AgentLoop(model=req.model_type, max_steps=req.max_steps)
    result = loop.run(req.instruction, verification=req.verification)
    return RunResponse(task_id=str(uuid.uuid4()), success=result["success"],
                       steps=result["actions"], duration_ms=result["duration_ms"],
                       verification=result["verification"], backend=result["backend"],
                       error=result["error"])
