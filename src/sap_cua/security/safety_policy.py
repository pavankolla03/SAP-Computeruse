"""Safety policy engine for SAP-CUA action risk classification and enforcement."""

from __future__ import annotations

import fnmatch
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk severity levels for agent actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SafetyAction(BaseModel):
    """Result of classifying an action against the safety policy."""

    action_id: str
    action: str
    risk: RiskLevel
    requires_approval: bool = False
    reason: str = ""
    sandbox_allowed: bool = False


# ---------------------------------------------------------------------------
# Policy rules — class-level dict mapping intent/action patterns to risk
# ---------------------------------------------------------------------------
_POLICY_RULES: dict[str, RiskLevel] = {
    # ---- LOW: read-only, navigation ------------------------------------
    "OPEN_IFLOW": RiskLevel.LOW,
    "OPEN_DESIGN": RiskLevel.LOW,
    "OPEN_MONITOR": RiskLevel.LOW,
    "NAVIGATE_DASHBOARD": RiskLevel.LOW,
    "QUERY_MPL": RiskLevel.LOW,
    "GET_TRACE": RiskLevel.LOW,
    "READ_ARTIFACT": RiskLevel.LOW,
    "LIST_IFLOWS": RiskLevel.LOW,
    "LIST_TENANTS": RiskLevel.LOW,
    "GET_METRICS": RiskLevel.LOW,
    "VIEW_LOGS": RiskLevel.LOW,
    # wildcard patterns (evaluated via fnmatch)
    "OPEN_*": RiskLevel.LOW,
    "QUERY_*": RiskLevel.LOW,
    "GET_*": RiskLevel.LOW,
    "LIST_*": RiskLevel.LOW,
    "READ_*": RiskLevel.LOW,
    "VIEW_*": RiskLevel.LOW,
    # ---- MEDIUM: create / deploy DEV artifacts -------------------------
    "CREATE_IFLOW": RiskLevel.MEDIUM,
    "CREATE_TENANT": RiskLevel.MEDIUM,
    "ADD_ENDPOINT": RiskLevel.MEDIUM,
    "ADD_CREDENTIAL": RiskLevel.MEDIUM,
    "UPDATE_IFLOW_METADATA": RiskLevel.MEDIUM,
    "DEPLOY_IFLOW": RiskLevel.MEDIUM,
    "DEPLOY_IFLOW_DEV": RiskLevel.MEDIUM,
    "CREATE_SECURITY_ARTIFACT": RiskLevel.MEDIUM,
    "CREATE_ROLE": RiskLevel.MEDIUM,
    "ADD_ROLE_MEMBER": RiskLevel.MEDIUM,
    "ADD_PACKAGE": RiskLevel.MEDIUM,
    "IMPORT_PACKAGE": RiskLevel.MEDIUM,
    "CREATE_*": RiskLevel.MEDIUM,
    "ADD_*": RiskLevel.MEDIUM,
    "DEPLOY_*": RiskLevel.MEDIUM,
    "IMPORT_*": RiskLevel.MEDIUM,
    # ---- HIGH: delete, undeploy, credentials, security material -------
    "DELETE_IFLOW": RiskLevel.HIGH,
    "DELETE_TENANT": RiskLevel.HIGH,
    "DELETE_ENDPOINT": RiskLevel.HIGH,
    "UNDEPLOY_IFLOW": RiskLevel.HIGH,
    "UNDEPLOY_PACKAGE": RiskLevel.HIGH,
    "CREATE_SECURITY_MATERIAL": RiskLevel.HIGH,
    "UPDATE_SECURITY_MATERIAL": RiskLevel.HIGH,
    "DELETE_SECURITY_MATERIAL": RiskLevel.HIGH,
    "CONFIGURE_OAUTH": RiskLevel.HIGH,
    "UPDATE_CREDENTIAL": RiskLevel.HIGH,
    "DELETE_ROLE": RiskLevel.HIGH,
    "DELETE_PACKAGE": RiskLevel.HIGH,
    "REMOVE_ROLE_MEMBER": RiskLevel.HIGH,
    "DELETE_*": RiskLevel.HIGH,
    "UNDEPLOY_*": RiskLevel.HIGH,
    "CONFIGURE_*": RiskLevel.HIGH,
    # ---- CRITICAL: production, trust, role administration -------------
    "DEPLOY_IFLOW_PROD": RiskLevel.CRITICAL,
    "DEPLOY_PROD": RiskLevel.CRITICAL,
    "TRUST_CONFIG": RiskLevel.CRITICAL,
    "CONFIGURE_TRUST": RiskLevel.CRITICAL,
    "ROLE_ADMIN": RiskLevel.CRITICAL,
    "MANAGE_ROLE_ADMIN": RiskLevel.CRITICAL,
    "UPDATE_TRUST_CONFIG": RiskLevel.CRITICAL,
    "DEPLOY_TO_PROD": RiskLevel.CRITICAL,
}


