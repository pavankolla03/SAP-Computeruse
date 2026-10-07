"""Orchestrator — coordinates long-running agent tasks with retry, priorities, and tracking."""

from __future__ import annotations

import logging
import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path

from sap_cua.security import sanitize_data
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class TaskPriority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instruction: str = ""
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    model: str = "mock"
    checkpoint: str = ""
    max_steps: int = 25
    priority: int = 0
    retries: int = 0
    error: Optional[str] = None
    steps_taken: int = 0
    duration_ms: int = 0


    @property
    def duration(self) -> float | None:
        return self.duration_ms / 1000 if self.completed_at is not None else None


class Orchestrator:
    """Coordinates local tasks with optional SQLite persistence."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._tasks: dict[str, Task] = {}
        self._running: dict[str, bool] = {}
        self._lock = threading.RLock()
        self.db_path = Path(db_path) if db_path is not None else None
        if self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                for (payload,) in db.execute("SELECT payload FROM tasks"):
                    data = json.loads(payload)
                    data["status"] = TaskStatus(data["status"])
                    task = Task(**data)
                    # Interrupted work is never silently replayed after restart.
                    if task.status == TaskStatus.RUNNING:
                        task.status = TaskStatus.FAILED
                        task.error = "Interrupted before completion; requires reconciliation"
                    self._tasks[task.task_id] = task

    def _save(self, task: Task) -> None:
        if self.db_path is not None:
            payload = json.dumps(sanitize_data(asdict(task)))
            with sqlite3.connect(self.db_path) as db:
                db.execute("INSERT OR REPLACE INTO tasks VALUES (?, ?)", (task.task_id, payload))

    def submit_task(self, instruction: str, model: str = "mock",
                    max_steps: int = 25, priority: int = 0) -> Task:
        task = Task(
            instruction=instruction, model=model, max_steps=max_steps, priority=priority,
        )
        self._tasks[task.task_id] = task
        self._save(task)
        logger.info("Submitted task %s: %s", task.task_id, instruction[:60])
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda t: t.started_at or "", reverse=True)

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc).isoformat()
        self._running.pop(task_id, None)
        self._save(task)
        logger.info("Cancelled task %s", task_id)
        return True

    def run_task(self, task_id: str, agent_runner: Callable[[Task], dict[str, Any]], *,
                 max_retries: int = 0, retry_safe: bool = False) -> dict[str, Any]:
        """Run a task; retries require an explicit idempotency/reconciliation decision."""
        if max_retries < 0 or (max_retries and not retry_safe):
            raise ValueError("Retries require retry_safe=True and a nonnegative limit")
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(f"Unknown task_id: {task_id}")
            if task.status != TaskStatus.PENDING:
                return {"success": False, "error": "Task not runnable", "attempts": 0}
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc).isoformat()
            self._running[task_id] = True
            self._save(task)
        start = time.monotonic()
        result: dict[str, Any] = {"success": False, "error": "Task cancelled"}
        attempts = 0
        try:
            for attempt in range(max_retries + 1):
                if task.status == TaskStatus.CANCELLED:
                    break
                attempts += 1
                task.retries = attempt
                try:
                    result = sanitize_data(agent_runner(task))
                    if not isinstance(result, dict):
                        raise TypeError("Task runner must return an object")
                    if result.get("success") is True:
                        break
                    result.setdefault("error", "Runner did not report verified success")
                except Exception as exc:
                    result = sanitize_data({"success": False, "error": str(exc)})
            if task.status == TaskStatus.CANCELLED:
                result = {"success": False, "error": "Task cancelled"}
            else:
                task.status = TaskStatus.COMPLETED if result.get("success") is True else TaskStatus.FAILED
            result["attempts"] = attempts
            task.result = result
            task.error = result.get("error")
        finally:
            task.duration_ms = int((time.monotonic() - start) * 1000)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            step_count = result.get("steps", 0)
            task.steps_taken = len(step_count) if isinstance(step_count, list) else step_count
            self._running.pop(task_id, None)
            self._save(task)
        return result

    def get_statistics(self) -> dict[str, Any]:
        total = len(self._tasks)
        by_status: dict[str, int] = {}
        for task in self._tasks.values():
            by_status[task.status.value] = by_status.get(task.status.value, 0) + 1
        completed = [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
        avg_duration = sum(t.duration_ms for t in completed) / max(len(completed), 1)
        return {
            "total": total,
            "by_status": by_status,
            "avg_duration_ms": int(avg_duration),
            "running": sum(1 for v in self._running.values() if v),
        }
