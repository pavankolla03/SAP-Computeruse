import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from sap_cua.api.main import create_app
from sap_cua.runtime.sap_api import SAPAPIClient
from sap_cua.runtime.sap_api.connection import (
    KEYS,
    ConnectionService,
    ProbeBusy,
    connection_status,
    probe_connection,
)
from sap_cua.runtime.sap_api.verification import (
    verify_deployment,
    verify_iflow,
    verify_message,
    verify_package,
)


def client(handler):
    return SAPAPIClient(
        api_base="https://tenant.example/api/v1",
        token_url="https://auth.example/oauth/token",
        client_id="fixture-client",
        client_secret="fixture-secret",
        transport=httpx.MockTransport(handler),
    )


def with_auth(handler):
    def wrapped(request):
        if request.url.host == "auth.example":
            return httpx.Response(200, json={"access_token": "fixture-token"})
        return handler(request)

    return wrapped


def test_missing_and_invalid_configuration_never_contains_values():
    assert connection_status({})["missing"] == list(KEYS)
    env = dict(
        zip(
            KEYS,
            [
                "http://private.invalid",
                "https://auth.example/token?secret=oops",
                "private-id",
                "private-secret",
            ],
            strict=True,
        )
    )
    result = connection_status(env)
    assert result["invalid"] == list(KEYS[:2]) and not result["configured"]
    assert "private-secret" not in json.dumps(result) and "oops" not in json.dumps(result)


def test_probe_only_reads_and_hides_all_sap_payloads():
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.params["$top"] == "1"
        return httpx.Response(
            200, json={"d": {"results": [{"Name": "PRIVATE_CUSTOMER", "secret": "NEVER_RETURN"}]}}
        )

    with client(with_auth(handle)) as api:
        result = probe_connection(api)
    assert result["success"] and len(requests) == 3
    assert not result["write_permissions_verified"] and not result["identity_verified"]
    assert "PRIVATE_CUSTOMER" not in json.dumps(result) and "NEVER_RETURN" not in json.dumps(result)


def test_probe_stops_after_auth_failure():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(401, text="private error")

    with client(handle) as api:
        result = probe_connection(api)
    assert not result["success"] and len(requests) == 1 and len(result["checks"]) == 1
    assert "private error" not in json.dumps(result)


def test_html_login_page_is_not_valid_read_access():
    with client(with_auth(lambda _: httpx.Response(200, text="<html>Login</html>"))) as api:
        assert not probe_connection(api)["success"]


def test_capability_denial_does_not_hide_other_read_results():
    def handle(request):
        if "Runtime" in request.url.path:
            return httpx.Response(403)
        return httpx.Response(200, json={"d": {"results": []}})

    with client(with_auth(handle)) as api:
        result = probe_connection(api)
    assert not result["success"] and [c["success"] for c in result["checks"]] == [True, False, True]


def test_concurrent_probe_denied():
    service = ConnectionService()
    service._lock.acquire()
    try:
        with pytest.raises(ProbeBusy):
            service.probe()
    finally:
        service._lock.release()


def test_probe_route_requires_local_session_and_no_client_supplied_configuration(
    tmp_path, monkeypatch
):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SAP_CUA_DATABASE_URL", raising=False)
    with TestClient(create_app(tmp_path, test_mode=True)) as c:
        assert c.get("/api/sap/status").status_code == 401
        c.get("/")
        assert not c.get("/api/sap/status").json()["configured"]
        assert c.post("/api/sap/probe", json={}).status_code == 403
        headers = {"x-sap-cua": "workbench"}
        assert (
            c.post(
                "/api/sap/probe", headers=headers, json={"api_base": "https://evil.example"}
            ).status_code
            == 422
        )
        result = c.post("/api/sap/probe", headers=headers, json={})
        assert result.status_code == 200 and result.json()["checks"] == []


def test_package_http_failure_is_not_existence():
    from sap_cua.services.verifier import verify_package_exists

    with client(with_auth(lambda _: httpx.Response(404))) as api:
        assert not verify_package(api, "DEMO")["success"]
        assert not verify_package_exists(api, "DEMO")["success"]


def test_iflow_requires_matching_package_and_id():
    with client(
        with_auth(lambda _: httpx.Response(200, json={"d": {"Id": "FLOW", "PackageId": "OTHER"}}))
    ) as api:
        assert not verify_iflow(api, "DEMO", "FLOW")["success"]


