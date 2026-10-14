import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from sap_cua.runtime.sap_api.connection import ProbeBusy
from sap_cua.runtime.sap_api.profiles import ConnectionProfiles, Profile, ProfileInput, runtime_path
from sap_cua.runtime.sap_api.testing import RuntimeTestClient


def config():
    return {
        "api_base": "https://management.example/api/v1",
        "token_url": "https://auth.example/oauth/token",
        "client_id": "management-id",
        "client_secret": "management-sensitive-value",
        "runtime_base": "https://runtime.example",
        "runtime_token_url": "https://runtime-auth.example/oauth/token",
        "runtime_client_id": "runtime-id",
        "runtime_client_secret": "runtime-sensitive-value",
        "allowed_test_prefix": "/http/",
        "environment": "dev",
        "allow_dev_writes": True,
    }


def test_profiles_never_return_credentials_or_write_them_to_environment(monkeypatch):
    monkeypatch.delenv("SAP_CLIENT_SECRET", raising=False)
    profiles = ConnectionProfiles({})
    public = profiles.configure(ProfileInput(**config()))
    encoded = json.dumps(public)
    for name in ("client_id", "client_secret", "runtime_client_id", "runtime_client_secret"):
        assert config()[name] not in encoded
    assert public["execution_enabled"] and public["profile"]["client_secret_present"]
    import os

    assert not os.getenv("SAP_CLIENT_SECRET")
    with profiles.lease(public["connection_revision"]) as snapshot:
        assert snapshot.client_secret.get_secret_value() == config()["client_secret"]
    assert not profiles.clear()["configured"]


def test_revision_change_and_busy_lease_prevent_retargeting():
    profiles = ConnectionProfiles({})
    first = profiles.configure(ProfileInput(**config()))
    second = profiles.configure(ProfileInput(**config()))
    with pytest.raises(ValueError), profiles.lease(first["connection_revision"]):
        pytest.fail("Old connection revision must not execute")
    with profiles.lease(second["connection_revision"]):
        assert profiles.status()["busy"]
        for change in (
            profiles.clear,
            lambda: profiles.configure(ProfileInput(**config())),
            profiles.probe,
        ):
            with pytest.raises(ProbeBusy):
                change()
    assert not profiles.status()["busy"]


def test_blank_secret_reuse_only_for_same_endpoint_and_principal():
    profiles = ConnectionProfiles({})
    profiles.configure(ProfileInput(**config()))
    new = {**config(), "client_id": "", "client_secret": ""}
    assert profiles.configure(ProfileInput(**new))["configured"]
    with pytest.raises(ValueError):
        profiles.configure(
            ProfileInput(**{**new, "token_url": "https://other.example/oauth/token"})
        )
    with pytest.raises(ValueError):
        profiles.configure(ProfileInput(**{**new, "client_id": "other-id"}))
    assert profiles.status()["configured"]


def test_incomplete_runtime_and_permission_never_enable_writes():
    profiles = ConnectionProfiles({})
    state = profiles.configure(ProfileInput(**{**config(), "runtime_client_secret": ""}))
    assert state["configured"] and not state["execution_enabled"]
    with pytest.raises(PermissionError), profiles.lease(state["connection_revision"]):
        pass
    state = profiles.configure(ProfileInput(**{**config(), "allow_dev_writes": False}))
    assert not state["execution_enabled"]


@pytest.mark.parametrize(
    "path",
    [
        "//other.example/http/a",
        "/http/../secrets",
        "/http/%2e%2e/a",
        "/http/a?url=evil",
        "/other/a",
        "/http/a#x",
        "/http/a\\b",
    ],
)
def test_runtime_path_cannot_change_origin_or_escape_prefix(path):
    with pytest.raises(ValueError):
        runtime_path(path, "/http/")


def contract():
    return {
        "path": "/http/smoke",
        "method": "POST",
        "body": '{"test":true}',
        "expected_status": 200,
        "response_contains": "completed",
    }


def test_real_runtime_transport_checks_response_and_hides_bodies():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "runtime-auth.example":
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "runtime-bearer"})
        assert request.url == "https://runtime.example/http/smoke"
        assert request.headers["authorization"] == "Bearer runtime-bearer"
        assert request.content == contract()["body"].encode()
        return httpx.Response(
            200,
            text="completed private_customer_record",
            headers={"SAP_MessageProcessingLogID": "MESSAGE123"},
        )

    with RuntimeTestClient(Profile(**config()), transport=httpx.MockTransport(handler)) as client:
        result = client.send(contract())
    assert result["success"] and result["message_id"] == "MESSAGE123" and result["started_at"]
    assert len(requests) == 2 and "private_customer_record" not in json.dumps(result)
    assert "runtime-bearer" not in json.dumps(result)


