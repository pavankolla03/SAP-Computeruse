"""WebSocket support for live agent streaming."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

VALID_API_KEY = "test-api-key"


class AgentWebSocketHandler:
    """Handles WebSocket connections for live agent streaming."""

    def __init__(self) -> None:
        self._connections: dict[str, Any] = {}

    async def connect(self, websocket: Any, api_key: str) -> None:
        """Accept connection after API-key authentication."""
        if api_key != VALID_API_KEY:
            await websocket.close(code=4008, reason="Invalid API key")
            return
        await websocket.accept()
        session_id = str(uuid.uuid4())
        self._connections[session_id] = websocket
        await self._send(websocket, {"type": "connected", "session_id": session_id})
        try:
            while True:
                data = await websocket.receive_text()
                await self._handle(websocket, session_id, data)
        except Exception:
            logger.debug("WebSocket connection closed for %s", session_id)
        finally:
            self._connections.pop(session_id, None)

    async def _handle(self, websocket: Any, session_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self._send(websocket, {"type": "error", "error": "Invalid JSON"})
            return
        await self._send(websocket, {"type": "action_result", "session_id": session_id, "action": message})

    async def _send(self, websocket: Any, payload: dict[str, Any]) -> None:
        try:
            await websocket.send_json(payload)
        except Exception as exc:
            logger.debug("WebSocket send failed: %s", exc)
