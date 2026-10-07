"""SAP-CUA recorder module — captures human/agent SAP actions for training data."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RecorderEvent:
    """A single recorded event."""
    timestamp: float
    event_type: str
    data: dict[str, Any]
    screenshot: str | None = None
    cursor_x: float | None = None
    cursor_y: float | None = None
    application: str | None = None
    url: str | None = None
    dom_snapshot: str | None = None
    accessibility_tree: str | None = None


@dataclass
class RecorderSession:
    """A recording session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str | None = None
    mode: str = "human_demonstration"
    status: str = "active"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    ended_at: str | None = None
    events: list[RecorderEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SAPRecorder:
    """Records SAP actions for training data generation."""

    def __init__(self, storage_dir: str = "datasets/raw/recordings") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.session: RecorderSession | None = None
        self._current_task: str = ""
        self._mark_success: bool = False
        self._mark_failure: bool = False

    def start(self, task: str, mode: str = "human_demonstration") -> RecorderSession:
        self._current_task = task
        self._mark_success = False
        self._mark_failure = False
        self.session = RecorderSession(
            task_id=task,
            mode=mode,
            status="recording",
            metadata={"start_time": time.time()},
        )
        logger.info("Started recording session for task: %s", task)
        return self.session

    def record_event(
        self,
        event_type: str,
        data: dict[str, Any],
        screenshot: str | None = None,
        cursor: tuple[float, float] | None = None,
        application: str | None = None,
        url: str | None = None,
        dom: str | None = None,
        a11y: str | None = None,
    ) -> RecorderEvent:
        if self.session is None:
            raise RuntimeError("Recording session not started")
        event = RecorderEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data,
            screenshot=screenshot,
            cursor_x=cursor[0] if cursor else None,
            cursor_y=cursor[1] if cursor else None,
            application=application,
            url=url,
            dom_snapshot=dom,
            accessibility_tree=a11y,
        )
        self.session.events.append(event)
        return event

    def mark_success(self) -> None:
        self._mark_success = True

    def mark_failure(self) -> None:
        self._mark_failure = True

    def pause(self) -> None:
        if self.session:
            self.session.status = "paused"

    def stop(self) -> RecorderSession:
        if self.session is None:
            raise RuntimeError("No active session")
        self.session.status = "completed"
        self.session.ended_at = datetime.utcnow().isoformat()
        self.session.metadata["success"] = self._mark_success
        self.session.metadata["failure"] = self._mark_failure
        self._save_session()
        logger.info("Stopped recording session: %s (%d events)", self.session.session_id, len(self.session.events))
        completed = self.session
        self.session = None
        return completed

    def _save_session(self) -> None:
        if self.session is None:
            return
        session_file = self.storage_dir / f"{self.session.session_id}.json"
        data = {
            "session_id": self.session.session_id,
            "task_id": self.session.task_id,
            "mode": self.session.mode,
            "status": self.session.status,
            "started_at": self.session.started_at,
            "ended_at": self.session.ended_at,
            "metadata": self.session.metadata,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "data": e.data,
                    "screenshot": e.screenshot,
                    "cursor_x": e.cursor_x,
                    "cursor_y": e.cursor_y,
                    "application": e.application,
                    "url": e.url,
                }
                for e in self.session.events
            ],
        }
        from sap_cua.security import sanitize_data
        session_file.write_text(json.dumps(sanitize_data(data), indent=2))
        logger.info("Saved session: %s", session_file)


from sap_cua.recorder.processor import TrajectoryProcessor as _TrajectoryProcessor


class TrajectoryProcessor(_TrajectoryProcessor):
    """Compatibility wrapper around the shared sanitized processor."""

    def process(self, session_data: dict[str, Any]) -> dict[str, Any]:
        return self.process_session(session_data)

    def save(self, trajectory: dict[str, Any], name: str) -> Path:
        return Path(super().save(trajectory, name))
