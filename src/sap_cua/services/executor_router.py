"""Executor router — selects the best executor for each SAP action."""

from __future__ import annotations

import logging
from typing import Any

from sap_cua.sap.actions import get_action_definition, validate_action_arguments
from sap_cua.types import ExecutorType, RiskLevel, SAPAction

logger = logging.getLogger(__name__)


# Action-level executor preferences
EXECUTOR_POLICY: dict[str, tuple[ExecutorType, ...]] = {
    # API-first actions
    "CREATE_PACKAGE": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "CREATE_IFLOW": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "DEPLOY_IFLOW": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "QUERY_MPL": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "GET_TRACE": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "OPEN_MPL": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "RETRY_MESSAGE": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "CREATE_API_PROVIDER": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "CREATE_API_PROXY": (ExecutorType.SAP_API, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "CREATE_SECURITY_MATERIAL": (ExecutorType.SAP_API, ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    # GUI-required actions
    "ADD_CONTENT_MODIFIER": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "ADD_ROUTER": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "ADD_EXCEPTION_SUBPROCESS": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "ADD_GROOVY_SCRIPT": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "ADD_XSLT": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "ADD_MESSAGE_MAPPING": (ExecutorType.MCP, ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    # Navigation
    "OPEN_INTEGRATION_SUITE": (ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "OPEN_CLOUD_INTEGRATION": (ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "OPEN_DESIGN": (ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "OPEN_MONITOR": (ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    "OPEN_SECURITY_MATERIAL": (ExecutorType.PLAYWRIGHT, ExecutorType.GUI),
    # Code generation
    "ADD_GROOVY_SCRIPT": (ExecutorType.CODE, ExecutorType.GUI),
    "ADD_XSLT": (ExecutorType.CODE, ExecutorType.GUI),
}


class ExecutorRouter:
    """Routes SAP actions to the best available executor."""

    def __init__(self, api_available: bool = False) -> None:
        self.api_available = api_available
        self._last_reason: str = ""

    def route(self, action: SAPAction) -> SAPAction:
        """Select the best executor for the given action."""
        preferred = EXECUTOR_POLICY.get(action.intent, (ExecutorType.GUI,))
        if ExecutorType.SAP_API in preferred and not self.api_available:
            preferred = tuple(e for e in preferred if e != ExecutorType.SAP_API)
        if preferred:
            selected = preferred[0]
            reason = f"Selected {selected} for {action.intent} (policy={action.intent})"
        else:
            selected = ExecutorType.GUI
            reason = f"Falling back to GUI for {action.intent}"
        self._last_reason = reason
        logger.info(reason)
        return action.model_copy(update={"executor": selected})

    def get_last_reason(self) -> str:
        return self._last_reason

    def execute(
        self,
        intent: str | SAPAction,
        context: Any | None = None,
        gui_action: Any | None = None,
    ) -> dict[str, Any]:
        """Execute against an explicitly supplied mock environment.

        Routing preferences alone do not prove a live executor is available.
        Live API/GUI/MCP adapters will be registered in the next runtime phase.
        """
        action = intent if isinstance(intent, SAPAction) else SAPAction(
            intent=intent, executor=ExecutorType.GUI,
            arguments=getattr(context, "args", {}) or {},
            gui_action=gui_action, expected_state="",
        )
        errors = validate_action_arguments(action.intent, action.arguments)
        if errors:
            return {"success": False, "error": "; ".join(errors)}
        routed = self.route(action)
        sap_env = getattr(context, "sap_env", None)
        if sap_env is None:
            return {"success": False, "executor": routed.executor,
                    "error": "No executor is connected"}
        from sap_cua.sap.mocks import SAPMockEnvironment
        if not isinstance(sap_env, SAPMockEnvironment):
            return {"success": False, "error": "Live executor integration is not implemented"}
        try:
            result = sap_env.execute_action(action.intent, action.arguments)
            return {
                "success": result.get("success") is True,
                "executor": routed.executor,
                "backend": "mock",
                "result": result,
                "error": result.get("error"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc),
                    "executor": routed.executor, "backend": "mock"}


class ExecutorContext:
    """Lightweight context object passed to the executor router."""

    def __init__(
        self,
        task: str = "",
        state: Any | None = None,
        history: list | None = None,
        step: int = 0,
        sap_env: Any | None = None,
        args: dict | None = None,
    ) -> None:
        self.task = task
        self.state = state
        self.history = history or []
        self.step = step
        self.sap_env = sap_env
        self.args = args or {}
