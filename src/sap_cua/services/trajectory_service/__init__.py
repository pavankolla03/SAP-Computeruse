"""Sanitized trajectory files with a rebuildable SQLite metadata index."""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from sap_cua.security import sanitize_data


class TrajectoryStore:
    """JSON files are authoritative; SQLite is a rebuildable local index.

    Each rollout receives its own ID even when multiple rollouts share a task.
    This store does not certify image redaction or training-data eligibility.
    """

    def __init__(self, base_dir: str = "datasets/sanitized/trajectories", *,
                 root_dir: str | Path | None = None, db_path: str | Path | None = None) -> None:
        self.base_dir = Path(root_dir if root_dir is not None else base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path) if db_path is not None else self.base_dir / "index.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, dict[str, Any]] = {}
        self._load_index()

    def _metadata(self, tid: str, path: Path, data: dict[str, Any]) -> dict[str, Any]:
        return {"trajectory_id": tid, "task_id": data.get("task_id", ""),
                "path": str(path), "success": data.get("success") is True,
                "task": data.get("task", data.get("instruction", "")),
                "model": data.get("model", ""), "difficulty": data.get("difficulty", ""),
                "module": data.get("module", "")}

    def _load_index(self) -> None:
        for path in self.base_dir.glob("*.json"):
            if path.is_symlink():
                continue
            # Corrupt files fail visibly; silently skipping them hides lost data.
            data = sanitize_data(json.loads(path.read_text()))
            self._index[path.stem] = self._metadata(path.stem, path, data)
        self._sync_index()

    def _sync_index(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS trajectories (id TEXT PRIMARY KEY, metadata TEXT NOT NULL)")
            db.execute("DELETE FROM trajectories")
            db.executemany("INSERT INTO trajectories VALUES (?, ?)",
                           [(tid, json.dumps(meta)) for tid, meta in self._index.items()])

    def save_trajectory(self, trajectory: dict[str, Any]) -> str:
        data = sanitize_data(trajectory)
        tid = "traj_" + uuid.uuid4().hex
        path = self.base_dir / f"{tid}.json"
        # Exclusive creation prevents accidental overwrite.
        with path.open("x") as stream:
            stream.write(json.dumps(data, indent=2))
        self._index[tid] = self._metadata(tid, path, data)
        self._sync_index()
        return tid

    def load_trajectory(self, trajectory_id: str) -> dict[str, Any] | None:
        entry = self._index.get(trajectory_id)
        if entry is None:
            return None
        path = Path(entry["path"])
        if path.is_symlink():
            raise ValueError("Trajectory files cannot be symbolic links")
        return sanitize_data(json.loads(path.read_text()))

    def list_trajectories(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        results = [dict(value) for value in self._index.values()]
        for key, value in (filters or {}).items():
            if key == "task":
                results = [r for r in results if value.lower() in r.get("task", "").lower()]
            else:
                results = [r for r in results if r.get(key) == value]
        return results

    def search_trajectories(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [r for r in self.list_trajectories()
                if q in r.get("task_id", "").lower() or q in r.get("task", "").lower()]

    def delete_trajectory(self, trajectory_id: str) -> bool:
        entry = self._index.get(trajectory_id)
        if entry is None:
            return False
        Path(entry["path"]).unlink()
        del self._index[trajectory_id]
        self._sync_index()
        return True

    def get_statistics(self) -> dict[str, Any]:
        records = list(self._index.values())
        successes = sum(r["success"] for r in records)
        return {"total": len(records), "successful": successes,
                "failed": len(records) - successes,
                "success_rate": successes / max(len(records), 1),
                "by_model": dict(Counter(r["model"] for r in records)),
                "by_difficulty": dict(Counter(r["difficulty"] for r in records))}

    def export_to_jsonl(self) -> list[dict[str, Any]]:
        return [self.load_trajectory(tid) for tid in self._index]
