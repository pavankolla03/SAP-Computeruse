"""Unit tests for the orchestrator service."""

from __future__ import annotations

import threading
import time

import pytest

from sap_cua.services.orchestrator import (
    Orchestrator,
    Task,
    TaskStatus,
    TaskPriority,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def orchestrator(tmp_path):
    return Orchestrator(db_path=tmp_path / "tasks.db")


@pytest.fixture()
def simple_runner():
    """A runner that always succeeds."""
    def _runner(task):
        return {"success": True, "output": "done", "task_id": task.task_id}
    return _runner


@pytest.fixture()
def failing_runner():
    """A runner that always raises."""
    call_count = {"n": 0}
    def _runner(task):
        call_count["n"] += 1
        raise RuntimeError("boom")
    _runner.call_count = call_count
    return _runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_submit_task_returns_task(orchestrator):
    task = orchestrator.submit_task(
        instruction="Create a sales order",
        model="test-model",
        max_steps=10,
    )
    assert isinstance(task, Task)
    assert task.instruction == "Create a sales order"
    assert task.model == "test-model"
    assert task.max_steps == 10
    assert task.status == TaskStatus.PENDING
    assert task.task_id


def test_get_task(orchestrator):
    task = orchestrator.submit_task(instruction="GET test")
    fetched = orchestrator.get_task(task.task_id)
    assert fetched is not None
    assert fetched.task_id == task.task_id
    assert fetched.instruction == "GET test"

    missing = orchestrator.get_task("nonexistent-id")
    assert missing is None


def test_list_tasks_filter(orchestrator):
    t1 = orchestrator.submit_task("Task 1")
    t2 = orchestrator.submit_task("Task 2")
    t3 = orchestrator.submit_task("Task 3")

    all_tasks = orchestrator.list_tasks()
    assert len(all_tasks) == 3

    pending = orchestrator.list_tasks(TaskStatus.PENDING)
    assert len(pending) == 3

    pending_str = orchestrator.list_tasks("pending")
    assert len(pending_str) == 3


def test_run_task(orchestrator, simple_runner):
    task = orchestrator.submit_task(instruction="Run me", model="fast")
    result = orchestrator.run_task(task.task_id, simple_runner)

    assert result["output"] == "done"
    updated = orchestrator.get_task(task.task_id)
    assert updated.status == TaskStatus.COMPLETED
    assert updated.duration is not None
    assert updated.duration >= 0


def test_cancel_task(orchestrator):
    task = orchestrator.submit_task(instruction="Cancel me")
    cancelled = orchestrator.cancel_task(task.task_id)
    assert cancelled is True
    assert orchestrator.get_task(task.task_id).status == TaskStatus.CANCELLED

    # Cannot cancel twice
    assert orchestrator.cancel_task(task.task_id) is False


def test_run_with_retries(orchestrator, failing_runner):
    task = orchestrator.submit_task(instruction="Fail test", max_steps=5)
    result = orchestrator.run_task(task.task_id, failing_runner, max_retries=3, retry_safe=True)

    assert result["error"] == "boom"
    assert result["attempts"] == 4  # Explicit opt-in: one attempt plus three safe retries
    updated = orchestrator.get_task(task.task_id)
    assert updated.status == TaskStatus.FAILED
    assert updated.retries == 3


def test_task_duration_tracking(orchestrator, simple_runner):
    task = orchestrator.submit_task(instruction="Timed")
    orchestrator.run_task(task.task_id, simple_runner)
    updated = orchestrator.get_task(task.task_id)
    assert updated.completed_at is not None
    assert updated.duration is not None
    assert updated.duration >= 0


def test_priority_ordering(orchestrator):
    """Lower-priority tasks are still stored; priority is preserved."""
    low = orchestrator.submit_task("Low", priority=TaskPriority.LOW)
    high = orchestrator.submit_task("High", priority=TaskPriority.HIGH)
    tasks = orchestrator.list_tasks()
    task_map = {t.instruction: t for t in tasks}
    assert task_map["Low"].priority == TaskPriority.LOW
    assert task_map["High"].priority == TaskPriority.HIGH


def test_run_unknown_task_raises(orchestrator, simple_runner):
    with pytest.raises(KeyError, match="Unknown task_id"):
        orchestrator.run_task("does-not-exist", simple_runner)


def test_default_does_not_replay_failed_mutations(orchestrator, failing_runner):
    task = orchestrator.submit_task("Mutation with unknown outcome")
    result = orchestrator.run_task(task.task_id, failing_runner)
    assert result["attempts"] == 1
    assert failing_runner.call_count["n"] == 1


def test_missing_success_flag_is_not_success(orchestrator):
    task = orchestrator.submit_task("Unverified task")
    orchestrator.run_task(task.task_id, lambda task: {"output": "maybe"})
    assert task.status == TaskStatus.FAILED


def test_persistence_survives_restart(tmp_path):
    path = tmp_path / "tasks.db"
    first = Orchestrator(db_path=path)
    task = first.submit_task("Persist me")
    first.run_task(task.task_id, lambda task: {"success": True, "steps": 2})
    restored = Orchestrator(db_path=path).get_task(task.task_id)
    assert restored.status == TaskStatus.COMPLETED
    assert restored.steps_taken == 2


def test_cancellation_is_not_overwritten(orchestrator):
    task = orchestrator.submit_task("Cancel during execution")
    def runner(task):
        orchestrator.cancel_task(task.task_id)
        return {"success": True}
    result = orchestrator.run_task(task.task_id, runner)
    assert result["success"] is False
    assert task.status == TaskStatus.CANCELLED
