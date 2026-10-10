"""Read-only connectivity readiness, without returning credentials or SAP payloads."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from urllib.parse import urlsplit

from sap_cua.runtime.sap_api import SAPAPIClient, secure_url

KEYS = ("SAP_API_BASE_URL", "SAP_TOKEN_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET")


def connection_status(environment: Mapping[str, str] | None = None):
    environment = os.environ if environment is None else environment
    missing = [key for key in KEYS if not environment.get(key, "").strip()]
    invalid = []
    for key in KEYS[:2]:
        if key not in missing:
            try:
                secure_url(environment[key])
            except ValueError:
                invalid.append(key)
    return {
        "configured": not missing and not invalid,
        "missing": missing,
        "invalid": invalid,
        "mode": "read_only",
        "live_execution_enabled": False,
        "tenant_host": urlsplit(environment["SAP_API_BASE_URL"]).hostname
        if "SAP_API_BASE_URL" not in missing + invalid
        else None,
    }


def probe_connection(client: SAPAPIClient):
    """A successful GET establishes access to that resource, not mutation permission."""
    start = time.monotonic()
    checks = []
    operations = [
        ("packages", client.list_packages),
        ("runtime_artifacts", client.list_runtime_artifacts),
        ("message_logs", lambda: client.query_mpl({"$select": "MessageGuid,Status"}, limit=1)),
    ]
    for name, operation in operations:
        response = operation()
        payload = response.get("data")
        valid = (
            response.get("success") is True
            and isinstance(payload, dict)
            and isinstance(payload.get("results"), list)
        )
        checks.append(
            {
                "resource": name,
                "success": valid,
                "status_code": response.get("status_code"),
                "reason": "read_access_confirmed"
                if valid
                else "unexpected_response"
                if response.get("success")
                else "request_failed",
            }
        )
        # Avoid repeated OAuth failures or requests after a network/config failure.
        if response.get("outcome") in ("not_sent", "unknown") or response.get("status_code") == 401:
            break
    return {
        "success": len(checks) == len(operations) and all(c["success"] for c in checks),
        "mode": "read_only",
        "checked_at": time.time(),
        "duration_ms": round((time.monotonic() - start) * 1000),
        "checks": checks,
        "live_execution_enabled": False,
        "identity_verified": False,
        "write_permissions_verified": False,
    }


def probe_configured_connection():
    status = connection_status()
    if not status["configured"]:
        return {**status, "success": False, "checks": []}
    with SAPAPIClient(timeout_seconds=10, allow_mutations=False) as client:
        return {**status, **probe_connection(client)}


class ProbeBusy(RuntimeError):
    pass


class ConnectionService:
    def __init__(self):
        from threading import Lock

        self._lock = Lock()
        self.last_probe = None

    def status(self):
        return {**connection_status(), "last_probe": self.last_probe}

    def probe(self):
        if not self._lock.acquire(blocking=False):
            raise ProbeBusy("A connection check is already running")
        try:
            self.last_probe = probe_configured_connection()
            return self.last_probe
        finally:
            self._lock.release()
