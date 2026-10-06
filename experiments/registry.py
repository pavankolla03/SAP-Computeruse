"""Experiment registry for tracking training runs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ExperimentRegistry:
    """Track experiments via a simple YAML/JSON registry."""

    def __init__(self, registry_path: str = "experiments/registry.json") -> None:
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                self.experiments: dict[str, dict[str, Any]] = json.load(f)
        else:
            self.experiments = {}

    def _save(self) -> None:
        with open(self.registry_path, "w") as f:
            json.dump(self.experiments, f, indent=2, default=str)

    def register(self, name: str, config: dict[str, Any]) -> str:
        experiment_id = f"exp-{len(self.experiments)+1:04d}"
        self.experiments[experiment_id] = {
            "id": experiment_id,
            "name": name,
            "config": config,
            "created_at": datetime.utcnow().isoformat(),
            "status": "registered",
        }
        self._save()
        logger.info("Registered experiment %s: %s", experiment_id, name)
        return experiment_id

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        return self.experiments.get(experiment_id)

    def list_all(self) -> dict[str, dict[str, Any]]:
        return dict(self.experiments)
