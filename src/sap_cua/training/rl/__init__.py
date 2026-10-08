"""SAP-CUA Reinforcement Learning (GRPO-style) module with rewards and verifier-based scoring."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


REWARD = {
    "correct_package_created": 1.0,
    "correct_iflow_created": 2.0,
    "correct_sender": 2.0,
    "correct_receiver": 2.0,
    "deployment_successful": 5.0,
    "functional_test_successful": 10.0,
    "mpl_completed": 5.0,
    "correct_recovery": 5.0,
    "unnecessary_gui_action": -0.05,
    "wrong_component": -1.0,
    "deployment_failure": -2.0,
    "modification_of_unrelated_object": -10.0,
    "credential_leakage": -100.0,
    "unauthorized_destructive_action": -100.0,
}


def reward_function(
    outcome: dict[str, Any],
    action_history: list[dict[str, Any]] | None = None,
) -> float:
    """Compute total reward from a rollout outcome."""
    score = 0.0
    if outcome.get("package_created"):
        score += REWARD["correct_package_created"]
    if outcome.get("iflow_created"):
        score += REWARD["correct_iflow_created"]
    if outcome.get("sender_correct"):
        score += REWARD["correct_sender"]
    if outcome.get("receiver_correct"):
        score += REWARD["correct_receiver"]
    if outcome.get("deployed"):
        score += REWARD["deployment_successful"]
    if outcome.get("mpl_success"):
        score += REWARD["mpl_completed"]
    if outcome.get("functional_test_passed"):
        score += REWARD["functional_test_successful"]
    if outcome.get("recovery_succeeded"):
        score += REWARD["correct_recovery"]

    for event in outcome.get("negative_events", []):
        score += REWARD.get(event, -1.0)

    gui_actions = sum(1 for a in (action_history or []) if a.get("executor") == "gui")
    api_actions = sum(1 for a in (action_history or []) if a.get("executor") == "sap_api")
    if api_actions > 0 and gui_actions > api_actions * 3:
        score += REWARD["unnecessary_gui_action"] * (gui_actions - api_actions)

    return score


class RLTrainer:
    """GRPO-style RL training for SAP-CUA."""

    def __init__(
        self,
        base_model: str,
        output_path: str,
        suite_path: str = "datasets/sapbench-v1",
        config: dict | None = None,
    ) -> None:
        self.base_model = base_model
        self.output_path = Path(output_path)
        self.suite_path = Path(suite_path)
        self.config = config or {}
        logger.info("RLTrainer: base=%s suite=%s", base_model, suite_path)

    def run_episode(
        self,
        task: dict[str, Any],
        agent_runner: Callable[[dict[str, Any]], dict[str, Any]],
        max_steps: int = 50,
    ) -> dict[str, Any]:
        """Run a single RL episode."""
        try:
            outcome = agent_runner(task)
        except Exception as exc:
            logger.warning("Episode failed: %s", exc)
            outcome = {"success": False, "error": str(exc)}
        score = reward_function(outcome, outcome.get("action_history", []))
        return {
            "task_id": task.get("task_id", "unknown"),
            "outcome": outcome,
            "reward": score,
        }

    def train(self, episodes: int = 1000) -> dict[str, Any]:
        raise NotImplementedError("RL policy optimization is not implemented. Episode scoring does not train weights.")
