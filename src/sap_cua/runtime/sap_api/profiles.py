"""Session-only DEV connection configuration and leases for immutable live runs.

Browser credentials never enter environment variables, files, logs, or API responses.
Environment configuration remains available for unattended installations.
"""

from __future__ import annotations

import os
import re
import uuid
from contextlib import contextmanager
from threading import Lock
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from sap_cua.runtime.sap_api import SAPAPIClient, secure_url
from sap_cua.runtime.sap_api.connection import ProbeBusy, probe_connection


def runtime_path(value: str, prefix: str = "/") -> str:
    # Reject encoded separators/dot segments rather than depending on proxy normalization.
    if (
        not re.fullmatch(r"/[A-Za-z0-9_./~-]*", value)
        or "//" in value
        or any(part in (".", "..") for part in value.split("/"))
        or not value.startswith(prefix)
        or len(value) > 500
    ):
        raise ValueError("Use an absolute runtime path within the configured test prefix")
    return value


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    api_base: str = Field(max_length=2000)
    token_url: str = Field(max_length=2000)
    client_id: SecretStr = Field(default=SecretStr(""), max_length=2000, repr=False)
    client_secret: SecretStr = Field(default=SecretStr(""), max_length=8192, repr=False)
    runtime_base: str = Field(default="", max_length=2000)
    runtime_token_url: str = Field(default="", max_length=2000)
    runtime_client_id: SecretStr = Field(default=SecretStr(""), max_length=2000, repr=False)
    runtime_client_secret: SecretStr = Field(default=SecretStr(""), max_length=8192, repr=False)
    allowed_test_prefix: str = "/http/"
    environment: Literal["dev"] = "dev"
    allow_dev_writes: bool = False

    @field_validator("api_base", "token_url", "runtime_base", "runtime_token_url")
    @classmethod
    def validate_url(cls, value, info):
        if not value and info.field_name.startswith("runtime"):
            return value
        value = secure_url(value)
        if info.field_name == "runtime_base" and urlsplit(value).path not in ("", "/"):
            raise ValueError("Runtime base must be an HTTPS origin without a path")
        return value

    @field_validator("allowed_test_prefix")
    @classmethod
    def validate_prefix(cls, value):
        runtime_path(value)
        if value == "/" or not value.endswith("/"):
            raise ValueError("Use a bounded test prefix ending in /, for example /http/")
        return value


class Profile(ProfileInput):
    def api_client(self, *, allow_mutations=False):
        return SAPAPIClient(
            api_base=self.api_base,
            token_url=self.token_url,
            client_id=self.client_id.get_secret_value(),
            client_secret=self.client_secret.get_secret_value(),
            allow_mutations=allow_mutations and self.allow_dev_writes,
            timeout_seconds=10,
        )

    def test_client(self):
        from sap_cua.runtime.sap_api.testing import RuntimeTestClient

        return RuntimeTestClient(self)

    def public(self):
        result = self.model_dump(
            exclude={"client_id", "client_secret", "runtime_client_id", "runtime_client_secret"}
        )
        for name in ("client_id", "client_secret", "runtime_client_id", "runtime_client_secret"):
            result[name + "_present"] = bool(getattr(self, name).get_secret_value())
        return result


