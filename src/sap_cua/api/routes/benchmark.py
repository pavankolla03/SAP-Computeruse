"""Benchmark API endpoint."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sap_cua.evaluation.sapbench.runner import run_benchmark

logger = logging.getLogger(__name__)
router = APIRouter()


class BenchmarkRequest(BaseModel):
    suite: str = "sapbench-v1"
    model_type: str = "mock"
    output_dir: str = "results/"
    runs_per_task: int = 3


class BenchmarkResponse(BaseModel):
    summary: dict[str, Any]


@router.post("/run", response_model=BenchmarkResponse)
async def run_benchmark_api(req: BenchmarkRequest) -> BenchmarkResponse:
    summary = run_benchmark(
        suite=req.suite,
        model_type=req.model_type,
        output_dir=req.output_dir,
        runs_per_task=req.runs_per_task,
    )
    return BenchmarkResponse(summary=summary)
