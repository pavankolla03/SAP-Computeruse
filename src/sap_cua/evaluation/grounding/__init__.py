"""SAP-CUA grounding evaluation."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _iou(box1: tuple[float, float, float, float], box2: tuple[float, float, float, float]) -> float:
    """Intersection-over-Union for two bboxes (x1, y1, x2, y2)."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def _point_in_bbox(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    x, y = point
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


class GroundingEvaluator:
    """Evaluates grounding accuracy for UI element predictions."""

    def evaluate_prediction(
        self,
        predicted_bbox: tuple[float, float, float, float],
        ground_truth_bbox: tuple[float, float, float, float],
        threshold: float = 0.5,
    ) -> bool:
        """Return True if predicted bbox meets IoU threshold with ground truth."""
        return _iou(predicted_bbox, ground_truth_bbox) >= threshold

    def iou(self, box1: tuple[float, float, float, float], box2: tuple[float, float, float, float]) -> float:
        return _iou(box1, box2)

    def point_in_bbox(self, point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
        return _point_in_bbox(point, bbox)

    def accuracy_at_threshold(
        self,
        predictions: list[tuple[float, float, float, float]],
        ground_truths: list[tuple[float, float, float, float]],
        thresholds: list[float] | None = None,
    ) -> dict[str, float]:
        thresholds = thresholds or [0.3, 0.5, 0.7]
        result: dict[str, float] = {}
        for thresh in thresholds:
            hits = sum(
                1 for p, g in zip(predictions, ground_truths)
                if _iou(p, g) >= thresh
            )
            result[f"iou@{thresh}"] = hits / len(predictions) if predictions else 0.0
        return result

    def batch_evaluate(
        self,
        predictions: list[tuple[float, float, float, float]],
        ground_truths: list[tuple[float, float, float, float]],
    ) -> dict[str, Any]:
        if not predictions:
            return {"mean_iou": 0.0, "accuracy_at_0.5": 0.0, "count": 0}
        ious = [_iou(p, g) for p, g in zip(predictions, ground_truths)]
        acc_05 = sum(1 for iou_val in ious if iou_val >= 0.5) / len(ious)
        return {
            "mean_iou": round(sum(ious) / len(ious), 4),
            "accuracy_at_0.5": round(acc_05, 4),
            "count": len(ious),
        }
