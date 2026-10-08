"""Pinned OpenCUA inference with image inputs and non-executable action parsing."""

from __future__ import annotations

import ast
import base64
import io
import json
import math
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image

from sap_cua.types import ExecutorType, GUIAction, ModelResponse

MODEL_ID = "xlangai/OpenCUA-7B"
MODEL_REVISION = "a2efb7d2b104d477a4a2666a357e79550a28aafc"
SYSTEM_PROMPT = (
    "You are a GUI agent. Given a task and screenshot, return the next pyautogui action."
)


def resized_dimensions(width: int, height: int, max_pixels: int = 1_003_520) -> tuple[int, int]:
    """Qwen image resize rules, matching the processor's configured pixel budget."""
    factor = 28
    if min(width, height) < factor or max(width, height) / min(width, height) > 200:
        raise ValueError("Unsupported image dimensions")
    w, h = round(width / factor) * factor, round(height / factor) * factor
    if w * h > max_pixels:
        scale = math.sqrt(width * height / max_pixels)
        w, h = (
            math.floor(width / scale / factor) * factor,
            math.floor(height / scale / factor) * factor,
        )
    elif w * h < 3136:
        scale = math.sqrt(3136 / (width * height))
        w, h = (
            math.ceil(width * scale / factor) * factor,
            math.ceil(height * scale / factor) * factor,
        )
    return w, h


def parse_action(text: str, width: int, height: int) -> ModelResponse:
    """Parse one allowlisted literal call. Never evaluate generated Python."""
    if width <= 0 or height <= 0 or len(text) > 32000:
        raise ValueError("Invalid action frame or excessive model output")
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = blocks[-1].strip() if blocks else text.strip()
    tree = ast.parse(code, mode="exec")
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        raise ValueError("Expected exactly one pyautogui action")
    call = tree.body[0].value
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "pyautogui"
    ):
        raise ValueError("Only literal pyautogui calls are accepted")
    name = call.func.attr
    args = [ast.literal_eval(a) for a in call.args]
    if any(k.arg is None for k in call.keywords):
        raise ValueError("Expanded keyword arguments are not allowed")
    kwargs = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    if name in ("click", "doubleClick", "rightClick"):
        if (
            set(kwargs) - {"x", "y"}
            or len(args) > 2
            or (args and "x" in kwargs)
            or (len(args) > 1 and "y" in kwargs)
        ):
            raise ValueError("Unsupported click arguments")
        x = kwargs.get("x", args[0] if args else None)
        y = kwargs.get("y", args[1] if len(args) > 1 else None)
        if not all(type(v) in (float, int) for v in (x, y)) or not (
            0 <= x < width and 0 <= y < height
        ):
            raise ValueError("Click is outside image bounds")
        gui = GUIAction(
            type={"click": "click", "doubleClick": "double_click", "rightClick": "right_click"}[
                name
            ],
            x=x / width,
            y=y / height,
        )
    elif (
        name in ("write", "typewrite")
        and len(args) == 1
        and not kwargs
        and isinstance(args[0], str)
    ):
        gui = GUIAction(type="type", text=args[0])
    elif name == "press" and len(args) == 1 and not kwargs and isinstance(args[0], str):
        gui = GUIAction(type="key_press", key=args[0])
    elif name == "hotkey" and args and not kwargs and all(isinstance(a, str) for a in args):
        gui = GUIAction(type="hotkey", keys=args)
    else:
        raise ValueError(f"Unsupported GUI action: {name}")
    return ModelResponse(
        intent=gui.type.value.upper(),
        executor=ExecutorType.GUI,
        gui_action=gui,
        confidence=0.0,
        reasoning="Parsed model action; not yet executed",
    )


