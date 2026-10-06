"""Computer-use model abstraction — interface and adapters."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage  # noqa: F401
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False
    PILImage = Any  # type: ignore[assignment,misc]

from sap_cua.types import GUIAction, ModelResponse


class ComputerUseModel(ABC):
    """Abstract interface for any computer-use model."""

    @abstractmethod
    def observe(self, image: PILImage | str) -> dict[str, Any]: ...

    @abstractmethod
    def plan(self, instruction: str, history: list[dict[str, Any]]) -> dict[str, Any]: ...

    @abstractmethod
    def act(self, instruction: str, image: PILImage | str, history: list[dict[str, Any]]) -> ModelResponse: ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def get_action(self) -> str: ...

    @abstractmethod
    def get_confidence(self) -> float: ...


class OpenCUAAdapter(ComputerUseModel):
    """Adapter for OpenCUA-7B via Transformers/vLLM."""

    def __init__(
        self,
        model_path: str = "xlangai/OpenCUA-7B",
        device: str = "cpu",
        use_vllm: bool = False,
        torch_dtype: str = "float32",
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.use_vllm = use_vllm
        self.torch_dtype = torch_dtype
        self.history: list[dict[str, Any]] = []
        self._last_action: str = ""
        self._last_confidence: float = 0.0
        self._loaded = False
        logger.info("OpenCUAAdapter initialized (model=%s, device=%s)", model_path, device)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.use_vllm:
            try:
                from vllm import LLM  # noqa: F401
                logger.info("vLLM backend available")
            except ImportError:
                logger.warning("vLLM not available, falling back to transformers")
                self.use_vllm = False
        self._loaded = True
        logger.info("OpenCUA-7B model ready (deferred loading)")

    def observe(self, image: PILImage | str) -> dict[str, Any]:
        self._ensure_loaded()
        if isinstance(image, str) and _HAS_PIL:
            image = PILImage.open(image)  # type: ignore[union-attr]
        return {"image_size": (1024, 1024), "has_pil": _HAS_PIL}

    def plan(self, instruction: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        return {"instruction": instruction, "steps": len(history)}

    def act(self, instruction: str, image: PILImage | str, history: list[dict[str, Any]]) -> ModelResponse:
        from sap_cua.types import ExecutorType
        self._ensure_loaded()
        self._last_action = "click_0.5_0.5"
        self._last_confidence = 0.7
        self.history.append({"instruction": instruction, "action": self._last_action})
        return ModelResponse(
            intent="CLICK",
            executor=ExecutorType.GUI,
            gui_action=GUIAction(type="click", x=0.5, y=0.5),
            confidence=self._last_confidence,
            reasoning="OpenCUA placeholder action",
        )

    def reset(self) -> None:
        self.history.clear()
        self._last_action = ""
        self._last_confidence = 0.0

    def get_action(self) -> str:
        return self._last_action

    def get_confidence(self) -> float:
        return self._last_confidence


class UITARSAdapter(ComputerUseModel):
    """Adapter for ByteDance UI-TARS-1.5-7B."""

    def __init__(
        self,
        model_path: str = "bytedance/UI-TARS-1.5-7B",
        device: str = "cpu",
        use_vllm: bool = False,
        torch_dtype: str = "float32",
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.use_vllm = use_vllm
        self.torch_dtype = torch_dtype
        self.history: list[dict[str, Any]] = []
        self._last_action = ""
        self._last_confidence = 0.0
        self._loaded = False
        logger.info("UITARSAdapter initialized (model=%s)", model_path)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

    def observe(self, image: PILImage | str) -> dict[str, Any]:
        return {"image_size": (1024, 1024), "has_pil": _HAS_PIL}

    def plan(self, instruction: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        return {"instruction": instruction, "steps": len(history)}

    def act(self, instruction: str, image: PILImage | str, history: list[dict[str, Any]]) -> ModelResponse:
        from sap_cua.types import ExecutorType
        self._last_action = "click_0.5_0.5"
        self._last_confidence = 0.7
        return ModelResponse(
            intent="CLICK",
            executor=ExecutorType.GUI,
            gui_action=GUIAction(type="click", x=0.5, y=0.5),
            confidence=0.7,
            reasoning="UI-TARS placeholder",
        )

    def reset(self) -> None:
        self.history.clear()

    def get_action(self) -> str:
        return self._last_action

    def get_confidence(self) -> float:
        return self._last_confidence


class MockModel(ComputerUseModel):
    """Mock model for development/testing."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []
        self._last_action = ""
        self._last_confidence = 0.85
        self._mock_responses = [
            "click_0.82_0.05",
            "click_0.91_0.12",
            "click_0.50_0.50",
            "type_hello world",
            "scroll_down_300",
            "hotkey_ctrl+s",
        ]
        self._mock_index = 0

    def observe(self, image: PILImage | str) -> dict[str, Any]:
        return {"mock": True, "image_size": (1440, 900), "has_pil": _HAS_PIL}

    def plan(self, instruction: str, history: list[dict[str, Any]]) -> dict[str, Any]:
        return {"instruction": instruction, "mock_plan": True, "steps": len(history)}

    def act(self, instruction: str, image: PILImage | str, history: list[dict[str, Any]]) -> ModelResponse:
        from sap_cua.types import ExecutorType, GUIActionType
        action_str = self._mock_responses[self._mock_index % len(self._mock_responses)]
        self._mock_index += 1
        self._last_action = action_str
        parts = action_str.split("_", 1)
        action_type = parts[0]
        if action_type == "click" and len(parts) > 1:
            coords = parts[1].split("_")
            gui = GUIAction(type=GUIActionType.CLICK, x=float(coords[0]), y=float(coords[1]))
            intent, executor = "CLICK", ExecutorType.GUI
        elif action_type == "type" and len(parts) > 1:
            gui = GUIAction(type=GUIActionType.TYPE, text=parts[1])
            intent, executor = "TYPE", ExecutorType.GUI
        elif action_type == "scroll":
            gui = GUIAction(type=GUIActionType.SCROLL, y=0.5)
            intent, executor = "SCROLL", ExecutorType.GUI
        elif action_type == "hotkey":
            gui = GUIAction(type=GUIActionType.HOTKEY, keys=parts[1].split("_"))
            intent, executor = "HOTKEY", ExecutorType.GUI
        else:
            gui = GUIAction(type=GUIActionType.CLICK, x=0.5, y=0.5)
            intent, executor = "CLICK", ExecutorType.GUI
        self.history.append({"instruction": instruction, "action": self._last_action})
        return ModelResponse(
            intent=intent,
            executor=executor,
            gui_action=gui,
            confidence=0.85,
            reasoning="Mock response",
        )

    def reset(self) -> None:
        self.history.clear()
        self._mock_index = 0
        self._last_action = ""

    def get_action(self) -> str:
        return self._last_action

    def get_confidence(self) -> float:
        return self._last_confidence


def get_model(model_type: str = "mock", **kwargs: Any) -> ComputerUseModel:
    """Factory function to create model adapters."""
    if model_type == "opencua":
        return OpenCUAAdapter(**kwargs)
    if model_type == "ui-tars":
        return UITARSAdapter(**kwargs)
    if model_type == "mock":
        return MockModel()
    raise ValueError(f"Unknown model type: {model_type}")
