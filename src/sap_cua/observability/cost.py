"""Cost tracking and budget enforcement."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# GPU hourly rates in USD
GPU_HOURLY_RATES: dict[str, float] = {
    "H100": 2.0,
    "A100": 1.5,
    "A10": 0.6,
}

# Storage cost per GB per month in USD
STORAGE_COST_PER_GB_MONTH: float = 0.023

# vLLM inference: cost per 1M tokens (approximate)
VLLM_INFERENCE_COST_PER_1M_TOKENS: float = 0.5


@dataclass
class UsageRecord:
    """Single cost usage record."""

    model: str
    gpu_hours: float = 0.0
    storage_gb: float = 0.0
    external_api_calls: int = 0
    external_api_cost: float = 0.0
    inference_tokens: int = 0


class CostTracker:
    """Tracks costs across models and enforces budgets."""

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._max_job_cost: float | None = None
        env_max = os.environ.get("MAX_JOB_COST_USD")
        if env_max is not None:
            try:
                self._max_job_cost = float(env_max)
            except ValueError:
                logger.warning("Invalid MAX_JOB_COST_USD: %s", env_max)

    # ── Estimation ──────────────────────────────────────────────────────────

    def estimate_job_cost(self, config: dict[str, Any]) -> float:
        """Estimate USD cost for a job described by *config*."""
        gpu_type = config.get("gpu_type", "A10")
        gpu_hours = float(config.get("gpu_hours", 0.0))
        storage_gb = float(config.get("storage_gb", 0.0))
        api_calls = int(config.get("external_api_calls", 0))
        api_cost = float(config.get("external_api_cost", 0.0))
        tokens = int(config.get("inference_tokens", 0))

        gpu_rate = GPU_HOURLY_RATES.get(gpu_type.upper(), GPU_HOURLY_RATES["A10"])
        gpu_cost = gpu_rate * gpu_hours
        storage_cost = (storage_gb / 30.0) * STORAGE_COST_PER_GB_MONTH
        inference_cost = (tokens / 1_000_000.0) * VLLM_INFERENCE_COST_PER_1M_TOKENS
        return gpu_cost + storage_cost + inference_cost + api_cost

    # ── Recording ───────────────────────────────────────────────────────────

    def record_usage(
        self,
        model: str,
        gpu_hours: float = 0.0,
        storage_gb: float = 0.0,
        external_api_calls: int = 0,
        external_api_cost: float = 0.0,
        inference_tokens: int = 0,
    ) -> UsageRecord:
        record = UsageRecord(
            model=model,
            gpu_hours=gpu_hours,
            storage_gb=storage_gb,
            external_api_calls=external_api_calls,
            external_api_cost=external_api_cost,
            inference_tokens=inference_tokens,
        )
        self._records.append(record)
        return record

    # ── Spend queries ───────────────────────────────────────────────────────

    def get_total_spend(self) -> float:
        total = 0.0
        for rec in self._records:
            gpu_rate = GPU_HOURLY_RATES.get(rec.model.upper().split("_")[0], GPU_HOURLY_RATES["A10"])
            total += gpu_rate * rec.gpu_hours
            total += (rec.storage_gb / 30.0) * STORAGE_COST_PER_GB_MONTH
            total += (rec.inference_tokens / 1_000_000.0) * VLLM_INFERENCE_COST_PER_1M_TOKENS
            total += rec.external_api_cost
        return round(total, 6)

    def get_spend_by_model(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for rec in self._records:
            gpu_rate = GPU_HOURLY_RATES.get(rec.model.upper().split("_")[0], GPU_HOURLY_RATES["A10"])
            cost = gpu_rate * rec.gpu_hours
            cost += (rec.storage_gb / 30.0) * STORAGE_COST_PER_GB_MONTH
            cost += (rec.inference_tokens / 1_000_000.0) * VLLM_INFERENCE_COST_PER_1M_TOKENS
            cost += rec.external_api_cost
            totals[rec.model] = totals.get(rec.model, 0.0) + cost
        return {k: round(v, 6) for k, v in totals.items()}

    # ── Budget enforcement ──────────────────────────────────────────────────

    def check_budget(self, max_cost_usd: float, estimated_cost: float) -> bool:
        """Return True if *estimated_cost* is within *max_cost_usd*."""
        effective_max = self._max_job_cost if self._max_job_cost is not None else max_cost_usd
        return estimated_cost <= effective_max
