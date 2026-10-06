"""SAP task verifiers — programmatic verification for agent actions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_package_exists(env: Any, package_id: str) -> dict[str, Any]:
    """Verify that a package exists in the SAP environment."""
    result = env.get_package(package_id)
    if result is None:
        return {"success": False, "reason": f"Package {package_id} not found"}
    return {"success": True, "package": result}


def verify_iflow_exists(env: Any, package_id: str, iflow_id: str) -> dict[str, Any]:
    """Verify that an iFlow exists in the specified package."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        return {"success": True, "iflow": iflow}
    return {"success": False, "reason": "Unknown environment type"}


def verify_iflow_deployed(env: Any, package_id: str, iflow_id: str) -> dict[str, Any]:
    """Verify that an iFlow is deployed."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        if iflow.get("status") != "DEPLOYED":
            return {"success": False, "reason": f"iFlow {key} status: {iflow.get('status')}"}
        return {"success": True, "status": "DEPLOYED"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_sender_adapter(env: Any, package_id: str, iflow_id: str, adapter_type: str) -> dict[str, Any]:
    """Verify an iFlow has a sender adapter of the specified type."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        for sender in iflow.get("senders", []):
            if sender.get("adapter", "").lower() == adapter_type.lower():
                return {"success": True, "sender": sender}
        return {"success": False, "reason": f"No {adapter_type} sender found"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_receiver_adapter(env: Any, package_id: str, iflow_id: str, adapter_type: str) -> dict[str, Any]:
    """Verify an iFlow has a receiver adapter of the specified type."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        for receiver in iflow.get("receivers", []):
            if receiver.get("adapter", "").lower() == adapter_type.lower():
                return {"success": True, "receiver": receiver}
        return {"success": False, "reason": f"No {adapter_type} receiver found"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_mpl_success(env: Any, iflow_key: str) -> dict[str, Any]:
    """Verify MPL shows a successful message."""
    entries = env.query_mpl(iflow_key) if hasattr(env, "query_mpl") else []
    success_entries = [e for e in entries if e.get("status") == "COMPLETED"]
    if not success_entries:
        return {"success": False, "reason": "No successful MPL entries"}
    return {"success": True, "entries": success_entries, "count": len(success_entries)}


def verify_security_material_exists(env: Any, name: str) -> dict[str, Any]:
    """Verify security material exists."""
    materials = env.security_materials if hasattr(env, "security_materials") else {}
    for mat in materials.values():
        if mat.get("name") == name:
            return {"success": True, "material": mat}
    return {"success": False, "reason": f"Security material '{name}' not found"}


def run_verifier(env: Any, verifier_name: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch to the appropriate verifier function."""
    verifiers = {
        "verify_package_exists": verify_package_exists,
        "verify_iflow_exists": verify_iflow_exists,
        "verify_iflow_deployed": verify_iflow_deployed,
        "verify_sender_adapter": verify_sender_adapter,
        "verify_receiver_adapter": verify_receiver_adapter,
        "verify_mpl_success": verify_mpl_success,
        "verify_security_material_exists": verify_security_material_exists,
    }
    verifier = verifiers.get(verifier_name)
    if verifier is None:
        return {"success": False, "reason": f"Unknown verifier: {verifier_name}"}
    return verifier(env, **kwargs)