@pytest.mark.parametrize(
    "status,body,headers",
    [
        (200, "wrong response", {"SAP_MessageProcessingLogID": "MESSAGE123"}),
        (500, "completed", {"SAP_MessageProcessingLogID": "MESSAGE123"}),
        (200, "completed", {}),
        (302, "completed", {"location": "https://elsewhere.example"}),
    ],
)
def test_false_success_and_redirects_rejected(status, body, headers):
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == "runtime-auth.example":
            return httpx.Response(200, json={"access_token": "test-token"})
        return httpx.Response(status, text=body, headers=headers)

    with RuntimeTestClient(Profile(**config()), transport=httpx.MockTransport(handler)) as client:
        result = client.send(contract())
    assert not result["success"] and seen == ["runtime-auth.example", "runtime.example"]


def test_runtime_timeout_is_uncertain_and_never_replayed():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        if request.url.host == "runtime-auth.example":
            return httpx.Response(200, json={"access_token": "test-token"})
        raise httpx.ReadTimeout("PRIVATE ERROR")

    with RuntimeTestClient(Profile(**config()), transport=httpx.MockTransport(handler)) as client:
        result = client.send(contract())
    assert result["outcome"] == "unknown" and not result["success"]
    assert len(calls) == 2 and "PRIVATE ERROR" not in json.dumps(result)


def test_response_budget_is_bounded():
    def handler(request):
        if request.url.host == "runtime-auth.example":
            return httpx.Response(200, json={"access_token": "test-token"})
        return httpx.Response(200, content=b"x" * 100)

    with RuntimeTestClient(
        Profile(**config()), transport=httpx.MockTransport(handler), max_bytes=10
    ) as client:
        result = client.send(contract())
    assert not result["success"] and "budget" in result["error"]


def test_slow_small_chunks_cannot_hold_runtime_lease_indefinitely(monkeypatch):
    from sap_cua.runtime.sap_api import testing

    clock = [0.0]
    received = []
    monkeypatch.setattr(testing.time, "monotonic", lambda: clock[0])

    class Trickle(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(100):
                clock[0] += 16
                received.append(True)
                yield b"x"

    def handler(request):
        if request.url.host == "runtime-auth.example":
            return httpx.Response(200, json={"access_token": "test-token"})
        return httpx.Response(200, stream=Trickle())

    with RuntimeTestClient(Profile(**config()), transport=httpx.MockTransport(handler)) as client:
        result = client.send(contract())
    assert not result["success"] and len(received) == 2
    assert "budget" in result["error"]


def test_oversized_oauth_response_does_not_send_test():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(200, content=b" " * 65537)

    with RuntimeTestClient(Profile(**config()), transport=httpx.MockTransport(handler)) as client:
        result = client.send(contract())
    assert not result["success"] and result["outcome"] == "not_sent"
    assert calls == ["runtime-auth.example"]


def test_probe_finished_response_releases_busy_flag(monkeypatch):
    from sap_cua.runtime.sap_api import profiles as module

    profiles = ConnectionProfiles({})
    profiles.configure(ProfileInput(**config()))
    monkeypatch.setattr(module, "probe_connection", lambda client: {"success": True, "checks": []})
    response = profiles.probe()
    assert response["success"] and not response["busy"]
    assert not profiles.status()["busy"]


def test_profile_api_errors_and_history_never_echo_secret(tmp_path, monkeypatch):
    from sap_cua.api.main import create_app

    monkeypatch.delenv("SAP_CUA_DATABASE_URL", raising=False)
    with TestClient(create_app(tmp_path, test_mode=True)) as client:
        assert client.post("/api/sap/profile", json=config()).status_code == 401
        client.get("/")
        headers = {"x-sap-cua": "workbench"}
        response = client.post("/api/sap/profile", json=config(), headers=headers)
        assert response.status_code == 200 and "sensitive-value" not in response.text
        invalid = {**config(), "token_url": "http://invalid", "extra": "TOPSECRET"}
        response = client.post("/api/sap/profile", json=invalid, headers=headers)
        assert response.status_code == 422 and "TOPSECRET" not in response.text
        assert "sensitive-value" not in response.text
        assert client.get("/api/live/runs").json() == []


def test_rag_failure_does_not_block_setup_ui(tmp_path, monkeypatch):
    from sap_cua.api.main import create_app
    from sap_cua.engineering.service import RAGService

    failed = threading.Event()

    def fail(*args):
        failed.set()
        raise RuntimeError("SECRET database connection")

    monkeypatch.setenv("SAP_CUA_DATABASE_URL", "fixture")
    monkeypatch.setattr(RAGService, "from_environment", fail)
    with TestClient(create_app(tmp_path, test_mode=True)) as client:
        assert client.get("/").status_code == 200
        assert failed.wait(2)
        assert client.get("/api/sap/profile").status_code == 200
        assert client.get("/api/rag/status").status_code == 503
        assert "SECRET" not in client.get("/api/rag/status").text
