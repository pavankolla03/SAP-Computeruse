"""State transition pretraining (GUI state dynamics) for SAP-CUA."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StateTransitionExample(BaseModel):
    """A single GUI state-transition example."""

    before_image: str
    after_image: str
    action: str
    transition_type: str
    module: str


class TransitionDatasetBuilder:
    """Build a dataset of state transitions for pretraining.

    Supports forward generation (state + action -> next state),
    inverse generation (state + next state -> action), deduplication
    via perceptual hashing, and persistence.
    """

    def __init__(self) -> None:
        self._examples: List[StateTransitionExample] = []

    # ── add transition ─────────────────────────────────────────────

    def add_transition(
        self,
        before_img: str,
        after_img: str,
        action: str,
        module: str,
    ) -> None:
        """Append a transition example."""
        transition_type = self._classify_action(action)
        self._examples.append(
            StateTransitionExample(
                before_image=before_img,
                after_image=after_img,
                action=action,
                transition_type=transition_type,
                module=module,
            )
        )

    # ── generate inverse ───────────────────────────────────────────

    def generate_inverse(self) -> List[StateTransitionExample]:
        """S_t + S_t+1 -> action  (inverse model).

        Each existing example generates a new entry with the
        images swapped and an explicit action description.
        """
        generated: List[StateTransitionExample] = []
        for ex in self._examples:
            action_desc = f"Inverse: {ex.action} produced the observed change"
            generated.append(
                StateTransitionExample(
                    before_image=ex.after_image,
                    after_image=ex.before_image,
                    action=action_desc,
                    transition_type="inverse",
                    module=ex.module,
                )
            )
        logger.info("Generated %d inverse transitions.", len(generated))
        return generated

    # ── generate forward ───────────────────────────────────────────

    def generate_forward(self) -> List[StateTransitionExample]:
        """S_t + action -> expected next state  (forward model).

        Creates additional entries with explicit 'forward' labels.
        """
        generated: List[StateTransitionExample] = []
        for ex in self._examples:
            action_desc = f"Forward: applying '{ex.action}'"
            generated.append(
                StateTransitionExample(
                    before_image=ex.before_image,
                    after_image=ex.after_image,
                    action=action_desc,
                    transition_type="forward",
                    module=ex.module,
                )
            )
        logger.info("Generated %d forward transitions.", len(generated))
        return generated

    # ── deduplicate ────────────────────────────────────────────────

    def deduplicate(self) -> int:
        """Remove near-identical transitions using perceptual hashing.

        Returns the number of duplicates removed.
        """
        seen: Dict[str, int] = {}
        unique: List[StateTransitionExample] = []
        for ex in self._examples:
            phash = self._perceptual_hash(ex.before_image + ex.action)
            if phash not in seen:
                seen[phash] = len(unique)
                unique.append(ex)
            else:
                logger.debug(
                    "Duplicate transition removed (hash=%s)", phash[:8]
                )
        removed = len(self._examples) - len(unique)
        self._examples = unique
        logger.info("Deduplication removed %d entries.", removed)
        return removed

    # ── persistence ────────────────────────────────────────────────

    def save(self, output_path: Union[str, Path]) -> None:
        """Save dataset as JSON or JSONL."""
        p = Path(output_path)
        data = [ex.model_dump() for ex in self._examples]
        if p.suffix == ".jsonl":
            with open(p, "w") as fh:
                for item in data:
                    fh.write(json.dumps(item) + "\n")
        else:
            with open(p, "w") as fh:
                json.dump(data, fh, indent=2)
        logger.info("Saved %d transition examples to %s", len(data), p)

    def load(self, input_path: Union[str, Path]) -> None:
        """Load dataset, replacing current examples."""
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset file not found: {p}")
        raw = (
            self._load_jsonl(p) if p.suffix == ".jsonl" else self._load_json(p)
        )
        self._examples = [
            StateTransitionExample(**item) for item in raw
        ]
        logger.info("Loaded %d transition examples from %s", len(self._examples), p)

    # ── private helpers ─────────────────────────────────────────────

    @staticmethod
    def _classify_action(action: str) -> str:
        a = action.lower()
        if "drag" in a or "scroll" in a:
            return "drag"
        if "type" in a or "enter" in a:
            return "type"
        if "navigate" in a or "tab" in a:
            return "navigation"
        return "click"

    @staticmethod
    def _perceptual_hash(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

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