class OpenCUARuntime:
    def __init__(
        self,
        model_path: str | None = None,
        *,
        api_base: str | None = None,
        max_pixels: int = 1_003_520,
    ) -> None:
        self.model_path = Path(model_path or os.getenv("SAP_CUA_MODEL_PATH", ".models/OpenCUA-7B"))
        self.api_base = api_base or os.getenv("SAP_CUA_INFERENCE_URL")
        self.max_pixels = max_pixels
        self.model = self.tokenizer = self.image_processor = None

    def load_processor(self) -> None:
        if self.tokenizer is not None:
            return
        if not (self.model_path / "config.json").exists():
            raise FileNotFoundError("OpenCUA is not downloaded. Run sap-cua download-model.")
        from transformers import AutoTokenizer, AutoImageProcessor

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path), trust_remote_code=True, local_files_only=True
        )
        self.image_processor = AutoImageProcessor.from_pretrained(
            str(self.model_path), local_files_only=True, use_fast=False
        )
        self.image_processor.max_pixels = self.max_pixels

    def prepare(
        self, image: Image.Image, instruction: str, answer: str | None = None
    ) -> dict[str, Any]:
        """Expand media tokens from the actual processor grid; mask prompt labels for SFT."""
        self.load_processor()
        import torch

        info = self.image_processor(images=[image.convert("RGB")], return_tensors="pt")
        grid = info["image_grid_thw"]
        count = int(grid[0].prod()) // self.image_processor.merge_size**2
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": instruction}]},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        token = "<|media_placeholder|>"
        if prompt.count(token) != 1:
            raise ValueError("Unexpected OpenCUA image template")
        prompt = prompt.replace(token, token * count)
        prompt_ids = self.tokenizer(prompt, add_special_tokens=False)["input_ids"]
        ids = prompt_ids
        if answer is not None:
            ids = (
                ids
                + self.tokenizer(answer + self.tokenizer.eos_token, add_special_tokens=False)[
                    "input_ids"
                ]
            )
        result = {
            "input_ids": torch.tensor([ids]),
            "attention_mask": torch.ones((1, len(ids)), dtype=torch.long),
            "pixel_values": info["pixel_values"],
            "image_grid_thw": grid,
        }
        if answer is not None:
            labels = result["input_ids"].clone()
            labels[:, : len(prompt_ids)] = -100
            result["labels"] = labels
        return result

    def load_model(self) -> None:
        if self.model is not None:
            return
        self.load_processor()
        import torch
        from transformers import AutoModel

        kwargs: dict[str, Any] = {
            "trust_remote_code": True,
            "local_files_only": True,
            "torch_dtype": torch.bfloat16,
            "attn_implementation": "sdpa",
        }
        if torch.cuda.is_available():
            kwargs["device_map"] = "auto"
        else:
            # Keep resident weights bounded on the 16 GB development machine.
            kwargs.update(
                device_map="auto",
                max_memory={"cpu": "6GiB"},
                offload_folder=str(self.model_path / "offload"),
                offload_state_dict=True,
            )
        self.model = AutoModel.from_pretrained(str(self.model_path), **kwargs).eval()
        if not hasattr(self.model, "generate"):
            from transformers.generation import GenerationMixin

            self.model.__class__ = type(
                "OpenCUAGeneration", (self.model.__class__, GenerationMixin), {}
            )

    def ground(
        self, image: Image.Image, instruction: str, *, max_tokens: int = 128
    ) -> ModelResponse:
        if not 1 <= max_tokens <= 512:
            raise ValueError("max_tokens must be between 1 and 512")
        width, height = resized_dimensions(*image.size, max_pixels=self.max_pixels)
        if self.api_base:
            import httpx

            buffer = io.BytesIO()
            # Send already-resized pixels so the returned coordinate frame is explicit.
            image.resize((width, height)).save(buffer, format="PNG")
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(buffer.getvalue()).decode()
                            },
                        },
                        {"type": "text", "text": instruction},
                    ],
                },
            ]
            headers = {}
            if os.getenv("SAP_CUA_INFERENCE_KEY"):
                headers["Authorization"] = "Bearer " + os.environ["SAP_CUA_INFERENCE_KEY"]
            response = httpx.post(
                self.api_base.rstrip("/") + "/chat/completions",
                headers=headers,
                json={
                    "model": "opencua-7b",
                    "messages": messages,
                    "temperature": 0,
                    "max_tokens": max_tokens,
                },
                timeout=180,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        else:
            self.load_model()
            import torch

            inputs = self.prepare(image, instruction)
            device = self.model.get_input_embeddings().weight.device
            if device.type == "meta":
                device = torch.device("cpu")
            inputs = {
                k: v.to(device=device, dtype=torch.bfloat16 if k == "pixel_values" else v.dtype)
                for k, v in inputs.items()
            }
            with torch.inference_mode():
                output = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    max_time=120,
                    do_sample=False,
                    eos_token_id=self.tokenizer.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            text = self.tokenizer.decode(
                output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True
            )
        return parse_action(text, width, height)


def download_model(destination: str = ".models/OpenCUA-7B") -> str:
    from huggingface_hub import snapshot_download

    result = snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=destination,
        allow_patterns=[
            "*.json",
            "*.safetensors",
            "*.py",
            "*.tiktoken",
            "*.txt",
            "*.md",
            "*.jinja",
            "tiktoken.model",
            "LICENSE*",
        ],
        max_workers=3,
    )
    (Path(result) / "sap-cua-model.json").write_text(
        json.dumps(
            {
                "repo_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "trained_for_sap": False,
                "status": "downloaded",
            },
            indent=2,
        )
    )
    return result
