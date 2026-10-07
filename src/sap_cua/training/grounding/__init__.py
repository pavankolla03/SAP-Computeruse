"""SAP grounding dataset builder."""

import hashlib
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GroundingExample(BaseModel):
    """Single grounding (instruction-to-element) example."""

    image_path: str
    instruction: str
    target: Dict[str, Union[List[float], Dict[str, float]]]
    module: str
    confidence: float = Field(ge=0.0, le=1.0)


class GroundingDatasetBuilder:
    """Build and manage a grounding dataset for SAP-CUA training.

    Examples can be added individually, auto-generated from DOM
    snapshots, augmented, split, saved, and loaded.
    """

    def __init__(self) -> None:
        self._examples: List[GroundingExample] = []

    # ── add examples ───────────────────────────────────────────────

    def add_example(
        self,
        image_path: str,
        instruction: str,
        target: Dict[str, Any],
        module: str,
        confidence: float = 1.0,
    ) -> None:
        """Append a new grounding example."""
        self._examples.append(
            GroundingExample(
                image_path=image_path,
                instruction=instruction,
                target=target,
                module=module,
                confidence=confidence,
            )
        )

    def add_from_screenshot(
        self,
        image_path: str,
        element_selector: str,
        instruction: str,
        module: str,
    ) -> None:
        """Auto-generate a bbox from a CSS selector and add the example.

        When a real DOM is unavailable a synthetic bbox is generated.
        """
        bbox = self._bbox_from_selector(element_selector, image_path)
        self.add_example(
            image_path=image_path,
            instruction=instruction,
            target={"bbox": bbox},
            module=module,
        )

    # ── augmentation ───────────────────────────────────────────────

    def augment(self, resolution: Optional[Tuple[int, int]] = None, zoom_level: float = 1.0) -> List[GroundingExample]:
        """Return augmented copies of every example.

        *resolution* rescales the image; *zoom_level* simulates zoom.
        Augmented examples share the same target but carry ``confidence``
        slightly reduced to indicate synthetic origin.
        """
        augmented: List[GroundingExample] = []
        for ex in self._examples:
            new_conf = round(ex.confidence * 0.9, 2)
            suffix = f"_aug_z{zoom_level}"
            img = (
                f"{ex.image_path.rsplit('.', 1)[0]}{suffix}."
                f"{ex.image_path.rsplit('.', 1)[1]}"
                if "." in ex.image_path
                else ex.image_path + suffix
            )
            augmented.append(
                GroundingExample(
                    image_path=img,
                    instruction=ex.instruction,
                    target=ex.target,
                    module=ex.module,
                    confidence=new_conf,
                )
            )
        logger.info("Augmented %d examples (zoom=%.1f)", len(augmented), zoom_level)
        return augmented

    # ── split ──────────────────────────────────────────────────────

    def split(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
    ) -> Dict[str, List[GroundingExample]]:
        """Return train / validation / test splits."""
        random.seed(42)
        shuffled = self._examples[:]
        random.shuffle(shuffled)
        n = len(shuffled)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)
        return {
            "train": shuffled[:train_end],
            "validation": shuffled[train_end:val_end],
            "test": shuffled[val_end:],
        }

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
        logger.info("Saved %d examples to %s", len(data), p)

    def load(self, input_path: Union[str, Path]) -> None:
        """Load dataset from JSON or JSONL, replacing current examples."""
        p = Path(input_path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset file not found: {p}")
        raw = (
            self._load_jsonl(p) if p.suffix == ".jsonl" else self._load_json(p)
        )
        self._examples = [
            GroundingExample(**item) for item in raw
        ]
        logger.info("Loaded %d examples from %s", len(self._examples), p)

    # ── statistics ─────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Return counts and distribution by SAP module."""
        total = len(self._examples)
        by_module: Dict[str, int] = {}
        for ex in self._examples:
            by_module[ex.module] = by_module.get(ex.module, 0) + 1
        return {
            "total_examples": total,
            "by_module": by_module,
            "avg_confidence": round(
                sum(ex.confidence for ex in self._examples) / max(total, 1), 3
            ),
        }

    # ── filtering ──────────────────────────────────────────────────

    def filter_by_confidence(self, min_confidence: float) -> None:
        """Remove examples below *min_confidence*."""
        before = len(self._examples)
        self._examples = [
            ex for ex in self._examples if ex.confidence >= min_confidence
        ]
        logger.info(
            "Filtered by confidence>=%.2f: %d -> %d examples",
            min_confidence,
            before,
            len(self._examples),
        )

    # ── private helpers ─────────────────────────────────────────────

    @staticmethod
    def _bbox_from_selector(selector: str, image_path: str) -> List[float]:
        """Produce a synthetic bbox from a CSS selector string."""
        h = hash(selector + image_path)
        x1 = abs(h) % 800
        y1 = abs(h >> 4) % 600
        w = abs(h >> 8) % 100 + 50
        ht = abs(h >> 12) % 40 + 20
        return [x1, y1, x1 + w, y1 + ht]

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