class Clock:
    value = 0

    def time(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def deployment_api(build_states, runtime_states):
    build = iter(build_states)
    runtime = iter(runtime_states)

    def handle(request):
        assert request.method == "GET"
        if "BuildAndDeployStatus" in request.url.path:
            return httpx.Response(200, json={"d": {"Status": next(build)}})
        return httpx.Response(200, json={"d": {"Id": "FLOW", "Status": next(runtime)}})

    return client(with_auth(handle))


def test_deployment_requires_build_and_runtime_and_only_reads():
    clock = Clock()
    with deployment_api(["DEPLOYING", "SUCCESS", "SUCCESS"], ["STARTING", "STARTED"]) as api:
        result = verify_deployment(
            api, "FLOW", "TASK", timeout=20, monotonic=clock.time, sleep=clock.sleep
        )
    assert result["success"] and len(result["checks"]) == 5
    assert not result["business_test_verified"]


@pytest.mark.parametrize("status", ["FAIL", "FAIL_ON_LICENSE_ERROR", "UNKNOWN"])
def test_failed_or_unknown_build_never_passes(status):
    clock = Clock()
    with deployment_api([status], []) as api:
        assert not verify_deployment(api, "FLOW", "TASK", monotonic=clock.time, sleep=clock.sleep)[
            "success"
        ]


def test_polling_has_bounded_budget():
    clock = Clock()
    with deployment_api(["DEPLOYING"] * 5, []) as api:
        result = verify_deployment(
            api, "FLOW", "TASK", timeout=3, poll_interval=2, monotonic=clock.time, sleep=clock.sleep
        )
    assert not result["success"] and clock.value == 3 and len(result["checks"]) == 2


def mpl_api(row):
    def handle(request):
        assert (
            request.method == "GET" and request.url.params["$filter"] == "MessageGuid eq 'MESSAGE'"
        )
        return httpx.Response(200, json={"d": {"results": [row]}})

    return client(with_auth(handle))


def message_row():
    return {
        "MessageGuid": "MESSAGE",
        "IntegrationFlowName": "FLOW",
        "Status": "COMPLETED",
        "LogStart": "2026-10-10T01:00:01Z",
        "LogEnd": "2026-10-10T01:00:02Z",
    }


def test_fresh_correlated_mpl_proves_processing_only():
    with mpl_api(message_row()) as api:
        result = verify_message(api, "FLOW", "MESSAGE", datetime(2026, 10, 10, 1, tzinfo=UTC))
    assert result["success"] and not result["business_payload_verified"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("MessageGuid", "OTHER"),
        ("IntegrationFlowName", "OTHER"),
        ("Status", "FAILED"),
        ("LogStart", "2026-10-09T01:00:00Z"),
        ("LogStart", "2026-10-10T01:00:01"),
        ("LogEnd", "bad date"),
    ],
)
def test_unrelated_stale_or_incomplete_mpl_fails(field, value):
    row = message_row()
    row[field] = value
    with mpl_api(row) as api:
        assert not verify_message(api, "FLOW", "MESSAGE", datetime(2026, 10, 10, 1, tzinfo=UTC))[
            "success"
        ]


@pytest.mark.parametrize(
    "payload", [None, [], {}, {"access_token": 1}, {"access_token": "token", "expires_in": "nan"}]
)
def test_malformed_oauth_response_fails_without_secret_details(payload):
    with client(lambda _: httpx.Response(200, json=payload)) as api:
        result = api.get_package("DEMO")
    assert not result["success"] and result["outcome"] == "not_sent"
    assert "fixture-secret" not in json.dumps(result)


def test_query_limit_cannot_be_overridden_by_filter():
    with (
        client(lambda _: pytest.fail("Network must not be called")) as api,
        pytest.raises(ValueError),
    ):
        api.query_mpl({"$top": 100000}, limit=1)


@pytest.mark.parametrize("payload", ["TASK", {"d": "TASK"}])
def test_scalar_deployment_task_response_normalized(payload):
    with client(with_auth(lambda _: httpx.Response(200, json=payload))) as api:
        assert api._request("GET", "Fixture")["data"] == {"task_id": "TASK"}


def test_complex_artifact_identity_and_conflicts():
    row = message_row()
    row.pop("IntegrationFlowName")
    row["IntegrationArtifact"] = {"Id": "FLOW"}
    with mpl_api(row) as api:
        assert verify_message(api, "FLOW", "MESSAGE", datetime(2026, 10, 10, 1, tzinfo=UTC))[
            "success"
        ]
    row["IntegrationFlowName"] = "OTHER"
    with mpl_api(row) as api:
        assert not verify_message(api, "FLOW", "MESSAGE", datetime(2026, 10, 10, 1, tzinfo=UTC))[
            "success"
        ]
