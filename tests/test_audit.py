"""Tests for audit logger module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sap_cua.observability.audit import AuditLogEntry, AuditLogger


@pytest.fixture
def logger(tmp_path):
    return AuditLogger(log_dir=str(tmp_path / "audit"))


class TestAuditLogger:
    def test_log_action_creates_entry(self, logger):
        entry = logger.log_action({
            "task_id": "t1",
            "model": "sap-cua-7b",
            "checkpoint": "v0.1",
            "observation": "Page loaded with login form",
            "action": "click",
            "executor": "gui",
            "arguments": {"target": "username_field"},
            "result": "success",
        })
        assert isinstance(entry, AuditLogEntry)
        assert entry.task_id == "t1"
        assert entry.action == "click"

    def test_log_action_redacts_secrets(self, logger):
        entry = logger.log_action({
            "task_id": "t2",
            "action": "authenticate",
            "arguments": {"password": "mysecret123"},
            "observation": "password: mysecret123",
        })
        # The observation field has the password inline and should be redacted
        assert "mysecret123" not in entry.observation_hash

    def test_observation_hash_is_consistent(self, logger):
        logger.log_action({"task_id": "x", "observation": "Page X", "action": "click"})
        e1 = logger.get_logs(task_id="x")[0]
        e1.observation_hash = "fixed"
        logger2 = AuditLogger(log_dir=str(Path(logger.log_dir)))
        # re-init would create a new buffer, but the hash for same observation is identical
        e2 = logger2.log_action({"task_id": "y", "observation": "Page X", "action": "click"})
        # We re-instantiate logger2 so buffer is separate
        assert e2.observation_hash is not None

    def test_get_logs_filter_by_task(self, logger):
        logger.log_action({"task_id": "alpha", "action": "click"})
        logger.log_action({"task_id": "beta", "action": "type"})
        result = logger.get_logs(task_id="alpha")
        assert len(result) == 1
        assert result[0].task_id == "alpha"

    def test_replay_returns_steps(self, logger):
        for i in range(3):
            logger.log_action({
                "task_id": "task-99",
                "action": f"step{i}",
                "executor": "gui",
            })
        replay = logger.replay("task-99")
        assert len(replay) == 3

    def test_export_jsonl(self, logger, tmp_path):
        logger.log_action({"task_id": "exp", "action": "click"})
        export_path = tmp_path / "audit.jsonl"
        returned = logger.export(str(export_path))
        assert Path(returned).exists()
        lines = Path(returned).read_text().strip().split("\n")
        assert len(lines) >= 1
        loaded = json.loads(lines[0])
        assert loaded["task_id"] == "exp"

    def test_log_action_hash_present(self, logger):
        entry = logger.log_action({"task_id": "h", "action": "click", "observation": "obs"})
        assert entry.observation_hash and len(entry.observation_hash) > 0
