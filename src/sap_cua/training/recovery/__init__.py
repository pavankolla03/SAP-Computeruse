"""Failure recovery training data builder for SAP-CUA."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RecoveryExample(BaseModel):
    """A single failure-recovery training example."""

    failure_type: str
    before_state: Dict[str, Any]
    diagnosis: str
    remediation: str
    after_state: Dict[str, Any]
    actions: List[Dict[str, Any]]
    success: bool


class RecoveryDatasetBuilder:
    """Build a dataset of failure-recovery trajectories.

    Useful for training the agent to recover from common SAP errors
    (HTTP 401/403, timeouts, mapping errors, etc.).
    """

    def __init__(self) -> None:
        self._examples: List[RecoveryExample] = []

    # ── add failure ────────────────────────────────────────────────

    def add_failure(
        self,
        failure_type: str,
        before_state: Dict[str, Any],
        error_msg: str,
        remediation: str,
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Register a new failure/recovery trajectory."""
        self._examples.append(
            RecoveryExample(
                failure_type=failure_type,
                before_state=before_state,
                diagnosis=error_msg,
                remediation=remediation,
                after_state=self._project_after_state(before_state, remediation),
                actions=actions or [],
                success=True,
            )
        )

    # ── generate from MPL ──────────────────────────────────────────

    def generate_from_mpl(
        self, mpl_entries: List[Dict[str, Any]]
    ) -> List[RecoveryExample]:
        """Parse a list of MPL (Message Processing Log) dicts and generate
        recovery examples.

        Each MPL entry is expected to have ``error_code``,
        ``description``, and ``stack_trace`` keys.
        """
        generated: List[RecoveryExample] = []
        for entry in mpl_entries:
            error_code = entry.get("error_code", "UNKNOWN")
            desc = entry.get("description", "")
            ft = str(error_code)
            before_state = {
                "mpl_id": entry.get("mpl_id", "unknown"),
                "timestamp": entry.get("timestamp", ""),
                "status": "failed",
            }
            remediation = self._default_remediation(ft, desc)
            actions = self._default_actions(ft)
            generated.append(
                RecoveryExample(
                    failure_type=ft,
                    before_state=before_state,
                    diagnosis=desc,
                    remediation=remediation,
                    after_state={**before_state, "status": "recovered"},
                    actions=actions,
                    success=True,
                )
            )
        self._examples.extend(generated)
        logger.info(
            "Generated %d recovery examples from MPL entries.", len(generated)
        )
        return generated

    # ── augment ────────────────────────────────────────────────────

    def augment_variations(
        self, base_example: RecoveryExample
    ) -> List[RecoveryExample]:
        """Create variations of the same failure with paraphrased diagnoses."""
        templates = [
            f"Detected {base_example.failure_type} – reattempting with backoff",
            f"Error {base_example.failure_type} encountered – applying remediation",
            f"Recovering from {base_example.failure_type} failure",
        ]
        variations: List[RecoveryExample] = []
        for diag in templates:
            variations.append(
                RecoveryExample(
                    failure_type=base_example.failure_type,
                    before_state=base_example.before_state,
                    diagnosis=diag,
                    remediation=base_example.remediation,
                    after_state=base_example.after_state,
                    actions=base_example.actions[:],
                    success=base_example.success,
                )
            )
        return variations

    # ── persistence ────────────────────────────────────────────────

    def save(self, output_path: Union[str, Path]) -> None:
        """Persist dataset as JSON or JSONL."""
        p = Path(output_path)
        data = [ex.model_dump() for ex in self._examples]
        if p.suffix == ".jsonl":
            with open(p, "w") as fh:
                for item in data:
                    fh.write(json.dumps(item) + "\n")
        else:
            with open(p, "w") as fh:
                json.dump(data, fh, indent=2)
        logger.info("Saved %d recovery examples to %s", len(data), p)

    def load(self, input_path: Union[str, Path]) -> None:
        """Load dataset, replacing current examples."""
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset file not found: {p}")
        raw = (
            self._load_jsonl(p) if p.suffix == ".jsonl" else self._load_json(p)
        )
        self._examples = [RecoveryExample(**item) for item in raw]
        logger.info("Loaded %d recovery examples from %s", len(self._examples), p)

    # ── statistics ─────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Return distribution by failure type and success rate."""
        total = len(self._examples)
        by_type: Dict[str, int] = {}
        successes = 0
        for ex in self._examples:
            by_type[ex.failure_type] = by_type.get(ex.failure_type, 0) + 1
            if ex.success:
                successes += 1
        return {
            "total_examples": total,
            "by_failure_type": by_type,
            "success_rate": round(successes / max(total, 1), 3),
        }

    # ── private helpers ─────────────────────────────────────────────

    @staticmethod
    def _project_after_state(
        before: Dict[str, Any], remediation: str
    ) -> Dict[str, Any]:
        after = dict(before)
        after["status"] = "recovered"
        after["remediation"] = remediation
        return after

    @staticmethod
    def _default_remediation(ft: str, desc: str) -> str:
        remap = {
            "401": "Re-authenticate the user session and retry.",
            "403": "Refresh authorisation token and verify role assignment.",
            "timeout": "Increase request timeout and implement exponential backoff.",
            "mapping_error": "Verify RFC destination mapping and retry.",
        }
        return remap.get(ft, f"Investigate error '{ft}' and apply standard recovery procedure.")

    @staticmethod
    def _default_actions(ft: str) -> List[Dict[str, Any]]:
        return [{"action": "log_error", "params": {"code": ft}}, {"action": "retry", "params": {"max_attempts": 3}}]

    @staticmethod
    def _load_json(path: Path) -> list:
        with open(path) as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else data.get("data", [])

    @staticmethod
    def _load_jsonl(path: Path) -> list:
        items = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items
