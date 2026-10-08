from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SemanticStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    action: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    preferred_executor: Literal[
        "sap_api", "mcp", "template", "playwright", "browser_mouse", "computer_use"
    ] = "sap_api"
    fallback_executors: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high", "critical"] = "medium"
    permission: str = "integration_developer"
    preconditions: list[str] = Field(default_factory=list)
    verification: dict[str, Any] = Field(default_factory=dict)
    rollback: str = "Delete only run-owned sandbox resources after verification"
    source_ids: list[str] = Field(default_factory=list)


class SemanticPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    requirement: str
    planner: str
    backend: Literal["sandbox", "sap_api"] = "sandbox"
    customer: str
    tenant: str
    pattern: str
    steps: list[SemanticStep]
    sources: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    max_recovery_attempts: int = Field(2, ge=0, le=5)
    max_task_cost_usd: float = Field(0, ge=0, le=100)
    max_seconds: int = Field(120, ge=1, le=1800)
    requires_live_validation: bool = True
