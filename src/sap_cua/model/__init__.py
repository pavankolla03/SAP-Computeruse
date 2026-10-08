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
    """Real screenshot inference; unavailable checkpoints fail explicitly."""
    def __init__(self, model_path: str | None = None, **kwargs: Any):
        from sap_cua.model.opencua import OpenCUARuntime
        self.runtime = OpenCUARuntime(model_path)
        self.history = []
        self._last_action = ""

    def observe(self, image):
        if isinstance(image, str):
            with PILImage.open(image) as img:
                return {"image_size": img.size}
        if not isinstance(image, PILImage.Image):
            raise ValueError("OpenCUA requires an actual screenshot")
        return {"image_size": image.size}

    def plan(self, instruction, history):
        return {"instruction": instruction, "steps": len(history)}

    def act(self, instruction, image, history):
        self.observe(image)
        if isinstance(image, str):
            with PILImage.open(image) as img:
                response = self.runtime.ground(img, instruction)
        else:
            response = self.runtime.ground(image, instruction)
        self._last_action = response.intent
        return response

    def reset(self):
        self.history.clear()
        self._last_action = ""

    def get_action(self):
        return self._last_action

    def get_confidence(self):
        return 0.0  # No calibrated confidence estimator is available.


class UITARSAdapter(OpenCUAAdapter):
    """Reserved baseline; never masquerades as working inference."""
    def act(self, instruction, image, history):
        raise NotImplementedError("UI-TARS inference is not connected")


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
