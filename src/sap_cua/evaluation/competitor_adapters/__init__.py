"""SAP-CUA competitor evaluation adapters (optional).

Each adapter wraps a competing computer-use model and converts between its
native response format and our ``ModelResponse`` schema.  Adapters gracefully
handle missing dependencies / missing API keys by raising ``ImportError`` or
returning a mock response at instantiation time.
"""

from __future__ import annotations

import abc
import logging
import os
from typing import Any

from sap_cua.types import ExecutorType, GUIAction, GUIActionType, ModelResponse

logger = logging.getLogger(__name__)


# ─── Abstract Base ───────────────────────────────────────────────────────────


class BaseAdapter(abc.ABC):
    """Abstract base for all competitor adapters."""

    @abc.abstractmethod
    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Return per-image observations from the model.

        Parameters
        ----------
        image_paths:
            File paths of screenshots to process.

        Returns
        -------
        list of observation dicts
        """

    @abc.abstractmethod
    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        """Produce the next action given the current instruction and history.

        Parameters
        ----------
        instruction:
            Natural-language goal from the task.
        history:
            Previous action/observation pairs from this trajectory.

        Returns
        -------
        ModelResponse
        """


# ─── OpenAI ──────────────────────────────────────────────────────────────────


class OpenAIAdapter(BaseAdapter):
    """Adapter for the OpenAI computer-use-preview model.

    Requires the ``OPENAI_API_KEY`` environment variable and the ``openai``
    package (>= 1.0).
    """

    MODEL = "computer-use-preview"

    def __init__(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise ImportError("OPENAI_API_KEY environment variable is not set")
        try:
            import openai  # noqa: F401
        except ImportError as exc:
            raise ImportError("openai package is required for OpenAIAdapter") from exc

    # ------------------------------------------------------------------
    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Convert OpenAI screenshot / pending_safety_checks output."""
        import base64

        observations: list[dict[str, Any]] = []
        for path in image_paths:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            observations.append(
                {
                    "type": "computer_use_preview_screenshot",
                    "source": {"type": "base64", "data": b64},
                    "pending_safety_checks": [],
                }
            )
        return observations

    # ------------------------------------------------------------------
    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        from openai import OpenAI

        client = OpenAI()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are a computer-use assistant."},
            {"role": "user", "content": instruction},
        ]

        response = client.responses.create(
            model=self.MODEL,
            tools=[{"type": "computer_use_preview", "display_width": 1024, "display_height": 768}],
            input=messages,
        )

        return self._convert_response(response)

    # ------------------------------------------------------------------
    @staticmethod
    def _convert_response(response: Any) -> ModelResponse:
        """Convert OpenAI response to ``ModelResponse``."""
        import json

        output_items = response.output if hasattr(response, "output") else []
        intent = "unknown"
        gui_action: GUIAction | None = None
        confidence = 0.5
        reasoning = ""

        for item in output_items:
            if getattr(item, "type", None) == "computer_call":
                call = item
                action = getattr(call, "action", {})
                action_type = action.get("type", "unknown")
                intent = action_type.upper()

                if action_type == "click":
                    gui_action = GUIAction(
                        type=GUIActionType.CLICK,
                        x=action.get("x", 0.5),
                        y=action.get("y", 0.5),
                    )
                elif action_type == "type":
                    gui_action = GUIAction(
                        type=GUIActionType.TYPE,
                        text=action.get("text", ""),
                    )
                elif action_type == "scroll":
                    gui_action = GUIAction(
                        type=GUIActionType.SCROLL,
                        y=0.5,
                    )
                elif action_type == "drag":
                    gui_action = GUIAction(
                        type=GUIActionType.DRAG,
                        x=action.get("x", 0.5),
                        y=action.get("y", 0.5),
                        x2=action.get("x2"),
                        y2=action.get("y2"),
                    )
                elif action_type == "keypress":
                    gui_action = GUIAction(
                        type=GUIActionType.KEY_PRESS,
                        key=",".join(action.get("keys", [])),
                    )
                elif action_type == "wait":
                    gui_action = GUIAction(
                        type=GUIActionType.WAIT,
                        duration_ms=action.get("duration_ms", 1000),
                    )

                reasoning = f"OpenAI computer_call: {action_type}"
                break

        return ModelResponse(
            intent=intent,
            executor=ExecutorType.GUI,
            gui_action=gui_action,
            confidence=confidence,
            reasoning=reasoning,
        )


