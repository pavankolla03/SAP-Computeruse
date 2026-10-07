"""Trajectory processor — convert raw recordings to standardized training data."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sap_cua.security import redact_secrets, sanitize_data

logger = logging.getLogger(__name__)


class TrajectoryProcessor:
    """Process raw recordings into standardized training trajectories."""

    def __init__(self, storage_dir: str = "datasets/sanitized/trajectories") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def load_trajectory(self, path: str) -> dict[str, Any]:
        """Load a trajectory from a JSON file."""
        return json.loads(Path(path).read_text())

    def process_session(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """Convert raw session data into a standardized trajectory."""
        session_data = sanitize_data(session_data)
        events = session_data.get("events", [])
        steps = []
        before_state: dict[str, Any] | None = None
        for event in events:
            redacted_dict = event.get("data", {})
            semantic = self.extract_semantic_actions([event])
            step = {
                "before_state": before_state or {},
                "after_state": redacted_dict,
                "event_type": event.get("event_type"),
                "screenshot": event.get("screenshot"),
                "cursor": (event.get("cursor_x"), event.get("cursor_y")),
                "application": event.get("application"),
                "url": event.get("url"),
                "semantic_action": semantic[0] if semantic else None,
            }
            steps.append(step)
            before_state = redacted_dict
        success = session_data.get("metadata", {}).get("success", False)
        return {
            "task_id": session_data.get("task_id", "unknown"),
            "task": session_data.get("task_id", "unknown"),
            "environment": session_data.get("environment", {"product": "Integration Suite", "module": "Cloud Integration", "resolution": [1440, 900]}),
            "steps": self.deduplicate_steps(steps),
            "final_verification": {"success": success},
            "success": success,
        }

    def deduplicate_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove exact duplicate observations, preserving every action event."""
        deduped: list[dict[str, Any]] = []
        for step in steps:
            if (deduped and step == deduped[-1] and step.get("screenshot")
                    and not step.get("event_type") and not step.get("semantic_action")):
                continue
            deduped.append(step)
        return deduped

    def extract_semantic_actions(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert raw events to semantic action descriptions."""
        mapping = {
            "click": "CLICK_ELEMENT",
            "double_click": "DOUBLE_CLICK_ELEMENT",
            "right_click": "RIGHT_CLICK_ELEMENT",
            "type": "TYPE_TEXT",
            "key_press": "PRESS_KEY",
            "hotkey": "PRESS_HOTKEY",
            "scroll": "SCROLL",
            "drag": "DRAG",
            "wait": "WAIT",
        }
        results: list[dict[str, Any]] = []
        for event in sanitize_data(events):
            etype = event.get("event_type", "unknown")
            intent = mapping.get(etype, "UNKNOWN_ACTION")
            results.append({
                "intent": intent,
                "raw_event": event,
                "data": event.get("data", {}),
            })
        return results

    def compute_quality_score(self, trajectory: dict[str, Any]) -> float:
        """Return a quality score between 0 and 1."""
        scorer = QualityScorer()
        return scorer.overall_score(trajectory)

    def save(self, trajectory: dict[str, Any], path: str) -> str:
        """Sanitize and write trajectory to disk."""
        if not path or Path(path).name != path or path in (".", ".."):
            raise ValueError("Trajectory name must be a single filename")
        sanitized = json.dumps(sanitize_data(trajectory), ensure_ascii=False)
        file_path = self.storage_dir / f"{path}.json"
        file_path.write_text(sanitized)
        return str(file_path)


class QualityScorer:
    """Compute a composite quality score for a trajectory."""

    WEIGHTS = {
        "action_correctness": 0.30,
        "completeness": 0.25,
        "efficiency": 0.20,
        "no_secrets": 0.25,
    }

    def score_action_correctness(self, trajectory: dict[str, Any]) -> float:
        """Based on verifier results."""
        steps = trajectory.get("steps", [])
        if not steps:
            return 0.0
        correct = sum(1 for s in steps if s.get("verification", {}).get("success") is True)
        return correct / len(steps)

    def score_completeness(self, trajectory: dict[str, Any]) -> float:
        """Did it reach the goal?"""
        return 1.0 if trajectory.get("success") else 0.0

    def score_efficiency(self, trajectory: dict[str, Any]) -> float:
        """Fewer steps = better (normalized against 50-step reference)."""
        steps = len(trajectory.get("steps", []))
        return max(0.0, 1.0 - steps / 50.0)

    def score_no_secrets(self, trajectory: dict[str, Any]) -> float:
        """No leaked secrets = 1.0; any leak reduces score."""
        steps = trajectory.get("steps", [])
        if sanitize_data(steps) != steps:
            return 0.0
        raw = json.dumps(steps, default=str)
        _, findings = redact_secrets(raw)
        if not findings:
            return 1.0
        return max(0.0, 1.0 - 0.1 * len(findings))

    def overall_score(self, trajectory: dict[str, Any]) -> float:
        scores = {
            "action_correctness": self.score_action_correctness(trajectory),
            "completeness": self.score_completeness(trajectory),
            "efficiency": self.score_efficiency(trajectory),
            "no_secrets": self.score_no_secrets(trajectory),
        }
        return sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
