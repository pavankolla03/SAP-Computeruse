"""Audit logging for SAP actions."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sap_cua.security import redact_secrets

logger = logging.getLogger(__name__)


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    timestamp: str
    task_id: str
    model: str
    checkpoint: str
    observation_hash: str
    action: str
    executor: str
    arguments: dict[str, Any]
    sap_object: str | None = None
    result: str
    verifier_result: str | None = None
    risk: str = "low"
    approval_status: str = "pending"


class AuditLogger:
    """Append-only audit log for SAP agent actions."""

    def __init__(self, log_dir: str = "datasets/raw/audit") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: list[AuditLogEntry] = []

    def _hash_observation(self, observation: str) -> str:
        """Return SHA-256 hex digest of *observation* after redacting secrets."""
        redacted, _ = redact_secrets(observation or "")
        return hashlib.sha256(redacted.encode()).hexdigest()[:16]

    def log_action(self, action_data: dict[str, Any]) -> AuditLogEntry:
        """Write an audit entry from an action dict."""
        timestamp = datetime.now(timezone.utc).isoformat()
        observation = str(action_data.get("observation", ""))
        raw_args = action_data.get("arguments", {})

        # Redact secrets in dict values directly
        redacted_args = self._redact_dict(raw_args)

        entry = AuditLogEntry(
            timestamp=timestamp,
            task_id=action_data.get("task_id", "unknown"),
            model=action_data.get("model", "unknown"),
            checkpoint=action_data.get("checkpoint", ""),
            observation_hash=self._hash_observation(observation),
            action=action_data.get("action", ""),
            executor=action_data.get("executor", ""),
            arguments=redacted_args,
            sap_object=action_data.get("sap_object"),
            result=str(action_data.get("result", "")),
            verifier_result=str(action_data.get("verifier_result")) if action_data.get("verifier_result") is not None else None,
            risk=action_data.get("risk", "low"),
            approval_status=action_data.get("approval_status", "pending"),
        )
        self._buffer.append(entry)
        self._write_entry(entry)
        return entry

    _SENSITIVE_KEYS = {
        "password", "secret", "token", "api_key", "apikey", "private_key",
        "client_secret", "credential", "auth", "authorization", "bearer",
        "access_token", "refresh_token", "passwd", "pwd",
    }

    def _redact_dict(self, obj: Any) -> Any:
        """Recursively redact secret values in a dict/list structure."""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.lower() in self._SENSITIVE_KEYS and isinstance(v, str):
                    result[k] = "***REDACTED***"
                else:
                    result[k] = self._redact_dict(v)
            return result
        if isinstance(obj, list):
            return [self._redact_dict(v) for v in obj]
        if isinstance(obj, str):
            redacted, _ = redact_secrets(obj)
            return redacted
        return obj

    def _write_entry(self, entry: AuditLogEntry) -> None:
        task_dir = self.log_dir / entry.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        log_file = task_dir / "audit.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def get_logs(
        self,
        task_id: str | None = None,
        model: str | None = None,
        start_time: str | None = None,
    ) -> list[AuditLogEntry]:
        results: list[AuditLogEntry] = []
        for entry in self._buffer:
            if task_id and entry.task_id != task_id:
                continue
            if model and entry.model != model:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            results.append(entry)
        return results

    def replay(self, task_id: str) -> list[dict[str, Any]]:
        """Reconstruct a task execution as a list of step dicts."""
        logs = self.get_logs(task_id=task_id)
        return [entry.model_dump() for entry in sorted(logs, key=lambda e: e.timestamp)]

    def export(self, path: str) -> str:
        """Export all buffered entries to a JSONL file."""
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(entry.model_dump_json() + "\n")
        return str(path_obj)
