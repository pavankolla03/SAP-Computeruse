"""Capability-based hybrid routing. Unknown write outcomes never trigger fallback."""

from collections.abc import Callable
from dataclasses import dataclass

from sap_cua.engineering.actions import validate_step
from sap_cua.security import sanitize_data

PRIORITY = ("sap_api", "mcp", "template", "playwright", "browser_mouse", "computer_use")


@dataclass
class Binding:
    name: str
    supports: Callable
    execute: Callable
    verify: Callable


class HybridRouter:
    def __init__(self, bindings, authorize):
        self.bindings = {b.name: b for b in bindings}
        if len(self.bindings) != len(bindings) or set(self.bindings) - set(PRIORITY):
            raise ValueError("Invalid executor bindings")
        self.authorize = authorize

    def execute(self, step, scope):
        validate_step(step)
        if scope.role == "viewer" and step.action not in ("QUERY_MPL", "DIAGNOSE_ERROR"):
            raise PermissionError("Viewer cannot mutate SAP")
        # Authorization checks typed action/args, never model-provided risk labels.
        if self.authorize(step, scope) is not True:
            raise PermissionError("Action denied by runtime policy")
        for name in PRIORITY:
            binding = self.bindings.get(name)
            if not binding or binding.supports(step) is not True:
                continue
            try:
                result = binding.execute(step)
                verification = binding.verify(step, result)
                return sanitize_data(
                    {
                        "success": result.get("success") is True
                        and verification.get("success") is True,
                        "executor": name,
                        "result": result,
                        "verification": verification,
                        "outcome": "observed",
                    }
                )
            except Exception as exc:  # noqa: BLE001 - persist failure and never replay uncertain writes
                return {
                    "success": False,
                    "executor": name,
                    "outcome": "unknown",
                    "error": type(exc).__name__,
                    "retry_allowed": False,
                }
        return {
            "success": False,
            "outcome": "not_executed",
            "error": "No capable executor is connected",
        }
