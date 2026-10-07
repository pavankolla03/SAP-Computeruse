"""Dataset versioning and management."""

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
class DatasetVersion:
    name: str
    version: str
    source: str = ""
    license: str = "MIT"
    sanitization: str = ""
    num_examples: int = 0
    duplicates_removed: int = 0
    modules_covered: list[str] = field(default_factory=list)
    tenant_distribution: list[str] = field(default_factory=list)
    train_split: int = 0
    val_split: int = 0
    test_split: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class DatasetRegistry:
    """Versioned dataset registry with leakage prevention."""

    def __init__(self, data_dir: str = "datasets/registry") -> None:
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

    def _key(self, name: str, version: str) -> str:
        return f"{name}@{version}"

    def register_dataset(self, ds: DatasetVersion) -> str:
        key = self._key(ds.name, ds.version)
        self._entries[key] = {
            "dataset_id": ds.dataset_id,
            "name": ds.name,
            "version": ds.version,
            "source": ds.source,
            "license": ds.license,
            "sanitization": ds.sanitization,
            "num_examples": ds.num_examples,
            "duplicates_removed": ds.duplicates_removed,
            "modules_covered": ds.modules_covered,
            "tenant_distribution": ds.tenant_distribution,
            "train_split": ds.train_split,
            "val_split": ds.val_split,
            "test_split": ds.test_split,
            "created_at": ds.created_at,
        }
        self._save()
        logger.info("Registered dataset: %s", key)
        return key

    def get_dataset(self, name: str, version: str) -> dict[str, Any] | None:
        return self._entries.get(self._key(name, version))

    def list_datasets(self) -> list[dict[str, Any]]:
        return list(self._entries.values())

    def get_versions(self, name: str) -> list[str]:
        return sorted([k.split("@")[1] for k in self._entries if k.startswith(name + "@")])

    def check_leakage(self, train_ids: set[str], test_ids: set[str]) -> dict[str, Any]:
        overlap = train_ids & test_ids
        return {
            "has_leakage": bool(overlap),
            "overlap_count": len(overlap),
            "overlap_ids": list(overlap)[:10],
        }
