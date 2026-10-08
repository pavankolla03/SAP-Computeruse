"""Bounded screenshot agent loop; verifier and action permission are caller-owned."""

from __future__ import annotations
import time
from collections.abc import Callable
from sap_cua.security import sanitize_data


def run_browser_task(
    browser,
    model,
    instruction: str,
    *,
    verifier: Callable,
    authorize: Callable,
    max_steps: int = 20,
    max_seconds: float = 300,
):
    if not 1 <= max_steps <= 100 or not 0 < max_seconds <= 3600:
        raise ValueError("Invalid execution budget")
    if not callable(verifier) or not callable(authorize):
        raise ValueError("A trusted verifier and action authorizer are required")
    start = time.monotonic()
    history = []
    error = "Step budget exhausted"
    verification = {"success": False}
    for index in range(max_steps):
        if time.monotonic() - start >= max_seconds:
            error = "Time budget exhausted"
            break
        try:
            image = browser.observe()
            response = model.act(instruction, image, history)
            if time.monotonic() - start >= max_seconds:
                error = "Time budget exhausted after inference; no action executed"
                break
            if response.gui_action is None:
                raise ValueError("A browser GUI action is required")
            if authorize(response.gui_action) is not True:
                raise PermissionError("Action denied by caller policy")
            result = browser.execute_gui(response.gui_action)
            verification = verifier(browser)
            history.append(
                sanitize_data(
                    {
                        "step": index,
                        "action": response.gui_action.model_dump(mode="json"),
                        "result": result,
                        "verification": verification,
                    }
                )
            )
            if result.get("success") is not True:
                error = "Browser action failed"
                break
            if verification.get("success") is True:
                return {
                    "success": True,
                    "steps": history,
                    "verification": verification,
                    "backend": "playwright",
                    "duration_ms": round((time.monotonic() - start) * 1000),
                    "error": None,
                }
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
    return sanitize_data(
        {
            "success": False,
            "steps": history,
            "verification": verification,
            "backend": "playwright",
            "duration_ms": round((time.monotonic() - start) * 1000),
            "error": error,
        }
    )
