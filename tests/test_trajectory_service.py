"""Unit tests for the trajectory service."""

from __future__ import annotations

import pytest

from sap_cua.services.trajectory_service import TrajectoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return TrajectoryStore(root_dir=tmp_path / "trajectories", db_path=tmp_path / "index.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_save_and_load(store):
    traj = {
        "task_id": "task-001",
        "instruction": "Create a sales order",
        "model": "test-model",
        "success": True,
        "difficulty": "easy",
        "module": "SD",
        "steps": [{"action": "click", "element": "button"}],
    }
    tid = store.save_trajectory(traj)
    assert tid.startswith("traj_")
    loaded = store.load_trajectory(tid)
    assert loaded is not None
    assert loaded["task_id"] == "task-001"
    assert loaded["success"] is True


def test_load_missing_returns_none(store):
    assert store.load_trajectory("nonexistent") is None


def test_list_trajectories_empty(store):
    assert store.list_trajectories() == []


def test_list_with_filters(store):
    store.save_trajectory({"task_id": "t1", "model": "m1", "success": True, "difficulty": "easy"})
    store.save_trajectory({"task_id": "t2", "model": "m1", "success": False, "difficulty": "easy"})
    store.save_trajectory({"task_id": "t3", "model": "m2", "success": True, "difficulty": "hard"})

    easy = store.list_trajectories({"difficulty": "easy"})
    assert len(easy) == 2

    model_m1 = store.list_trajectories({"model": "m1"})
    assert len(model_m1) == 2

    success = store.list_trajectories({"success": True})
    assert len(success) == 2


def test_search_trajectories(store):
    store.save_trajectory({"task_id": "task-001", "instruction": "Create a sales order"})
    store.save_trajectory({"task_id": "task-002", "instruction": "Delete a customer"})

    hits = store.search_trajectories("sales")
    assert len(hits) == 1
    assert hits[0]["task_id"] == "task-001"


def test_delete_trajectory(store):
    traj = {"task_id": "del-1", "model": "x"}
    tid = store.save_trajectory(traj)
    assert store.delete_trajectory(tid) is True
    assert store.load_trajectory(tid) is None
    assert store.delete_trajectory(tid) is False


def test_get_statistics(store):
    store.save_trajectory({"task_id": "s1", "model": "m1", "success": True, "difficulty": "easy"})
    store.save_trajectory({"task_id": "s2", "model": "m1", "success": False, "difficulty": "easy"})
    store.save_trajectory({"task_id": "s3", "model": "m2", "success": True, "difficulty": "hard"})

    stats = store.get_statistics()
    assert stats["total"] == 3
    assert abs(stats["success_rate"] - 2 / 3) < 0.01
    assert stats["by_model"]["m1"] == 2
    assert stats["by_difficulty"]["easy"] == 2


def test_export_to_jsonl(store):
    store.save_trajectory({"task_id": "e1", "model": "m1", "success": True})
    store.save_trajectory({"task_id": "e2", "model": "m2", "success": False})
    exported = store.export_to_jsonl()
    assert len(exported) == 2
    ids = {t["task_id"] for t in exported}
    assert ids == {"e1", "e2"}