# ─── Claude / Anthropic ──────────────────────────────────────────────────────


class ClaudeAdapter(BaseAdapter):
    """Adapter for the Claude Sonnet 4 computer-use tool format.

    Requires the ``ANTHROPIC_API_KEY`` environment variable and the
    ``anthropic`` package (>= 0.40).
    """

    MODEL = "claude-sonnet-4-20250514"

    def __init__(self) -> None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ImportError("ANTHROPIC_API_KEY environment variable is not set")
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:
            raise ImportError("anthropic package is required for ClaudeAdapter") from exc

    # ------------------------------------------------------------------
    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Return Claude-format observation blocks."""
        observations: list[dict[str, Any]] = []
        for path in image_paths:
            with open(path, "rb") as fh:
                import base64
                b64 = base64.b64encode(fh.read()).decode()
            observations.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                }
            )
        return observations

    # ------------------------------------------------------------------
    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        from anthropic import Anthropic

        client = Anthropic()

        messages: list[dict[str, Any]] = [{"role": "user", "content": instruction}]

        response = client.messages.create(
            model=self.MODEL,
            max_tokens=1024,
            tools=[
                {
                    "name": "computer_use",
                    "description": "Control a computer via GUI actions",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": [
                                    "click", "double_click", "right_click",
                                    "type", "key", "scroll", "drag",
                                    "wait", "screenshot",
                                ],
                            },
                            "x": {"type": "number", "minimum": 0, "maximum": 1},
                            "y": {"type": "number", "minimum": 0, "maximum": 1},
                            "x2": {"type": "number"},
                            "y2": {"type": "number"},
                            "text": {"type": "string"},
                            "key": {"type": "string"},
                            "scroll_direction": {"type": "string"},
                            "scroll_amount": {"type": "integer"},
                            "duration_ms": {"type": "integer"},
                        },
                    },
                }
            ],
            messages=messages,
        )

        return self._convert_response(response)

    # ------------------------------------------------------------------
    @staticmethod
    def _convert_response(response: Any) -> ModelResponse:
        """Convert Anthropic response to ``ModelResponse``."""
        intent = "unknown"
        gui_action: GUIAction | None = None
        confidence = 0.5
        reasoning = ""

        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == "computer_use":
                args = getattr(block, "input", {})
                action = args.get("action", "unknown")
                intent = action.upper()

                if action in ("click", "double_click", "right_click"):
                    gui_action = GUIAction(
                        type=GUIActionType(action),
                        x=args.get("x", 0.5),
                        y=args.get("y", 0.5),
                    )
                elif action == "type":
                    gui_action = GUIAction(
                        type=GUIActionType.TYPE,
                        text=args.get("text", ""),
                    )
                elif action == "key":
                    gui_action = GUIAction(
                        type=GUIActionType.HOTKEY,
                        keys=args.get("key", "").split("+"),
                    )
                elif action == "scroll":
                    gui_action = GUIAction(
                        type=GUIActionType.SCROLL,
                        y=0.5,
                    )
                elif action == "drag":
                    gui_action = GUIAction(
                        type=GUIActionType.DRAG,
                        x=args.get("x", 0.5),
                        y=args.get("y", 0.5),
                        x2=args.get("x2"),
                        y2=args.get("y2"),
                    )
                elif action == "wait":
                    gui_action = GUIAction(
                        type=GUIActionType.WAIT,
                        duration_ms=args.get("duration_ms", 1000),
                    )

                reasoning = f"Claude computer_use: {action}"
                break

        return ModelResponse(
            intent=intent,
            executor=ExecutorType.GUI,
            gui_action=gui_action,
            confidence=confidence,
            reasoning=reasoning,
        )


# ─── Google Gemini ───────────────────────────────────────────────────────────


class GeminiAdapter(BaseAdapter):
    """Adapter for the Google Gemini computer-use function-calling format.

    Requires the ``GOOGLE_API_KEY`` environment variable and the
    ``google.generativeai`` package.
    """

    MODEL = "gemini-2.0-flash"

    def __init__(self) -> None:
        if not os.getenv("GOOGLE_API_KEY"):
            raise ImportError("GOOGLE_API_KEY environment variable is not set")
        try:
            import google.generativeai  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package is required for GeminiAdapter"
            ) from exc

    # ------------------------------------------------------------------
    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Return Gemini-format parts (image blobs + text)."""
        observations: list[dict[str, Any]] = []
        for path in image_paths:
            with open(path, "rb") as fh:
                import base64
                b64 = base64.b64encode(fh.read()).decode()
            observations.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "mime_type": "image/png",
                        "data": b64,
                    },
                }
            )
        return observations

    # ------------------------------------------------------------------
    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

        model = genai.GenerativeModel(
            self.MODEL,
            tools=[self._build_function_declarations()],
        )

        chat = model.start_chat()
        response = chat.send_message(
            f"Current screen: screenshot provided.\nInstruction: {instruction}"
        )

        return self._convert_response(response)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_function_declarations() -> dict[str, Any]:
        return {
            "function_declarations": [
                {
                    "name": "computer_use",
                    "description": "Control a computer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["click", "double_click", "type", "scroll", "drag", "key"],
                            },
                            "x": {"type": "number", "minimum": 0, "maximum": 1},
                            "y": {"type": "number", "minimum": 0, "maximum": 1},
                            "x2": {"type": "number"},
                            "y2": {"type": "number"},
                            "text": {"type": "string"},
                            "key": {"type": "string"},
                            "direction": {"type": "string"},
                            "amount": {"type": "integer"},
                        },
                    },
                }
            ]
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _convert_response(response: Any) -> ModelResponse:
        """Convert Gemini response to ``ModelResponse``."""
        intent = "unknown"
        gui_action: GUIAction | None = None
        confidence = 0.5
        reasoning = ""

        candidates = getattr(response, "candidates", [])
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    args = dict(getattr(fc, "args", {}))
                    action = args.get("action", "unknown")
                    intent = action.upper()

                    if action == "click":
                        gui_action = GUIAction(
                            type=GUIActionType.CLICK,
                            x=args.get("x", 0.5),
                            y=args.get("y", 0.5),
                        )
                    elif action == "double_click":
                        gui_action = GUIAction(
                            type=GUIActionType.DOUBLE_CLICK,
                            x=args.get("x", 0.5),
                            y=args.get("y", 0.5),
                        )
                    elif action == "type":
                        gui_action = GUIAction(
                            type=GUIActionType.TYPE,
                            text=args.get("text", ""),
                        )
                    elif action == "key":
                        gui_action = GUIAction(
                            type=GUIActionType.HOTKEY,
                            keys=args.get("key", "").split("+"),
                        )
                    elif action == "scroll":
                        gui_action = GUIAction(
                            type=GUIActionType.SCROLL,
                            y=0.5,
                        )
                    elif action == "drag":
                        gui_action = GUIAction(
                            type=GUIActionType.DRAG,
                            x=args.get("x", 0.5),
                            y=args.get("y", 0.5),
                            x2=args.get("x2"),
                            y2=args.get("y2"),
                        )

                    reasoning = f"Gemini computer_use: {action}"
                    break

        return ModelResponse(
            intent=intent,
            executor=ExecutorType.GUI,
            gui_action=gui_action,
            confidence=confidence,
            reasoning=reasoning,
        )


