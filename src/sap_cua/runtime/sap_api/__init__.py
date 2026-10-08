"""SAP Cloud Integration OData client with per-instance OAuth and explicit mutations.

No implicit mock fallback, cross-host redirects, or automatic write retries.
Tenant permissions, CSRF requirements and supported resources need tenant validation.
"""

from __future__ import annotations

import base64
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", value):
        raise ValueError("Invalid SAP artifact identifier")
    return value


def secure_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("SAP endpoint must be an HTTPS URL without credentials, query or fragment")
    return value.rstrip("/")


class SAPAPIClient:
    def __init__(
        self,
        base_url: str = "",
        api_base: str = "",
        client_id: str = "",
        client_secret: str = "",
        *,
        token_url: str = "",
        allow_mutations: bool = False,
        transport: httpx.BaseTransport | None = None,
    ):
        self.api_base = secure_url(
            api_base
            or os.getenv("SAP_API_BASE_URL")
            or (base_url.rstrip("/") + "/api/v1" if base_url else "")
        )
        self.token_url = secure_url(token_url or os.getenv("SAP_TOKEN_URL", ""))
        self.client_id = client_id or os.getenv("SAP_CLIENT_ID", "")
        self._secret = client_secret or os.getenv("SAP_CLIENT_SECRET", "")
        if not self.client_id or not self._secret:
            raise ValueError(
                "SAP OAuth credentials are required; use SAPMockEnvironment explicitly for simulation"
            )
        self.allow_mutations = allow_mutations
        self._client = httpx.Client(transport=transport, timeout=30, follow_redirects=False)
        self._token = ""
        self._expires = 0.0

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _access_token(self) -> str:
        if time.monotonic() < self._expires:
            return self._token
        response = self._client.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=httpx.BasicAuth(self.client_id, self._secret),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"SAP OAuth failed (HTTP {response.status_code}); response body withheld"
            )
        payload = response.json()
        self._token = payload["access_token"]
        self._expires = time.monotonic() + max(0, float(payload.get("expires_in", 300)) - 30)
        return self._token

    def _request(self, method: str, resource: str, *, body=None, params=None) -> dict[str, Any]:
        if method != "GET" and not self.allow_mutations:
            return {
                "success": False,
                "data": None,
                "error": "Live mutations require explicit authorization",
                "backend": "sap_api",
            }
        try:
            response = self._client.request(
                method,
                self.api_base + "/" + resource,
                headers={
                    "Authorization": "Bearer " + self._access_token(),
                    "Accept": "application/json",
                },
                json=body,
                params=params,
            )
            # Acceptance of deployment is NOT proof the runtime reached STARTED.
            success = 200 <= response.status_code < 300
            if not success:
                return {
                    "success": False,
                    "data": None,
                    "status_code": response.status_code,
                    "error": f"SAP returned HTTP {response.status_code}; response body withheld",
                    "backend": "sap_api",
                }
            if not response.content:
                data = None
            elif "json" in response.headers.get("content-type", ""):
                data = response.json()
                if isinstance(data, dict):
                    data = data.get("d", data)
            else:
                data = {"task_id": response.text.strip().strip('"')}
            return {
                "success": True,
                "data": data,
                "status_code": response.status_code,
                "error": None,
                "backend": "sap_api",
            }
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as exc:
            # Never include request headers, credentials, response bodies, or untrusted exception text.
            return {
                "success": False,
                "data": None,
                "error": f"SAP request failed ({type(exc).__name__}); writes were not retried",
                "backend": "sap_api",
            }

    def create_package(self, name: str, description: str = "", *, package_id: str | None = None):
        return self._request(
            "POST",
            "IntegrationPackages",
            body={
                "Id": identifier(package_id or name),
                "Name": name,
                "Description": description,
                "ShortText": description[:100],
            },
        )

    def get_package(self, package_id: str):
        return self._request("GET", f"IntegrationPackages('{identifier(package_id)}')")

    def update_package(self, package_id: str, data: dict[str, Any]):
        if set(data) - {"Name", "Description", "ShortText", "Version", "Vendor"}:
            raise ValueError("Unsupported package field")
        return self._request("PUT", f"IntegrationPackages('{identifier(package_id)}')", body=data)

    def delete_package(self, package_id: str):
        return self._request("DELETE", f"IntegrationPackages('{identifier(package_id)}')")

    def get_iflows(self, package_id: str):
        return self._request(
            "GET", f"IntegrationPackages('{identifier(package_id)}')/IntegrationDesigntimeArtifacts"
        )

    def create_iflow(
        self, package_id: str, name: str, *, artifact_zip: bytes, iflow_id: str | None = None
    ):
        if not artifact_zip.startswith(b"PK") or len(artifact_zip) > 20_000_000:
            raise ValueError("A valid, bounded iFlow ZIP artifact is required")
        return self._request(
            "POST",
            "IntegrationDesigntimeArtifacts",
            body={
                "Id": identifier(iflow_id or name),
                "Name": name,
                "PackageId": identifier(package_id),
                "ArtifactContent": base64.b64encode(artifact_zip).decode(),
            },
        )

    def deploy_iflow(self, package_id: str, iflow_id: str, version: str = "active"):
        identifier(package_id)
        return self._request(
            "POST",
            "DeployIntegrationDesigntimeArtifact",
            params={"Id": f"'{identifier(iflow_id)}'", "Version": f"'{identifier(version)}'"},
        )

    def deployment_status(self, task_id: str):
        return self._request("GET", f"BuildAndDeployStatus(TaskId='{identifier(task_id)}')")

    def runtime_status(self, iflow_id: str):
        return self._request("GET", f"IntegrationRuntimeArtifacts('{identifier(iflow_id)}')")

    def query_mpl(self, filters: dict[str, Any] | None = None, limit: int = 100):
        if not 1 <= limit <= 500:
            raise ValueError("MPL limit must be between 1 and 500")
        params = {"$top": limit, "$orderby": "LogStart desc", **(filters or {})}
        if set(params) - {"$top", "$orderby", "$filter", "$skip", "$select"}:
            raise ValueError("Unsupported MPL query option")
        return self._request("GET", "MessageProcessingLogs", params=params)

    def get_security_materials(self, filter_expr: str | None = None):
        raise NotImplementedError(
            "Security material access requires a separately authorized resource-specific implementation"
        )
