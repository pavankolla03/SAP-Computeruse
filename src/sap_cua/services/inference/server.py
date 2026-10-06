"""Inference server for SAP-CUA model serving."""

from __future__ import annotations

import logging
import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from sap_cua.model import get_model

logger = logging.getLogger(__name__)

app = FastAPI(title="SAP-CUA Inference", version="0.1.0")

model_type = os.getenv("MODEL_TYPE", "mock")
model = get_model(model_type)


class InferRequest(BaseModel):
    instruction: str
    image: Optional[str] = None
    history: Optional[list] = None


class InferResponse(BaseModel):
    intent: str
    executor: str
    confidence: float
    gui_action: Optional[dict] = None


@app.get("/health")
async def health():
    return {"status": "ok", "model": model_type}


@app.post("/infer", response_model=InferResponse)
async def infer(req: InferRequest):
    from sap_cua.types import ModelResponse
    response = model.act(
        instruction=req.instruction,
        image=req.image,
        history=req.history or [],
    )
    gui_action_dict = None
    if response.gui_action:
        gui_action_dict = response.gui_action.model_dump()
    return InferResponse(
        intent=response.intent,
        executor=response.executor.value,
        confidence=response.confidence,
        gui_action=gui_action_dict,
    )


if __name__ == "__main__":
    port = int(os.getenv("INFERENCE_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