# ─── ByteDance Navigator (stub) ──────────────────────────────────────────────


class NavigatorAdapter(BaseAdapter):
    """Stub adapter for ByteDance Navigator n2 computer-use model.

    This is a **placeholder** implementation.  The Navigator n2 API
    specification is not publicly documented; adapt accordingly when
    integration details become available.
    """

    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        logger.warning("NavigatorAdapter.observe() is a stub")
        return [
            {"type": "navigator_image", "path": p, "status": "stub"}
            for p in image_paths
        ]

    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        logger.warning("NavigatorAdapter.act() is a stub returning a mock response")
        return ModelResponse(
            intent="CLICK",
            executor=ExecutorType.GUI,
            gui_action=GUIAction(type=GUIActionType.CLICK, x=0.5, y=0.5),
            confidence=0.3,
            reasoning="NavigatorAdapter stub — replace with real implementation",
        )


# ─── UI-TARS (HuggingFace Transformers) ──────────────────────────────────────


class UITARSAdapter(BaseAdapter):
    """Adapter for ByteDance UI-TARS-1.5-7B via HuggingFace Transformers.

    The model is loaded lazily on the first ``act()`` call so that importing
    this module does not require ``torch`` or ``transformers`` to be installed.
    """

    DEFAULT_MODEL = "bytedance/UI-TARS-1.5-7B"

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or self.DEFAULT_MODEL
        self._model = None
        self._tokenizer = None
        self._loaded = False
        logger.info("UITARSAdapter configured (model=%s)", self.model_path)

    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "torch and transformers are required for UITARSAdapter"
            ) from exc

        logger.info("Loading UI-TARS-1.5-7B from %s ...", self.model_path)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self._model = AutoModelForCausalLM.from_pretrained(self.model_path)
        self._loaded = True
        logger.info("UI-TARS-1.5-7B loaded successfully")

    # ------------------------------------------------------------------
    def observe(self, image_paths: list[str]) -> list[dict[str, Any]]:
        """Tokenize images for UI-TARS."""
        return [{"path": p, "status": "pending"} for p in image_paths]

    # ------------------------------------------------------------------
    def act(
        self,
        instruction: str,
        history: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        self._ensure_loaded()

        prompt = self._build_prompt(instruction, history)
        inputs = self._tokenizer(prompt, return_tensors="pt")

        with self._model.device.type:
            outputs = self._model.generate(**inputs, max_new_tokens=256)
        generated = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

        return self._parse_output(generated)

    # ------------------------------------------------------------------
    @staticmethod
    def _build_prompt(
        instruction: str, history: list[dict[str, Any]] | None
    ) -> str:
        lines = ["You are a GUI agent. Predict the next action."]
        if history:
            lines.append("Previous actions:")
            for step in history[-5:]:
                lines.append(f"  - {step}")
        lines.append(f"Instruction: {instruction}")
        lines.append("Action:")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_output(text: str) -> ModelResponse:
        import re

        intent = "unknown"
        gui_action: GUIAction | None = None
        confidence = 0.5
        reasoning = text

        click_re = re.compile(r"click\(([0-9.]+),\s*([0-9.]+)\)")
        type_re = re.compile(r"type\(['\"](.+?)['\"]\)")
        scroll_re = re.compile(r"scroll\((up|down)\)")

        m_click = click_re.search(text)
        if m_click:
            intent = "CLICK"
            gui_action = GUIAction(
                type=GUIActionType.CLICK,
                x=float(m_click.group(1)),
                y=float(m_click.group(2)),
            )
        else:
            m_type = type_re.search(text)
            if m_type:
                intent = "TYPE"
                gui_action = GUIAction(type=GUIActionType.TYPE, text=m_type.group(1))
            else:
                m_scroll = scroll_re.search(text)
                if m_scroll:
                    intent = "SCROLL"
                    gui_action = GUIAction(type=GUIActionType.SCROLL, y=0.5)

        return ModelResponse(
            intent=intent,
            executor=ExecutorType.GUI,
            gui_action=gui_action,
            confidence=confidence,
            reasoning=reasoning,
        )


# ─── Factory ─────────────────────────────────────────────────────────────────


def get_competitor_adapter(name: str, **kwargs: Any) -> BaseAdapter | None:
    """Return a competitor adapter by name, or ``None`` if unavailable.

    Parameters
    ----------
    name:
        One of ``"openai"``, ``"claude"``, ``"gemini"``, ``"navigator"``,
        ``"ui-tars"``, ``"opencua"``.
    **kwargs:
        Forwarded to the adapter constructor.

    Returns
    -------
    BaseAdapter instance or ``None``
    """
    _adapters = {
        "openai": OpenAIAdapter,
        "claude": ClaudeAdapter,
        "gemini": GeminiAdapter,
        "navigator": NavigatorAdapter,
        "ui-tars": UITARSAdapter,
        "opencua": None,  # defined in sap_cua.model
    }

    if name not in _adapters:
        logger.warning("Unknown competitor adapter: %s", name)
        return None

    if name == "opencua":
        try:
            from sap_cua.model import OpenCUAAdapter  # noqa: F401
            return OpenCUAAdapter(**kwargs)
        except Exception as exc:
            logger.warning("OpenCUA adapter unavailable: %s", exc)
            return None

    adapter_cls = _adapters[name]
    assert adapter_cls is not None  # for type checkers

    try:
        return adapter_cls(**kwargs)
    except ImportError as exc:
        logger.warning("Competitor adapter '%s' unavailable: %s", name, exc)
        return None
    except Exception as exc:
        logger.error("Failed to instantiate '%s' adapter: %s", name, exc)
        return None
