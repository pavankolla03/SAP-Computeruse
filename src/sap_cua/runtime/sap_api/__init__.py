"""SAP API client — typed, retry-capable HTTP client for SAP Integration Suite.

All methods return a dict of the form ``{"success": bool, "data": Any,
"error": str | None}``.  When the required environment variables are absent,
the client falls back to a *mock mode* so that callers do not have to special-
case development environments.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─── Environment defaults ────────────────────────────────────────────────────

ENV_BASE_URL = os.getenv("SAP_BASE_URL", "")
ENV_API_BASE = os.getenv("SAP_API_BASE_URL", "")
ENV_CLIENT_ID = os.getenv("SAP_CLIENT_ID", "")
ENV_CLIENT_SECRET = os.getenv("SAP_CLIENT_SECRET", "")

_IS_MOCK = not (ENV_BASE_URL and ENV_API_BASE and ENV_CLIENT_ID and ENV_CLIENT_SECRET)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_headers() -> dict[str, str]:
    return {"Content-Type": "application/json"}


def _build_auth() -> httpx.Auth | None:
    """Return a BasicAuth if credentials are configured."""
    if _IS_MOCK:
        return None
    return httpx.BasicAuth(ENV_CLIENT_ID, ENV_CLIENT_SECRET)


def _base_url() -> str:
    return ENV_API_BASE or f"{ENV_BASE_URL.rstrip('/')}/api/v1"


def _mock_success(data: Any = None) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def _mock_failure(error: str) -> dict[str, Any]:
    return {"success": False, "data": None, "error": error}


# ─── Retry logic ─────────────────────────────────────────────────────────────

_RETRYABLE = {429, 500, 502, 503, 504}


def _call_with_retry(
    method: str,
    url: str,
    client: httpx.Client,
    json_body: dict[str, Any] | None = None,
    max_attempts: int = 3,
    backoff: float = 1.0,
) -> httpx.Response:
    """Make an HTTP request with exponential-backoff retry on 5xx / 429."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.request(
                method,
                url,
                json=json_body,
                headers=_build_headers(),
                auth=_build_auth(),
                timeout=30,
            )
            if resp.status_code not in _RETRYABLE:
                return resp
            # retryable
            logger.warning(
                "SAP API %s %s returned %d (attempt %d/%d)",
                method, url, resp.status_code, attempt, max_attempts,
            )
        except httpx.HTTPError as exc:
            last_exc = exc
            logger.warning(
                "SAP API %s %s raised %s (attempt %d/%d)",
                method, url, exc, attempt, max_attempts,
            )
        time.sleep(backoff * (2 ** (attempt - 1)))
    if last_exc:
        raise last_exc
    return resp  # type: ignore[possibly-undefined]


# ─── SAPAPIClient ─────────────────────────────────────────────────────────────

