"""Model registry endpoint."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_models() -> dict[str, Any]:
    registry_path = Path("model_registry")
    models = []
    if registry_path.exists():
        for p in registry_path.iterdir():
            if p.is_dir():
                metrics_file = p.path.joinpath("metrics.json")
                models.append({
                    "name": p.name,
                    "path": str(p),
                    "metrics_file": str(metrics_file) if metrics_file.exists() else None,
                })
    return {"models": models, "count": len(models)}