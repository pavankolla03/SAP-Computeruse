"""One controlled runtime test, bounded response assertions, and exact MPL identity.

No redirects, implicit credential reuse, response-body persistence, or send retries.
The approved iFlow must expose its MPL identifier in the response header.
"""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime

import httpx

from sap_cua.runtime.sap_api import identifier
from sap_cua.runtime.sap_api.profiles import runtime_path


class RuntimeTestClient:
    def __init__(self, profile, *, transport=None, max_bytes=1_000_000):
        self.profile = profile
        self.max_bytes = max_bytes
        self.client = httpx.Client(
            timeout=15,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    @staticmethod
    def _read(response, limit, deadline):
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise ValueError("Encoded responses are outside the bounded test contract")
        data = bytearray()
        # No coalescing buffer: inspect every received chunk, including tiny
        # trickles that would otherwise postpone the deadline check indefinitely.
        for chunk in response.iter_bytes():
            if len(data) + len(chunk) > limit or time.monotonic() > deadline:
                raise ValueError("Response observation budget exceeded")
            data.extend(chunk)
        return bytes(data)

    def send(self, test):
        path = runtime_path(test["path"], self.profile.allowed_test_prefix)
        body = test.get("body", "")
        expected = test["expected_status"]
        contains = test["response_contains"]
        content_type = test.get("content_type", "application/json")
        if (
            test.get("method", "POST") != "POST"
            or not isinstance(body, str)
            or len(body.encode()) > 65536
            or not 200 <= expected < 300
            or not isinstance(contains, str)
            or not 1 <= len(contains) <= 4000
            or content_type not in ("application/json", "application/xml", "text/plain")
        ):
            raise ValueError("Invalid functional test contract")
        if not all(
            (
                self.profile.runtime_base,
                self.profile.runtime_token_url,
                self.profile.runtime_client_id.get_secret_value(),
                self.profile.runtime_client_secret.get_secret_value(),
            )
        ):
            raise ValueError("Runtime OAuth configuration is incomplete")
        result = {
            "success": False,
            "outcome": "not_sent",
            "status_code": None,
            "message_id": None,
            "started_at": None,
            "assertions": {},
            "error": None,
        }
        sent = False
        try:
            with self.client.stream(
                "POST",
                self.profile.runtime_token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(
                    self.profile.runtime_client_id.get_secret_value(),
                    self.profile.runtime_client_secret.get_secret_value(),
                ),
                headers={"Accept-Encoding": "identity"},
            ) as token_response:
                if token_response.status_code != 200:
                    result["error"] = "Runtime OAuth failed; test was not sent"
                    return result
                token = json.loads(self._read(token_response, 65536, time.monotonic() + 30))
            lifetime = float(token.get("expires_in", 300)) if isinstance(token, dict) else 0
            if (
                not isinstance(token, dict)
                or not isinstance(token.get("access_token"), str)
                or not 1 <= len(token["access_token"]) <= 8192
                or not math.isfinite(lifetime)
                or lifetime <= 0
            ):
                raise ValueError("Invalid OAuth response")
            result["started_at"] = datetime.now(UTC).isoformat()
            sent = True
            deadline = time.monotonic() + 30
            with self.client.stream(
                "POST",
                self.profile.runtime_base + path,
                content=body.encode(),
                headers={
                    "Authorization": "Bearer " + token["access_token"],
                    "Content-Type": content_type,
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                result.update(status_code=response.status_code, outcome="definite")
                try:
                    data = self._read(response, self.max_bytes, deadline)
                except ValueError:
                    result["error"] = (
                        "Runtime response exceeded observation budget; send not retried"
                    )
                    return result
                response_text = data.decode("utf-8", errors="replace")
                observed_id = response.headers.get("sap_messageprocessinglogid")
                if observed_id:
                    try:
                        result["message_id"] = identifier(observed_id)
                    except ValueError:
                        pass
                result["assertions"] = {
                    "status_matches": response.status_code == expected,
                    "response_contains_expected_text": contains in response_text,
                    "message_id_present": result["message_id"] is not None,
                }
                result["success"] = all(result["assertions"].values())
                if not result["success"]:
                    result["error"] = "Functional response or MPL correlation contract failed"
                # Persist only booleans/counts; source payload and response can contain private data.
                result["response_bytes"] = len(data)
                return result
        except (httpx.HTTPError, ValueError, TypeError, OverflowError, KeyError) as exc:
            result.update(
                outcome="unknown" if sent else "not_sent",
                error=f"Runtime request failed ({type(exc).__name__}); test was not retried",
            )
            return result
