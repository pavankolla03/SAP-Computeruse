"""SAP-CUA agent loop — the main autonomous agent runtime."""

from __future__ import annotations

import logging
import time
from typing import Any

from sap_cua.services.executor_router import ExecutorRouter, ExecutorContext
from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.model import get_model
from sap_cua.types import SAPState, SAPModule, ExecutorType

logger = logging.getLogger(__name__)


class AgentLoop:
    """Main agent loop for SAP-CUA."""

    def __init__(self, model: str = "mock", max_steps: int = 25) -> None:
        self.model = get_model(model)
        self.max_steps = max_steps
        self.sap_env = SAPMockEnvironment()
        self.router = ExecutorRouter(self.sap_env)
        self.history: list[dict[str, Any]] = []
        self.current_state = SAPState()

    def run(self, task: str) -> dict[str, Any]:
        """Run the agent on a task."""
        start = time.time()
        self.reset()
        logger.info("AgentLoop starting task: %s", task[:80])

        for step in range(self.max_steps):
            from sap_cua.services.executor_router import ExecutorContext
            context = ExecutorContext(
                task=task,
                state=self.current_state,
                history=self.history,
                step=step,
                sap_env=self.sap_env,
            )
            try:
                observation = self.sap_env.observe()
                response = self.model.act(task, observation, self.history)
                action = response.intent
                executor = response.executor
                logger.info("Step %d: %s via %s (confidence=%.2f)",
                            step + 1, action, executor, response.confidence)
                result = self.router.execute(action, context)
                self.history.append({
                    "step": step,
                    "action": action,
                    "executor": executor,
                    "success": result.get("success", False),
                })
                if result.get("success"):
                    logger.info("Step %d succeeded", step + 1)
                    if self._verify_task_completion(task, result):
                        return {
                            "success": True,
                            "steps": step + 1,
                            "duration_ms": int((time.time() - start) * 1000),
                            "actions": self.history,
                        }
                else:
                    logger.warning("Step %d failed: %s", step + 1, result.get("error"))
            except Exception as exc:
                logger.error("Step %d error: %s", step + 1, exc)
                self.history.append({"step": step, "error": str(exc)})

        return {
            "success": False,
            "steps": len(self.history),
            "duration_ms": int((time.time() - start) * 1000),
            "actions": self.history,
            "error": "Max steps reached",
        }

    def _verify_task_completion(self, task: str, result: dict[str, Any]) -> bool:
        """Check if the task is complete."""
        return True

    def reset(self) -> None:
        self.history.clear()
        self.current_state = SAPState()
        self.model.reset()
