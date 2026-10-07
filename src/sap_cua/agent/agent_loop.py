"""Bounded mock agent loop with execution and independent state verification."""

from __future__ import annotations

import time
from typing import Any

from sap_cua.model import ComputerUseModel, get_model
from sap_cua.sap.actions import get_action_definition
from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.security import sanitize_data
from sap_cua.services.executor_router import ExecutorContext, ExecutorRouter
from sap_cua.services.verifier import verify_task_state
from sap_cua.types import SAPAction, SAPState


class AgentLoop:
    """Shared runtime for the CLI, API, and mock benchmark.

    A successful action is recorded separately from completion of the task.
    Criteria must come from the caller's task definition, never from the model.
    """

    def __init__(self, model: str | ComputerUseModel = "mock", max_steps: int = 25,
                 *, sap_env: SAPMockEnvironment | None = None,
                 max_duration_ms: int = 300_000) -> None:
        if max_steps < 1 or max_duration_ms < 1:
            raise ValueError("Step and duration limits must be positive")
        self.model = get_model(model) if isinstance(model, str) else model
        self.max_steps = max_steps
        self.max_duration_ms = max_duration_ms
        self.sap_env = sap_env if sap_env is not None else SAPMockEnvironment()
        self.router = ExecutorRouter(api_available=True)
        self.history: list[dict[str, Any]] = []
        self.current_state = SAPState()

    def run(self, task: str, *, verification: dict[str, Any] | None = None,
            reset_environment: bool = True) -> dict[str, Any]:
        start = time.monotonic()
        self.reset(reset_environment=reset_environment)
        check: dict[str, Any] = {"success": False, "reason": "No actions executed"}
        error = "Max steps reached without verified completion"
        for step in range(self.max_steps):
            if (time.monotonic() - start) * 1000 >= self.max_duration_ms:
                error = "Task duration limit reached"
                break
            try:
                observation = sanitize_data(self.sap_env.observe())
                response = self.model.act(task, observation, self.history)
                definition = get_action_definition(response.intent)
                action = SAPAction(
                    intent=response.intent, executor=response.executor,
                    arguments=response.arguments, gui_action=response.gui_action,
                    confidence=response.confidence,
                    expected_state=definition.expected_state if definition else "",
                    risk=definition.risk.value if definition else "high",
                )
                context = ExecutorContext(task=task, state=self.current_state,
                                          history=self.history, step=step, sap_env=self.sap_env)
                result = self.router.execute(action, context)
                check = verify_task_state(self.sap_env, verification)
                self.history.append(sanitize_data({
                    "step": step, "action": action.intent,
                    "action_data": action.model_dump(mode="json"),
                    "executor": result.get("executor", response.executor),
                    "backend": result.get("backend"), "success": result.get("success") is True,
                    "result": result, "verification": check,
                }))
                if (time.monotonic() - start) * 1000 >= self.max_duration_ms:
                    error = "Task duration limit reached"
                    break
                if result.get("success") is True and check.get("success") is True:
                    return self._result(True, start, check)
            except Exception as exc:
                self.history.append(sanitize_data({"step": step, "success": False, "error": str(exc)}))
        if verification is None:
            error = "Task is unverified: no task verification criteria supplied"
        return self._result(False, start, check, error)

    def _result(self, success: bool, start: float, verification: dict[str, Any],
                error: str | None = None) -> dict[str, Any]:
        return sanitize_data({
            "success": success, "steps": len(self.history),
            "duration_ms": int((time.monotonic() - start) * 1000),
            "actions": list(self.history), "verification": verification,
            "backend": "mock", "error": error,
        })

    def reset(self, *, reset_environment: bool = True) -> None:
        self.history.clear()
        self.current_state = SAPState()
        self.model.reset()
        if reset_environment:
            self.sap_env.reset()