class SafetyPolicy:
    """Central policy engine that classifies actions and enforces mode-based rules."""

    # Actions that are always allowed regardless of mode (read-only)
    _ALWAYS_ALLOW: set[str] = set()

    # Actions that are always blocked (regardless of mode)
    _ALWAYS_DENY: set[str] = set()

    def __init__(self, is_production: bool = False) -> None:
        self.is_production = is_production

    # ------------------------------------------------------------------
    # Risk classification
    # ------------------------------------------------------------------
    def classify_action(self, intent: str, module: str, *, is_production: bool | None = None) -> SafetyAction:
        """Classify an action and return a :class:`SafetyAction` with risk level.

        Args:
            intent: The action intent string (e.g. ``"DEPLOY_IFLOW"``).
            module: The SAP module being targeted (e.g. ``"Integration"``).
            is_production: Override production flag.

        Returns:
            A :class:`SafetyAction` describing the classified action.
        """
        if is_production is None:
            is_production = self.is_production

        risk = self._resolve_risk(intent, module)
        if risk is None:
            risk = RiskLevel.MEDIUM  # default unknown actions to medium

        requires_approval = risk in (RiskLevel.HIGH, RiskLevel.MEDIUM)
        sandbox_allowed = risk in (RiskLevel.LOW, RiskLevel.MEDIUM)

        # Build a human-readable reason
        reason = self._build_reason(intent, risk, module, is_production)

        return SafetyAction(
            action_id=intent,
            action=intent,
            risk=risk,
            requires_approval=requires_approval,
            reason=reason,
            sandbox_allowed=sandbox_allowed,
        )

    def _resolve_risk(self, intent: str, module: str) -> RiskLevel | None:
        """Look up the risk level for *intent*, checking exact match first then wildcards."""
        # Exact match
        if intent in _POLICY_RULES:
            return _POLICY_RULES[intent]

        # Pattern / wildcard match (order matters: more specific first)
        for pattern, level in sorted(_POLICY_RULES.items()):
            if "*" in pattern and fnmatch.fnmatch(intent, pattern):
                return level

        return None

    @staticmethod
    def _build_reason(intent: str, risk: RiskLevel, module: str, is_prod: bool) -> str:
        parts = [f"Action '{intent}' in module '{module}' is classified as {risk.value.upper()} risk"]
        if is_prod:
            parts.append("(production environment)")
        return "; ".join(parts)

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    def check_action(self, safety_action: SafetyAction, *, mode: str = "sandbox") -> dict[str, Any]:
        """Determine whether *safety_action* is allowed in *mode*.

        Args:
            safety_action: The pre-classified action.
            mode: ``"sandbox"`` or ``"production"``.

        Returns:
            Dict with keys: ``allowed``, ``requires_approval``, ``reason``.
        """
        risk = safety_action.risk
        action_id = safety_action.action_id

        if mode not in ("sandbox", "production"):
            mode = "sandbox"

        # --- Sandbox mode rules ---
        if mode == "sandbox":
            if risk == RiskLevel.CRITICAL:
                return {
                    "allowed": False,
                    "requires_approval": False,
                    "reason": f"CRITICAL actions (including '{action_id}') are blocked in sandbox mode",
                }
            if risk == RiskLevel.HIGH:
                return {
                    "allowed": True,
                    "requires_approval": True,
                    "reason": f"HIGH risk action '{action_id}' requires human approval in sandbox mode",
                }
            # LOW and MEDIUM: allowed without approval
            return {
                "allowed": True,
                "requires_approval": False,
                "reason": f"{risk.value.upper()} risk action '{action_id}' is allowed in sandbox mode",
            }

        # --- Production mode rules ---
        if risk == RiskLevel.CRITICAL:
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": f"CRITICAL actions are blocked in production without explicit approval",
            }
        if risk in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            return {
                "allowed": True,
                "requires_approval": True,
                "reason": f"{risk.value.upper()} risk action '{action_id}' requires approval in production",
            }
        # LOW: allowed without approval
        return {
            "allowed": True,
            "requires_approval": False,
            "reason": f"LOW risk action '{action_id}' is allowed in production",
        }

    # ------------------------------------------------------------------
    # Allowlist / denylist
    # ------------------------------------------------------------------
    def get_allowlist(self) -> set[str]:
        """Return set of action patterns allowed in the current mode."""
        if self.is_production:
            return {p for p, r in _POLICY_RULES.items() if r != RiskLevel.CRITICAL}
        return {p for p, r in _POLICY_RULES.items() if r != RiskLevel.CRITICAL}

    def get_denylist(self) -> set[str]:
        """Return set of action patterns denied in the current mode."""
        if self.is_production:
            return {p for p, r in _POLICY_RULES.items() if r == RiskLevel.CRITICAL}
        return {p for p, r in _POLICY_RULES.items() if r == RiskLevel.CRITICAL}
