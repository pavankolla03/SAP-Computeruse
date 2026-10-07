"""MCP (Model Context Protocol) executor for SAP-CUA."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class MCPConnectionError(RuntimeError):
    """Raised when an MCP server cannot be reached."""


class MCPExecutor:
    """Executor for calling tools exposed by an MCP server.

    The executor supports two transport modes:
    - ``stdio``: spawn the server as a subprocess (Claude-style MCP)
    - ``http``:  talk to a remote MCP server

    The executor is intentionally agnostic of the underlying MCP SDK so that
    it remains importable even when ``mcp`` is not installed.  When an MCP
    SDK is available, ``_connect`` can be extended to wire it in.
    """

    def __init__(
        self,
        server_name: str = "default",
        transport: str = "stdio",
        command: list[str] | None = None,
        url: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.server_name = server_name
        self.transport = transport
        self.command = command or os.getenv("MCP_COMMAND", "").split()
        self.url = url or os.getenv("MCP_URL")
        self.timeout = timeout
        self._connected = False
        self._client = None  # lazily connected MCP client, when available

    # ─── Lifecycle ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Establish a connection to the configured MCP server."""
        if self._connected:
            return

        if self.transport == "stdio":
            self._connect_stdio()
        elif self.transport == "http":
            self._connect_http()
        else:
            raise MCPConnectionError(f"Unknown transport: {self.transport}")

        self._connected = True
        logger.info(
            "Connected to MCP server '%s' via %s", self.server_name, self.transport
        )

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._client is not None:
            try:
                close = getattr(self._client, "close", None)
                if callable(close):
                    close()
            except Exception as exc:
                logger.warning("Error closing MCP client: %s", exc)
            self._client = None
        self._connected = False
        logger.info("Disconnected from MCP server '%s'", self.server_name)

    # ─── Public API ────────────────────────────────────────────────────────

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Invoke *tool_name* on the connected server.

        Returns a dict of the form
        ``{"success": bool, "data": Any, "error": str|None}``.
        """
        if not self._connected:
            self.connect()
        arguments = arguments or {}
        try:
            if self._client is not None and hasattr(self._client, "call_tool"):
                result = self._client.call_tool(tool_name, arguments)
                return {"success": True, "data": result, "error": None}
            return self._fallback_call(tool_name, arguments)
        except MCPConnectionError:
            return {"success": False, "data": None, "error": "MCP server unavailable"}
        except Exception as exc:
            logger.error("MCP call_tool(%s) failed: %s", tool_name, exc)
            return {"success": False, "data": None, "error": str(exc)}

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools exposed by the server."""
        if not self._connected:
            self.connect()
        try:
            if self._client is not None and hasattr(self._client, "list_tools"):
                return self._client.list_tools()
            return self._fallback_list_tools()
        except MCPConnectionError:
            logger.warning("MCP server unavailable when listing tools")
            return []
        except Exception as exc:
            logger.error("MCP list_tools failed: %s", exc)
            return []

    # ─── Internal helpers ──────────────────────────────────────────────────

    def _connect_stdio(self) -> None:
        """Try to connect via an MCP SDK; otherwise use stdio fallback."""
        if not self.command:
            logger.warning(
                "MCP stdio transport requires 'command'; using fallback mode"
            )
            return
        try:
            from mcp.client.stdio import stdio_client  # type: ignore

            self._client = stdio_client(self.command)
            logger.debug("MCP stdio client initialized for %s", self.command)
        except ImportError:
            logger.info("MCP SDK not installed; using stdio JSON-RPC fallback")
            self._client = None

    def _connect_http(self) -> None:
        """Try to connect via HTTP; otherwise use HTTP fallback."""
        if not self.url:
            raise MCPConnectionError(
                "HTTP transport requires a 'url' (or MCP_URL env var)"
            )
        try:
            from mcp.client.http import HttpStreamClient  # type: ignore

            self._client = HttpStreamClient(self.url, timeout=self.timeout)
            logger.debug("MCP HTTP client initialized for %s", self.url)
        except ImportError:
            logger.info("MCP SDK not installed; using HTTP JSON-RPC fallback")
            self._client = None

    def _fallback_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Stand-in call implementation when MCP SDK is not present."""
        if self.transport == "http" and self.url:
            import httpx
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            try:
                resp = httpx.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return {"success": True, "data": data.get("result"), "error": None}
            except Exception as exc:
                return {"success": False, "data": None, "error": str(exc)}
        return {
            "success": False,
            "data": None,
            "error": f"No MCP SDK available to call '{tool_name}'",
        }

    def _fallback_list_tools(self) -> list[dict[str, Any]]:
        """Fallback: query the HTTP server, or return an empty list."""
        if self.transport == "http" and self.url:
            try:
                import httpx
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                }
                resp = httpx.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data.get("result", [])
            except Exception as exc:
                logger.warning("Fallback list_tools failed: %s", exc)
        return []

    # ─── Context manager ──────────────────────────────────────────────────

    def __enter__(self) -> MCPExecutor:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()

    # ─── Serialization helpers ─────────────────────────────────────────────

    @staticmethod
    def serialize_request(
        tool_name: str, arguments: dict[str, Any], request_id: int = 1
    ) -> str:
        """Serialize a tool call to a JSON-RPC string."""
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
        )

    @staticmethod
    def deserialize_response(payload: str) -> dict[str, Any]:
        """Deserialize a JSON-RPC response string."""
        return json.loads(payload)