class SAPAPIClient:
    """Typed SAP Integration Suite REST API client.

    Falls back to mock mode when env vars are absent.
    """

    def __init__(
        self,
        base_url: str = "",
        api_base: str = "",
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        global _IS_MOCK
        self.base_url = base_url or ENV_BASE_URL
        self.api_base = api_base or ENV_API_BASE or f"{self.base_url.rstrip('/')}/api/v1"
        self.client_id = client_id or ENV_CLIENT_ID
        self.client_secret = client_secret or ENV_CLIENT_SECRET

        self._is_mock = not (
            self.base_url and self.client_id and self.client_secret
        )
        self._client: httpx.Client | None = None

    # ─── Lifecycle ──────────────────────────────────────────────────────────

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(base_url=self.api_base, timeout=30)
        return self._client

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> SAPAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ─── Package management ────────────────────────────────────────────────

    def create_package(
        self, name: str, description: str = ""
    ) -> dict[str, Any]:
        """Create a new integration package.

        POST /api/v1/Packages
        """
        if self._is_mock:
            return _mock_success({"id": f"pkg_{name.lower()}", "name": name, "description": description})
        client = self._get_client()
        body = {"name": name, "description": description}
        try:
            resp = _call_with_retry("POST", "/Packages", client, body)
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    def get_package(self, package_id: str) -> dict[str, Any]:
        """Get a package by ID.

        GET /api/v1/Packages('{id}')
        """
        if self._is_mock:
            return _mock_success(
                {"id": package_id, "name": package_id, "description": ""}
            )
        client = self._get_client()
        try:
            resp = _call_with_retry(
                "GET", f"/Packages('{package_id}')", client
            )
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    def update_package(self, package_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a package.

        PATCH /api/v1/Packages('{id}')
        """
        if self._is_mock:
            return _mock_success({"id": package_id, **data})
        client = self._get_client()
        try:
            resp = _call_with_retry(
                "PATCH", f"/Packages('{package_id}')", client, data
            )
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    def delete_package(self, package_id: str) -> dict[str, Any]:
        """Delete a package.

        DELETE /api/v1/Packages('{id}')
        """
        if self._is_mock:
            return _mock_success({"deleted": True, "id": package_id})
        client = self._get_client()
        try:
            resp = _call_with_retry(
                "DELETE", f"/Packages('{package_id}')", client
            )
            resp.raise_for_status()
            return _mock_success({"deleted": True, "id": package_id})
        except Exception as exc:
            return _mock_failure(str(exc))

    # ─── iFlow management ──────────────────────────────────────────────────

    def get_iflows(self, package_id: str) -> dict[str, Any]:
        """Get all integration flows in a package.

        GET /api/v1/IntegrationDesigntimeArtifacts?$filter=package eq '{id}'
        """
        if self._is_mock:
            return _mock_success([])
        client = self._get_client()
        try:
            resp = _call_with_retry(
                "GET",
                f"/IntegrationDesigntimeArtifacts?$filter=package eq '{package_id}'",
                client,
            )
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    def create_iflow(
        self, package_id: str, name: str, iflow_type: str = "INTEGRATION_FLOW"
    ) -> dict[str, Any]:
        """Create a new integration flow in a package.

        POST /api/v1/IntegrationDesigntimeArtifacts
        """
        if self._is_mock:
            return _mock_success(
                {"id": f"iflow_{name.lower()}", "name": name, "type": iflow_type}
            )
        client = self._get_client()
        body = {
            "name": name,
            "type": iflow_type,
            "packageId": package_id,
        }
        try:
            resp = _call_with_retry(
                "POST", "/IntegrationDesigntimeArtifacts", client, body
            )
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    def deploy_iflow(self, package_id: str, iflow_id: str) -> dict[str, Any]:
        """Deploy an integration flow.

        POST /api/v1/Deploy
        """
        if self._is_mock:
            return _mock_success(
                {
                    "id": f"deploy_{iflow_id}",
                    "status": "STARTED",
                    "message": f"Deployment of {iflow_id} started",
                }
            )
        client = self._get_client()
        body = {
            "message": f"Deploy {iflow_id}",
            "packageId": package_id,
            "artifactId": iflow_id,
        }
        try:
            resp = _call_with_retry("POST", "/Deploy", client, body)
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    # ─── Monitoring ────────────────────────────────────────────────────────

    def query_mpl(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Query the Message Processing Log.

        GET /api/v1/MessageProcessingLogs
        """
        if self._is_mock:
            return _mock_success([])
        client = self._get_client()
        params = filters or {}
        params.setdefault("$top", min(limit, 500))
        try:
            resp = _call_with_retry("GET", "/MessageProcessingLogs", client)
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))

    # ─── Security ──────────────────────────────────────────────────────────

    def get_security_materials(
        self, filter_expr: str | None = None
    ) -> dict[str, Any]:
        """Get security materials (certificates, key stores, etc.).

        GET /api/v1/SecurityMaterial
        """
        if self._is_mock:
            return _mock_success([])
        client = self._get_client()
        url = "/SecurityMaterial"
        if filter_expr:
            url += f"?$filter={filter_expr}"
        try:
            resp = _call_with_retry("GET", url, client)
            resp.raise_for_status()
            return _mock_success(resp.json())
        except Exception as exc:
            return _mock_failure(str(exc))
