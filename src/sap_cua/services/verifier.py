"""SAP task verifiers — programmatic verification for agent actions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def verify_package_exists(env: Any, package_id: str) -> dict[str, Any]:
    """Verify that a package exists in the SAP environment."""
    from sap_cua.runtime.sap_api import SAPAPIClient
    if isinstance(env,SAPAPIClient):
        from sap_cua.runtime.sap_api.verification import verify_package
        return verify_package(env,package_id)
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
    """Verify MPL shows a successful message for an iFlow."""
    entries = env.query_mpl(iflow_key) if hasattr(env, "query_mpl") else []
    success_entries = [e for e in entries if e.get("status") == "COMPLETED"]
    if not success_entries:
        return {"success": False, "reason": "No successful MPL entries"}
    return {"success": True, "entries": success_entries, "count": len(success_entries)}


# ── New verifiers ────────────────────────────────────────────────────────────

def verify_security_material_exists(env: Any, name: str) -> dict[str, Any]:
    """Verify security material exists by name."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        materials = env.security_materials if hasattr(env, "security_materials") else {}
        for mat_id, mat in materials.items():
            if mat.get("name") == name or mat_id == name:
                return {"success": True, "material_id": mat_id, "material": mat}
        return {"success": False, "reason": f"Security material '{name}' not found"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_message_status(env: Any, message_id: str, expected_status: str) -> dict[str, Any]:
    """Check MPL message status for a given message_id."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        entries = env.mpl_entries if hasattr(env, "mpl_entries") else []
        for entry in entries:
            if entry.get("message_id") == message_id:
                actual = entry.get("status", "UNKNOWN")
                if actual == expected_status:
                    return {"success": True, "message_id": message_id, "status": actual}
                return {
                    "success": False,
                    "reason": f"Message {message_id} has status '{actual}', expected '{expected_status}'",
                }
        return {"success": False, "reason": f"Message {message_id} not found in MPL"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_api_proxy_deployed(env: Any, proxy_name: str) -> dict[str, Any]:
    """Check that an APIM proxy is deployed."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        proxies = env.api_proxies if hasattr(env, "api_proxies") else {}
        proxy = proxies.get(proxy_name)
        if proxy is None:
            return {"success": False, "reason": f"API proxy '{proxy_name}' not found"}
        if proxy.get("status") != "DEPLOYED":
            return {"success": False, "reason": f"Proxy '{proxy_name}' status: {proxy.get('status')}"}
        return {"success": True, "proxy": proxy}
    return {"success": False, "reason": "Unknown environment type"}


def verify_http_response(env: Any, url: str, expected_status: int = 200) -> dict[str, Any]:
    """Check that an HTTP endpoint responds with the expected status code.

    No HTTP observation provider is connected yet. This verifier fails until an
    actual response or an explicit test fixture can be checked.
    """
    return {"success": False, "reason": "HTTP verification has no observed response",
            "url": url, "expected_status": expected_status}


def verify_external_parameter(env: Any, iflow_key: str, param_name: str) -> dict[str, Any]:
    """Check that an external parameter exists on a deployed iFlow."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        parts = iflow_key.split(":")
        if len(parts) != 2:
            return {"success": False, "reason": f"Invalid iflow_key format: {iflow_key}. Expected 'package:iflow'"}
        package_id, iflow_id = parts
        key = iflow_key
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        # Mock stores external parameters in a top-level 'external_parameters' list.
        ext_params = iflow.get("external_parameters", [])
        for param in ext_params:
            if param.get("name") == param_name:
                return {"success": True, "parameter": param}
        return {"success": False, "reason": f"External parameter '{param_name}' not found on iFlow {key}"}
    return {"success": False, "reason": "Unknown environment type"}


def verify_iflow_saved(env: Any, package_id: str, iflow_id: str) -> dict[str, Any]:
    """Check that an iFlow has been saved (not just created)."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        saved_at = iflow.get("saved_at")
        if saved_at is None:
            return {"success": False, "reason": f"iFlow {key} has not been saved yet"}
        return {"success": True, "iflow_id": iflow_id, "saved_at": saved_at}
    return {"success": False, "reason": "Unknown environment type"}


def verify_components_present(env: Any, package_id: str, iflow_id: str, components: list[str]) -> dict[str, Any]:
    """Check that multiple components of the specified types exist in an iFlow."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        key = f"{package_id}:{iflow_id}"
        iflow = env.iFlows.get(key)
        if iflow is None:
            return {"success": False, "reason": f"iFlow {key} not found"}
        actual_types = {c.get("type", "").lower() for c in iflow.get("components", [])}
        expected_types = {c.lower() for c in components}
        missing = expected_types - actual_types
        found = expected_types & actual_types
        if missing:
            return {
                "success": False,
                "reason": f"Missing components: {sorted(missing)}",
                "found": sorted(found),
                "missing": sorted(missing),
            }
        return {"success": True, "components": sorted(found)}
    return {"success": False, "reason": "Unknown environment type"}


def verify_package_deleted(env: Any, package_id: str) -> dict[str, Any]:
    """Check that a package no longer exists."""
    from sap_cua.sap.mocks import SAPMockEnvironment
    if isinstance(env, SAPMockEnvironment):
        if package_id in env.packages:
            return {"success": False, "reason": f"Package {package_id} still exists"}
        return {"success": True, "message": f"Package {package_id} has been deleted"}
    return {"success": False, "reason": "Unknown environment type"}


# ── Dispatcher ───────────────────────────────────────────────────────────────

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
        "verify_message_status": verify_message_status,
        "verify_api_proxy_deployed": verify_api_proxy_deployed,
        "verify_http_response": verify_http_response,
        "verify_external_parameter": verify_external_parameter,
        "verify_iflow_saved": verify_iflow_saved,
        "verify_components_present": verify_components_present,
        "verify_package_deleted": verify_package_deleted,
    }
    verifier = verifiers.get(verifier_name)
    if verifier is None:
        return {"success": False, "reason": f"Unknown verifier: {verifier_name}"}
    return verifier(env, **kwargs)


def verify_task_state(env: Any, specification: dict[str, Any] | None) -> dict[str, Any]:
    """Verify trusted task criteria against observed state; never model confidence."""
    if not isinstance(specification, dict) or not specification:
        return {"success": False, "reason": "No task verification criteria supplied"}
    if "all" in specification:
        checks = specification["all"]
        if not isinstance(checks, list) or not checks:
            return {"success": False, "reason": "Verification requires at least one check"}
        results = [verify_task_state(env, check) for check in checks]
        return {"success": all(r.get("success") is True for r in results), "checks": results}
    try:
        if not isinstance(specification, dict):
            raise TypeError("Verifier specification must be an object")
        name = specification.get("type", "")
        if not isinstance(name, str) or not name:
            raise ValueError("Verifier type is required")
        name = name if name.startswith("verify_") else "verify_" + name
        args = {k: v for k, v in specification.items() if k != "type"}
        return run_verifier(env, name, **args)
    except (TypeError, ValueError, AttributeError) as exc:
        return {"success": False, "reason": f"Invalid verifier specification: {exc}"}
