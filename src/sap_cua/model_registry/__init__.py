"""Model checkpoint registry with versioning."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelCheckpoint:
    """Registry entry for a model checkpoint."""
    name: str
    version: str
    base_model: str = ""
    dataset_version: str = ""
    git_commit: str = ""
    training_config: dict[str, Any] = field(default_factory=dict)
    learning_rate: float = 0.0
    lora_config: dict[str, Any] = field(default_factory=dict)
    gpu_type: str = ""
    training_cost: float = 0.0
    eval_scores: dict[str, float] = field(default_factory=dict)
    license: str = "MIT"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class ModelRegistry:
    """Versioned model checkpoint registry. Never overwrites."""

    def __init__(self, data_dir: str = "model_registry/data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file = self.data_dir / "registry.json"
        self._entries: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._registry_file.exists():
            try:
                self._entries = json.loads(self._registry_file.read_text())
            except Exception:
                self._entries = {}

    def _save(self) -> None:
        self._registry_file.write_text(json.dumps(self._entries, indent=2, default=str))

    def _make_key(self, name: str, version: str) -> str:
        return f"{name}@{version}"

    def register_checkpoint(self, checkpoint: ModelCheckpoint) -> str:
        key = self._make_key(checkpoint.name, checkpoint.version)
        if key in self._entries:
            version_num = len([k for k in self._entries if k.startswith(checkpoint.name + "@")])
            new_version = f"{checkpoint.version}.{version_num + 1}"
            key = self._make_key(checkpoint.name, new_version)
            checkpoint.version = new_version
        self._entries[key] = {
            "checkpoint_id": checkpoint.checkpoint_id,
            "name": checkpoint.name,
            "version": checkpoint.version,
            "base_model": checkpoint.base_model,
            "dataset_version": checkpoint.dataset_version,
            "git_commit": checkpoint.git_commit,
            "training_config": checkpoint.training_config,
            "learning_rate": checkpoint.learning_rate,
            "lora_config": checkpoint.lora_config,
            "gpu_type": checkpoint.gpu_type,
            "training_cost": checkpoint.training_cost,
            "eval_scores": checkpoint.eval_scores,
            "license": checkpoint.license,
            "created_at": checkpoint.created_at,
        }
        self._save()
        logger.info("Registered model: %s", key)
        return key

    def get_checkpoint(self, name: str, version: str) -> dict[str, Any] | None:
        return self._entries.get(self._make_key(name, version))

    def list_checkpoints(self, name: str | None = None) -> list[dict[str, Any]]:
        entries = list(self._entries.values())
        if name:
            entries = [e for e in entries if e.get("name") == name]
        return sorted(entries, key=lambda e: e.get("created_at", ""))

    def get_latest(self, name: str) -> dict[str, Any] | None:
        matching = self.list_checkpoints(name)
        return matching[-1] if matching else None

    def update_eval_scores(self, name: str, version: str, scores: dict[str, float]) -> None:
        key = self._make_key(name, version)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(f"Checkpoint {key} not found")
        entry.setdefault("eval_scores", {}).update(scores)
        self._save()

    def delete_checkpoint(self, name: str, version: str) -> bool:
        key = self._make_key(name, version)
        if key not in self._entries:
            return False
        del self._entries[key]
        self._save()
        return True
