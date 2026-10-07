"""Multi-tier memory system for SAP-CUA agents.

Provides short-term, task, long-term, and episodic memory tiers with
secret detection, LRU eviction, and pruning.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sap_cua.security import redact_secrets

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Memory tiers."""

    SHORT_TERM = "short_term"
    TASK = "task"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"


@dataclass
class MemoryEntry:
    """A single memory entry."""

    timestamp: float
    key: str
    value: Any
    memory_type: MemoryType
    importance: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "key": self.key,
            "value": self.value,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
        }


class Memory:
    """Multi-tier agent memory.

    Tiers:
    - **short_term**: Current task context (LRU-bounded to 256 entries).
    - **task**: Artefacts, aliases, deployment state for the current task.
    - **long_term**: Persistent patterns and config across sessions.
    - **episodic**: Completed task summaries.

    Secret detection is applied on every store and values matching
    secret patterns are rejected.
    """

    _SHORT_TERM_CAP = 256

    def __init__(self, task_id: str = "") -> None:
        self._task_id = task_id
        self._lock = threading.Lock()
        self._short_term: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._task_store: dict[str, MemoryEntry] = {}
        self._long_term: dict[str, MemoryEntry] = {}
        self._episodic: list[MemoryEntry] = []

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def store(self, key: str, value: Any, memory_type: MemoryType = MemoryType.SHORT_TERM, importance: float = 0.5) -> None:
        """Store *value* under *key* in the specified memory tier.

        Raises ``ValueError`` if the value contains a secret.
        """
        self._check_secret(value)
        entry = MemoryEntry(
            timestamp=time.time(),
            key=key,
            value=value,
            memory_type=memory_type,
            importance=importance,
        )
        with self._lock:
            if memory_type == MemoryType.SHORT_TERM:
                self._short_term[key] = entry
                self._short_term.move_to_end(key)
                if len(self._short_term) > self._SHORT_TERM_CAP:
                    oldest = next(iter(self._short_term))
                    del self._short_term[oldest]
            elif memory_type == MemoryType.TASK:
                self._task_store[key] = entry
            elif memory_type == MemoryType.LONG_TERM:
                self._long_term[key] = entry
            elif memory_type == MemoryType.EPISODIC:
                self._episodic.append(entry)

    def recall(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key, searching tiers in priority order."""
        with self._lock:
            if key in self._short_term:
                self._short_term.move_to_end(key)
                return self._short_term[key]
            if key in self._task_store:
                return self._task_store[key]
            if key in self._long_term:
                return self._long_term[key]
            for ep in self._episodic:
                if ep.key == key:
                    return ep
        return None

    # ------------------------------------------------------------------
    # Context getters
    # ------------------------------------------------------------------

    def get_short_term_context(self) -> dict[str, Any]:
        """Return the current short-term context as a dict."""
        with self._lock:
            return {k: e.value for k, e in self._short_term.items()}

    def get_task_context(self) -> dict[str, Any]:
        """Return task-level memory as a dict."""
        with self._lock:
            return {k: e.value for k, e in self._task_store.items()}

    def get_long_term_patterns(self) -> list[dict[str, Any]]:
        """Return long-term memory entries as a list of dicts."""
        with self._lock:
            return [e.to_dict() for e in self._long_term.values()]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear_short_term(self) -> None:
        """Clear the short-term buffer."""
        with self._lock:
            self._short_term.clear()

    def prune_old(self, age_seconds: float) -> int:
        """Remove entries older than *age_seconds* from short-term memory.

        Returns the number of entries removed.
        """
        cutoff = time.time() - age_seconds
        with self._lock:
            to_remove = [k for k, e in self._short_term.items() if e.timestamp < cutoff]
            for k in to_remove:
                del self._short_term[k]
        logger.debug("Pruned %d short-term entries", len(to_remove))
        return len(to_remove)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _check_secret(value: Any) -> None:
        """Raise ValueError if *value* contains a secret."""
        text = str(value)
        if not text:
            return
        redacted, findings = redact_secrets(text)
        if findings:
            raise ValueError(
                f"Secret detected in memory value; {len(findings)} finding(s): "
                + ", ".join(f["type"] for f in findings)
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._short_term) + len(self._task_store) + len(self._long_term) + len(self._episodic)

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"Memory(short={len(self._short_term)}, task={len(self._task_store)}, "
                f"long={len(self._long_term)}, episodic={len(self._episodic)})"
            )
