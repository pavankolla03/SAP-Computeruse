"""SAP-CUA trajectory evaluation."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TrajectoryEvaluator:
    """Evaluates trajectory quality, action efficiency, and completion."""

    def evaluate(self, trajectory: dict[str, Any], ground_truth: dict[str, Any] | None = None) -> dict[str, Any]:
        steps = trajectory.get("steps", [])
        success = trajectory.get("success", False)

        # Step accuracy: fraction of steps that produced a verifiable result
        total = len(steps)
        verified = sum(1 for s in steps if s.get("verification", {}).get("success") is True)
        step_accuracy = verified / total if total else 0.0

        # Action efficiency: fewer steps to complete = higher score (capped at 1.0)
        optimal_steps = max(ground_truth.get("expected_steps", total) if ground_truth else total, 1)
        action_efficiency = min(optimal_steps / max(total, 1), 1.0)

        # Goal completion
        goal_completion = 1.0 if success else 0.0

        # Executor selection: did it pick the preferred executor?
        correct_choices = sum(
            1 for s in steps
            if s.get("executor_selection_correct", False) or "executor" in s
        )
        executor_selection = correct_choices / total if total else 0.0

        # Error recovery: did it recover from failures?
        errors = [s for s in steps if not s.get("success", True)]
        recoveries = [e for e in errors if e.get("recovered", False)]
        error_recovery = len(recoveries) / len(errors) if errors else 1.0

        return {
            "step_accuracy": round(step_accuracy, 4),
            "action_efficiency": round(action_efficiency, 4),
            "goal_completion": round(goal_completion, 4),
            "executor_selection": round(executor_selection, 4),
            "error_recovery": round(error_recovery, 4),
        }

    def compare_to_baseline(self, traj: dict[str, Any], baseline_traj: dict[str, Any]) -> dict[str, Any]:
        """Compute diff between traj and a baseline trajectory."""
        current = self.evaluate(traj)
        baseline = self.evaluate(baseline_traj)
        return {
            metric: {
                "current": current[metric],
                "baseline": baseline[metric],
                "delta": round(current[metric] - baseline[metric], 4),
            }
            for metric in current
        }

    def find_bottlenecks(self, traj: dict[str, Any]) -> list[dict[str, Any]]:
        """Return segments that are inefficient (long or redundant)."""
        bottlenecks: list[dict[str, Any]] = []
        steps = traj.get("steps", [])
        for i, step in enumerate(steps):
            duration = step.get("duration_ms", 0)
            if duration > 5000:
                bottlenecks.append({"step_index": i, "reason": "slow_step", "duration_ms": duration})
            if step.get("screenshot") and i > 0 and steps[i - 1].get("screenshot") == step.get("screenshot"):
                bottlenecks.append({"step_index": i, "reason": "redundant_screenshot"})
        return bottlenecks

    def score_against_expert(self, traj: dict[str, Any], expert_traj: dict[str, Any]) -> float:
        """Compute similarity score between agent and expert trajectories (0-1)."""
        eval_result = self.evaluate(traj)
        expert_result = self.evaluate(expert_traj)
        total = 0.0
        for metric in eval_result:
            total += abs(eval_result[metric] - expert_result[metric])
        return max(0.0, 1.0 - total / len(eval_result))
