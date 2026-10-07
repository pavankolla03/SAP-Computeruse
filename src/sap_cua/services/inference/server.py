"""vLLM + Transformers inference server for SAP-CUA model serving."""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="SAP-CUA Inference Server", version="0.1.0")


# ─── Model Cache ─────────────────────────────────────────────────────────────


class ModelCache:
    """Cache loaded models by name to avoid reloading."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def get(self, name: str) -> Any | None:
        return self._cache.get(name)

    def put(self, name: str, model: Any) -> None:
        self._cache[name] = model

    def clear(self) -> None:
        self._cache.clear()

    @property
    def loaded(self) -> list[str]:
        return list(self._cache.keys())


# Global cache shared across the server process.
_model_cache = ModelCache()


# ─── Model Loading ───────────────────────────────────────────────────────────


def _load_vllm(model_name: str, **kwargs: Any) -> Any:
    try:
        from vllm import LLM
    except ImportError as exc:
        raise ImportError("vllm package is required for vLLM backend") from exc

    logger.info("Loading model via vLLM: %s", model_name)
    llm = LLM(model=model_name, **kwargs)
    logger.info("vLLM model loaded: %s", model_name)
    return llm


def _load_transformers(model_name: str, **kwargs: Any) -> Any:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "torch and transformers are required for Transformers backend"
        ) from exc

    logger.info("Loading model via Transformers: %s", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
    logger.info("Transformers model loaded: %s", model_name)
    return tokenizer, model


def load_model(
    model_name: str,
    backend: str = "auto",
    quantization: str | None = None,
    device: str = "auto",
    **kwargs: Any,
) -> Any:
    """Load a model, preferring vLLM if available.

    Parameters
    ----------
    model_name:
        HuggingFace model identifier or local path.
    backend:
        ``"vllm"``, ``"transformers"``, or ``"auto"`` (prefer vLLM).
    quantization:
        ``"4bit"`` or ``"8bit"`` (bitsandbytes) — only for Transformers.
    device:
        ``"auto"``, ``"cpu"``, ``"cuda"``, etc.
    """
    if backend == "auto":
        try:
            import vllm  # noqa: F401
            backend = "vllm"
        except ImportError:
            backend = "transformers"
        logger.info("Auto-selected backend: %s", backend)

    if backend == "vllm":
        load_kwargs: dict[str, Any] = {"device": device}
        if quantization:
            load_kwargs["quantization"] = quantization
        load_kwargs.update(kwargs)
        return _load_vllm(model_name, **load_kwargs)

    # Transformers
    load_kwargs_tf: dict[str, Any] = {}
    if device != "auto":
        load_kwargs_tf["device_map"] = device

    if quantization == "4bit":
        try:
            import bitsandbytes  # noqa: F401
            load_kwargs_tf["load_in_4bit"] = True
        except ImportError:
            logger.warning("bitsandbytes not installed; 4-bit quantization unavailable")
    elif quantization == "8bit":
        try:
            import bitsandbytes  # noqa: F401
            load_kwargs_tf["load_in_8bit"] = True
        except ImportError:
            logger.warning("bitsandbytes not installed; 8-bit quantization unavailable")

    load_kwargs_tf.update(kwargs)
    return _load_transformers(model_name, **load_kwargs_tf)


# ─── Inference Server ────────────────────────────────────────────────────────


class InferenceServer:
    """High-level inference server wrapping a loaded model."""

    def __init__(
        self,
        model_name: str = "mock",
        backend: str = "auto",
        quantization: str | None = None,
        device: str = "auto",
        cache_key: str = "default",
    ) -> None:
        self.model_name = model_name
        self.backend = backend
        self.quantization = quantization
        self.device = device
        self.cache_key = cache_key

        existing = _model_cache.get(cache_key)
        if existing is not None:
            self._model = existing
            logger.info("Reusing cached model '%s'", cache_key)
        else:
            if model_name == "mock":
                self._model = None
            else:
                self._model = load_model(
                    model_name,
                    backend=backend,
                    quantization=quantization,
                    device=device,
                )
            _model_cache.put(cache_key, self._model)

    # ------------------------------------------------------------------
    def _generate_vllm(self, request: Any) -> str:
        llm = self._model
        from vllm import SamplingParams
        params = SamplingParams(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        outputs = llm.generate([request.instruction], params)
        return outputs[0].outputs[0].text

    def _generate_transformers(
        self, request: Any, tokenizer: Any, model: Any
    ) -> str:
        import torch

        inputs = tokenizer(request.instruction, return_tensors="pt")
        device_map = getattr(model, "device_map", None)
        target_device = (
            torch.device(next(iter(device_map.values())))
            if device_map
            else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        inputs = {k: v.to(target_device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                pad_token_id=tokenizer.eos_token_id,
            )
        decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Strip the prompt prefix if it's echoed.
        if decoded.startswith(request.instruction):
            decoded = decoded[len(request.instruction):].strip()
        return decoded

    # ------------------------------------------------------------------
    def generate(self, request: Any) -> Any:
        """Run inference and return a ``ModelResponse``.

        Parameters
        ----------
        request:
            ``ModelRequest`` instance.

        Returns
        -------
        ModelResponse
        """
        try:
            if self._model is None:
                from sap_cua.model import get_model
                model = get_model("mock")
                response = model.act(
                    instruction=request.instruction,
                    image=request.image_paths[0] if request.image_paths else None,
                    history=request.history or [],
                )
                response.raw_output = "(mock inference)"
                return response

            if self.backend == "vllm":
                text = self._generate_vllm(request)
            else:
                tokenizer, model = self._model
                text = self._generate_transformers(request, tokenizer, model)

            return self._text_to_response(text)

        except RuntimeError as exc:
            err_msg = str(exc).lower()
            if "out of memory" in err_msg or "oom" in err_msg:
                logger.error("OOM during inference: %s", exc)
                raise HTTPException(status_code=507, detail="Out of memory during inference") from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            logger.error("Model not found: %s", exc)
            raise HTTPException(status_code=404, detail=f"Model not found: {self.model_name}") from exc
        except Exception as exc:
            logger.exception("Inference error: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    def generate_stream(self, request: Any) -> AsyncIterator[str]:
        """Yield tokens one at a time for streaming responses.

        Falls back to returning the full text in a single chunk when the
        backend does not natively support streaming.
        """
        response = self.generate(request)
        raw = response.raw_output or response.reasoning or ""
        chunk_size = 32
        for i in range(0, len(raw), chunk_size):
            yield raw[i : i + chunk_size]
            time.sleep(0.01)

    # ------------------------------------------------------------------
    @staticmethod
    def _text_to_response(text: str) -> Any:
        from sap_cua.types import ExecutorType, GUIAction, GUIActionType, ModelResponse
        import re

        intent = "unknown"
        gui_action: GUIAction | None = None
        confidence = 0.5

        click_m = re.search(r"click\(([0-9.]+),\s*([0-9.]+)\)", text)
        if click_m:
            intent = "CLICK"
            gui_action = GUIAction(
                type=GUIActionType.CLICK,
                x=float(click_m.group(1)),
                y=float(click_m.group(2)),
            )

        type_m = re.search(r"type\(['\"](.+?)['\"]\)", text)
        if not gui_action and type_m:
            intent = "TYPE"
            gui_action = GUIAction(type=GUIActionType.TYPE, text=type_m.group(1))

        return ModelResponse(
            intent=intent,
            executor=ExecutorType.GUI,
            gui_action=gui_action,
            confidence=confidence,
            reasoning=text,
            raw_output=text,
        )


# ─── FastAPI Routes ──────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": os.getenv("MODEL_NAME", "mock")}


@app.get("/info")
async def model_info() -> dict[str, Any]:
    return {
        "model_name": os.getenv("MODEL_NAME", "mock"),
        "backend": os.getenv("MODEL_BACKEND", "auto"),
        "quantization": os.getenv("MODEL_QUANTIZATION"),
        "cached_models": _model_cache.loaded,
    }


@app.post("/generate")
async def generate_endpoint(request: Any) -> Any:
    server = InferenceServer(
        model_name=os.getenv("MODEL_NAME", "mock"),
        backend=os.getenv("MODEL_BACKEND", "auto"),
        quantization=os.getenv("MODEL_QUANTIZATION"),
    )
    response = server.generate(request)
    return response.model_dump()


@app.post("/generate/stream")
async def generate_stream_endpoint(request: Any) -> StreamingResponse:
    server = InferenceServer(
        model_name=os.getenv("MODEL_NAME", "mock"),
        backend=os.getenv("MODEL_BACKEND", "auto"),
        quantization=os.getenv("MODEL_QUANTIZATION"),
    )
    return StreamingResponse(
        server.generate_stream(request),
        media_type="text/plain",
    )


# ─── Launch ──────────────────────────────────────────────────────────────────


def launch_server(
    host: str = "0.0.0.0",
    port: int = 8001,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """Start the uvicorn inference server."""
    uvicorn.run(
        "sap_cua.services.inference.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    port = int(os.getenv("INFERENCE_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