class ConnectionProfiles:
    def __init__(self, environment=None):
        self._lock = Lock()
        self._busy = False
        self._revision = uuid.uuid4().hex
        self._profile = None
        self._invalid = []
        self.last_probe = None
        env = os.environ if environment is None else environment
        fields = {
            "api_base": "SAP_API_BASE_URL",
            "token_url": "SAP_TOKEN_URL",
            "client_id": "SAP_CLIENT_ID",
            "client_secret": "SAP_CLIENT_SECRET",
            "runtime_base": "SAP_RUNTIME_BASE_URL",
            "runtime_token_url": "SAP_RUNTIME_TOKEN_URL",
            "runtime_client_id": "SAP_RUNTIME_CLIENT_ID",
            "runtime_client_secret": "SAP_RUNTIME_CLIENT_SECRET",
        }
        if env.get("SAP_API_BASE_URL") or env.get("SAP_TOKEN_URL"):
            try:
                self._profile = Profile(
                    **{key: env.get(var, "") for key, var in fields.items()},
                    allowed_test_prefix=env.get("SAP_RUNTIME_TEST_PREFIX", "/http/"),
                    environment=env.get("SAP_CUA_ENVIRONMENT", "dev"),
                    allow_dev_writes=env.get("SAP_ALLOW_DEV_WRITES", "").lower() == "true",
                )
            except ValueError:
                # Never echo validation errors: Pydantic's normal errors may contain secrets.
                self._invalid = ["SAP connection environment"]

    def _status(self):
        profile = self._profile
        missing = []
        for attr, key in (
            ("api_base", "SAP_API_BASE_URL"),
            ("token_url", "SAP_TOKEN_URL"),
            ("client_id", "SAP_CLIENT_ID"),
            ("client_secret", "SAP_CLIENT_SECRET"),
        ):
            value = getattr(profile, attr, "")
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if not value:
                missing.append(key)
        configured = not missing and not self._invalid
        blockers = []
        if not configured:
            blockers.append("Configure the DEV management API connection")
        if not profile or not all(
            (
                profile.runtime_base,
                profile.runtime_token_url,
                profile.runtime_client_id.get_secret_value(),
                profile.runtime_client_secret.get_secret_value(),
            )
        ):
            blockers.append(
                "Configure separate runtime OAuth credentials and the HTTPS runtime origin"
            )
        if not profile or not profile.allow_dev_writes:
            blockers.append("Enable DEV deployment permission in the connection form")
        return {
            "configured": configured,
            "execution_enabled": not blockers,
            "live_execution_enabled": not blockers,
            "connection_revision": self._revision,
            "blockers": blockers,
            "profile": profile.public() if profile else {},
            "tenant_host": urlsplit(profile.api_base).hostname if profile else None,
            "missing": missing,
            "invalid": self._invalid,
            "mode": "dev",
            "credential_storage": "server_session",
            "busy": self._busy,
            "last_probe": self.last_probe,
        }

    def status(self):
        with self._lock:
            return self._status()

    def configure(self, payload: ProfileInput):
        with self._lock:
            if self._busy:
                raise ProbeBusy("A SAP operation is active; wait before changing its connection")
            old = self._profile
            values = payload.model_dump()
            for stem, endpoints in (
                ("", ("api_base", "token_url")),
                ("runtime_", ("runtime_base", "runtime_token_url")),
            ):
                id_key, secret_key = stem + "client_id", stem + "client_secret"
                old_id = getattr(old, id_key).get_secret_value() if old else ""
                same_endpoints = old and all(getattr(old, key) == values[key] for key in endpoints)
                new_id = values[id_key].get_secret_value()
                if same_endpoints and not new_id:
                    values[id_key] = getattr(old, id_key)
                    new_id = old_id
                if (
                    same_endpoints
                    and new_id == old_id
                    and not values[secret_key].get_secret_value()
                ):
                    values[secret_key] = getattr(old, secret_key)
            profile = Profile(**values)
            if (
                not profile.client_id.get_secret_value()
                or not profile.client_secret.get_secret_value()
            ):
                raise ValueError("Enter management credentials for this API and OAuth endpoint")
            self._profile = profile
            self._invalid = []
            self._revision = uuid.uuid4().hex
            self.last_probe = None
            return self._status()

    def clear(self):
        with self._lock:
            if self._busy:
                raise ProbeBusy("A SAP operation is active; wait before forgetting its connection")
            self._profile = None
            self._invalid = []
            self._revision = uuid.uuid4().hex
            self.last_probe = None
            return self._status()

    @contextmanager
    def lease(self, expected_revision):
        with self._lock:
            if expected_revision != self._revision:
                raise ValueError("Connection changed; review a new plan before deployment")
            if self._busy:
                raise ProbeBusy("Another SAP operation is active")
            if not self._status()["execution_enabled"]:
                raise PermissionError("Complete and enable the DEV connection before deployment")
            self._busy = True
            profile = self._profile.model_copy(deep=True)
        try:
            yield profile
        finally:
            with self._lock:
                self._busy = False

    def probe(self):
        with self._lock:
            if self._busy:
                raise ProbeBusy("Another SAP operation is active")
            status = self._status()
            if not status["configured"]:
                return {**status, "success": False, "checks": []}
            self._busy = True
            profile = self._profile.model_copy(deep=True)
        result = None
        try:
            with profile.api_client() as client:
                result = probe_connection(client)
        finally:
            with self._lock:
                self._busy = False
                if result is not None:
                    self.last_probe = result
                    response = {**self._status(), **result}
        return response
