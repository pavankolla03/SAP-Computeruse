"""SAP-CUA SAP gateway service.

Routes requests to a live SAP instance or falls back to a mock environment
depending on configuration and feature flags.
"""

from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SAPGatewayConfig(BaseModel):
    """Configuration for the SAP gateway.

    All values are read from environment variables with sensible defaults.
    """

    model_config = {"extra": "ignore"}

    sap_environment: str = "sandbox"
    sap_base_url: str = ""
    sap_api_base_url: str = ""
    sap_client_id: str = ""
    sap_client_secret: str = ""
    sap_user: str = ""
    sap_password: str = ""
    sap_token_endpoint: str = ""

    # Feature flags: action -> bool
    feature_flags: dict[str, bool] = field(default_factory=dict)

    def is_live(self) -> bool:
        """Return True when credentials indicate a live SAP connection."""
        return bool(self.sap_client_id and self.sap_client_secret)

    def action_enabled(self, action: str) -> bool:
        """Return True if *action* is allowed by feature flags."""
        if not self.feature_flags:
            return True
        return self.feature_flags.get(action, True)

    @classmethod
    def from_env(cls) -> SAPGatewayConfig:
        """Build config from environment variables."""
        return cls(
            sap_environment=os.environ.get("SAP_ENVIRONMENT", "sandbox"),
            sap_base_url=os.environ.get("SAP_BASE_URL", ""),
            sap_api_base_url=os.environ.get("SAP_API_BASE_URL", ""),
            sap_client_id=os.environ.get("SAP_CLIENT_ID", ""),
            sap_client_secret=os.environ.get("SAP_CLIENT_SECRET", ""),
            sap_user=os.environ.get("SAP_USER", ""),
            sap_password=os.environ.get("SAP_PASSWORD", ""),
            sap_token_endpoint=os.environ.get("SAP_TOKEN_ENDPOINT", ""),
            feature_flags={
                k.replace("SAP_FF_", "").lower(): v
                for k, v in os.environ.items()
                if k.startswith("SAP_FF_")
            },
        )


class SAPGateway:
    """Routes SAP API calls to live client or mock based on config."""

    def __init__(self, config: SAPGatewayConfig | None = None) -> None:
        self._config = config or SAPGatewayConfig.from_env()
        self._client: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_live(self) -> bool:
        """True when SAP credentials are configured."""
        return self._config.is_live()

    def get_client(self) -> Any:
        """Return a live SAPAPIClient or a mock client."""
        if self._client is None:
            if self.is_live():
                try:
                    from sap_cua.runtime.sap_api import SAPAPIClient
                    self._client = SAPAPIClient()
                except ImportError:
                    logger.warning("SAPAPIClient unavailable; falling back to mock")
                    self._client = _MockClient()
            else:
                self._client = _MockClient()
        return self._client

    def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch *action* to the appropriate client.

        Args:
            action: The SAP API action to execute.
            args: Arguments for the action.

        Returns:
            Result dict from the client.
        """
        if not self._config.action_enabled(action):
            return {"status": "disabled", "action": action, "message": "Feature flag disabled"}

        client = self.get_client()
        method = getattr(client, action, None)
        if method is None:
            return {"status": "error", "action": action, "error": f"Unknown action: {action}"}
        try:
            result = method(**args) if callable(method) else method
            return result if isinstance(result, dict) else {"result": result}
        except TypeError:
            # positional fallback for mock clients
            return method(args)
        except Exception as exc:
            logger.error("SAP action %s failed: %s", action, exc)
            return {"status": "error", "action": action, "error": str(exc)}

    def health_check(self) -> dict[str, Any]:
        """Return gateway health information."""
        live = self.is_live()
        try:
            client = self.get_client()
            if not live:
                client_status = "mock"
            else:
                client_status = "ok"
        except Exception as exc:
            client_status = f"error: {exc}"

        return {
            "status": "healthy",
            "environment": self._config.sap_environment,
            "live": live,
            "client": client_status,
            "feature_flags": self._config.feature_flags,
        }

    @property
    def environment(self) -> str:
        return self._config.sap_environment


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class _MockClient:
    """Minimal mock SAP API client for testing and sandbox mode."""

    def create_package(self, name: str, **kwargs: Any) -> dict[str, Any]:
        return {"package_id": f"mock-{name}", "status": "created"}

    def get_package(self, package_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"package_id": package_id, "status": "found", "iflows": []}

    def update_package(self, package_id: str, data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {"package_id": package_id, "status": "updated"}

    def delete_package(self, package_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"package_id": package_id, "status": "deleted"}

    def get_iflows(self, package_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"package_id": package_id, "iflows": []}

    def create_iflow(self, package_id: str, name: str, **kwargs: Any) -> dict[str, Any]:
        return {"iflow_id": f"mock-{name}", "package_id": package_id, "status": "created"}

    def deploy_iflow(self, package_id: str, iflow_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"iflow_id": iflow_id, "package_id": package_id, "status": "deployed"}

    def query_mpl(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {"results": [], "query": query}

    def get_security_materials(self, **kwargs: Any) -> dict[str, Any]:
        return {"materials": []}

    def close(self) -> None:
        pass

    def __enter__(self) -> _MockClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
