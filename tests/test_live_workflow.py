"""Contracts for irreversible phases, correlation, scope, and replay prevention."""

import io
import json
import threading
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from sap_cua.engineering.live import LivePlanRequest, LiveService
from sap_cua.rag.schemas import Scope
from sap_cua.runtime.sap_api import SAPAPIClient
from sap_cua.services.workbench import RunStore


def exported(content="<flow><address>{{ADDRESS}}</address></flow>", filename="src/Flow.iflw"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(filename, content)
    return out.getvalue()


class SAPTenant:
    """Exercise the real HTTP client and verifiers against observed server state."""

    allowed_test_prefix = "/http/agent/"

    def __init__(self):
        self.packages = set()
        self.flows = {}
        self.requests = []
        self.fail_at = None
        self.write_timeout = None
        self.test_count = 0
        self.test_result = None
        self.message_wrong = False
        self.message_delay = 0
        self.mpl_reads = 0
        self.pause = None
        self.release = None
        self.started = None

    def handler(self, request):
        self.requests.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "fixture-access-token"})
        if request.headers.get("X-CSRF-Token") == "Fetch":
            return httpx.Response(200, headers={"X-CSRF-Token": "fixture-csrf"})
        if request.method == "POST" and self.write_timeout and self.write_timeout in path:
            raise httpx.ReadTimeout("https://tenant.example?client_secret=must-not-escape")
        if self.fail_at and self.fail_at in path:
            return httpx.Response(500, text="private response must-not-escape")
        if path.endswith("/IntegrationPackages"):
            if request.method == "GET":
                return httpx.Response(200, json={"d": {"results": []}})
            body = json.loads(request.content)
            self.packages.add(body["Id"])
            return httpx.Response(201)
        if path.endswith("/IntegrationRuntimeArtifacts"):
            return httpx.Response(200, json={"d": {"results": []}})
        if path.endswith("/MessageProcessingLogs"):
            if request.url.params.get("$top") == "1":
                return httpx.Response(200, json={"d": {"results": []}})
            self.mpl_reads += 1
            if self.mpl_reads <= self.message_delay:
                return httpx.Response(200, json={"d": {"results": []}})
            start = self.started or datetime.now(UTC)
            row = {
                "MessageGuid": "MESSAGE",
                "IntegrationFlowName": "WRONG" if self.message_wrong else "FLOW",
                "Status": "COMPLETED",
                "LogStart": (start + timedelta(seconds=1)).isoformat(),
                "LogEnd": (start + timedelta(seconds=2)).isoformat(),
            }
            return httpx.Response(200, json={"d": {"results": [row]}})
        if "/IntegrationPackages(" in path:
            name = path.split("'")[1]
            return (
                httpx.Response(200, json={"d": {"Id": name}})
                if name in self.packages
                else httpx.Response(404)
            )
        if path.endswith("/IntegrationDesigntimeArtifacts"):
            body = json.loads(request.content)
            self.flows[body["Id"]] = body["PackageId"]
            if self.pause:
                self.pause.set()
                self.release.wait(3)
            return httpx.Response(201)
        if "/IntegrationDesigntimeArtifacts(" in path:
            name = path.split("'")[1]
            return (
                httpx.Response(200, json={"d": {"Id": name, "PackageId": self.flows[name]}})
                if name in self.flows
                else httpx.Response(404)
            )
        if path.endswith("/DeployIntegrationDesigntimeArtifact"):
            return httpx.Response(202, text="TASK")
        if "/BuildAndDeployStatus(" in path:
            return httpx.Response(200, json={"d": {"Status": "SUCCESS"}})
        if "/IntegrationRuntimeArtifacts(" in path:
            return httpx.Response(200, json={"d": {"Id": "FLOW", "Status": "STARTED"}})
        raise AssertionError(str(request.url))

    def api_client(self, *, allow_mutations):
        return SAPAPIClient(
            api_base="https://tenant.example/api/v1",
            token_url="https://auth.example/token",
            client_id="fixture-id",
            client_secret="fixture-secret",
            allow_mutations=allow_mutations,
            transport=httpx.MockTransport(self.handler),
        )

    def test_client(self):
        return self

    def send(self, test):
        self.test_count += 1
        self.started = datetime.now(UTC)
        return self.test_result or {
            "success": True,
            "status_code": 200,
            "message_id": "MESSAGE",
            "started_at": self.started.isoformat(),
            "assertions": {"status": True, "body_contains": True},
            "outcome": "definite",
        }


class Connections:
    revision = "revision-1"
    configured = True
    enabled = True
    busy = False

    def __init__(self, profile):
        self.profile = profile

    def status(self):
        return {
            "configured": self.configured,
            "execution_enabled": self.enabled,
            "connection_revision": self.revision,
            "blockers": [],
            "tenant_host": "tenant.example",
        }

    @contextmanager
    def lease(self, expected_revision):
        if self.busy or self.revision != expected_revision or not self.enabled:
            raise ValueError("Connection no longer available")
        self.busy = True
        try:
            yield self.profile
        finally:
            self.busy = False


@pytest.fixture
def live(tmp_path):
    tenant = SAPTenant()
    service = LiveService(
        tmp_path,
        RunStore(tmp_path),
        Scope(customer="C", tenant="DEV", role="engineer"),
        Connections(tenant),
    )
    service.poll_interval = 0.001
    service.max_message_polls = 3
    service.message_timeout = 1
    return service, tenant


def plan_for(service, **changes):
    template = service.import_template(exported(), "Fixture template", approved=True)
    fields = {
        "template_id": template["id"],
        "parameters": {"ADDRESS": "https://receiver.example"},
        "package_id": "PKG",
        "iflow_id": "FLOW",
        "name": "Flow",
        "test": {
            "path": "/http/agent/test",
            "body": '{"hello":"world"}',
            "response_contains": "ok",
        },
    }
    fields.update(changes)
    return service.create_plan(LivePlanRequest(**fields))


def finished(service, id):
    service._thread.join(4)
    assert not service._thread.is_alive()
    return service.get_run(id)


def writes(tenant):
    return [p for method, p in tenant.requests if method == "POST" and not p.endswith("/token")]


def test_real_http_chain_requires_observed_upload_runtime_and_fresh_mpl(live):
    service, tenant = live
    plan = plan_for(service)
    assert service.plan_artifact(plan["id"]).startswith(b"PK")
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["success"] and result["status"] == "succeeded"
    assert len(writes(tenant)) == 3 and tenant.test_count == 1 and tenant.mpl_reads == 1
    assert len(result["steps"]) == 6 and all(s["status"] == "succeeded" for s in result["steps"])
    assert result["cleanup"]["created_package"] and result["cleanup"]["uploaded_iflow"]
    assert "fixture-secret" not in json.dumps(result)
    with pytest.raises(ValueError):
        service.start_run(plan["id"])
    assert len(writes(tenant)) == 3


def test_existing_package_is_reused_only_after_identity_check(live):
    service, tenant = live
    tenant.packages.add("PKG")
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["success"] and not result["cleanup"]["created_package"]
    assert len(writes(tenant)) == 2


def test_existing_iflow_never_overwritten(live):
    service, tenant = live
    tenant.flows["FLOW"] = "PKG"
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["status"] == "failed" and "overwrite denied" in result["error"]
    assert not writes(tenant) and tenant.test_count == 0


@pytest.mark.parametrize(
    "failed_resource", ["IntegrationDesigntimeArtifacts", "DeployIntegrationDesigntimeArtifact"]
)
def test_uncertain_write_is_not_retried_or_followed_by_test(live, failed_resource):
    service, tenant = live
    tenant.write_timeout = failed_resource
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["status"] == "failed" and "outcome unknown" in result["error"]
    assert sum(failed_resource in p for p in writes(tenant)) == 1 and tenant.test_count == 0
    assert "must-not-escape" not in json.dumps(result)


@pytest.mark.parametrize(
    "result",
    [
        {"success": False, "outcome": "unknown"},
        {"success": False, "status_code": 200, "assertions": {"body_contains": False}},
        {
            "success": True,
            "status_code": 200,
            "message_id": None,
            "started_at": "2026-10-13T01:00:00Z",
        },
    ],
)
def test_runtime_failure_or_missing_correlation_never_claims_success(live, result):
    service, tenant = live
    tenant.test_result = result
    plan = plan_for(service)
    service.start_run(plan["id"])
    record = finished(service, plan["id"])
    assert record["status"] == "failed" and tenant.test_count == 1 and tenant.mpl_reads == 0


def test_unrelated_message_never_passes_and_polling_is_bounded(live):
    service, tenant = live
    tenant.message_wrong = True
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert not result["success"] and tenant.mpl_reads == 3 and tenant.test_count == 1


def test_eventual_message_is_observed_without_resending_test(live):
    service, tenant = live
    tenant.message_delay = 1
    plan = plan_for(service)
    service.start_run(plan["id"])
    assert finished(service, plan["id"])["success"]
    assert tenant.mpl_reads == 2 and tenant.test_count == 1


def test_connection_revision_freezes_plan(live):
    service, tenant = live
    plan = plan_for(service)
    service.connections.revision = "revision-2"
    with pytest.raises(ValueError, match="Connection changed"):
        service.start_run(plan["id"])
    assert not tenant.requests


def test_unconfigured_plan_is_reviewable_but_never_executable(live):
    service, tenant = live
    service.connections.configured = False
    plan = plan_for(service)
    assert plan["blockers"]
    with pytest.raises(ValueError):
        service.start_run(plan["id"])
    assert not tenant.requests


def test_cancellation_waits_for_inflight_write_and_does_not_rollback(live):
    service, tenant = live
    tenant.pause, tenant.release = threading.Event(), threading.Event()
    plan = plan_for(service)
    service.start_run(plan["id"])
    assert tenant.pause.wait(2)
    assert service.cancel(plan["id"])["cancellation_requested"]
    assert service.get_run(plan["id"])["cancellation_requested"]
    another = plan_for(service, iflow_id="SECOND")
    with pytest.raises(ValueError, match="already active"):
        service.start_run(another["id"])
    tenant.release.set()
    result = finished(service, plan["id"])
    assert result["status"] == "cancelled" and result["cleanup"]["uploaded_iflow"]
    assert len(writes(tenant)) == 2 and not tenant.test_count
    assert all(method != "DELETE" for method, _ in tenant.requests)


def test_archive_and_run_are_customer_tenant_scoped(live, tmp_path):
    service, _ = live
    plan = plan_for(service)
    other = LiveService(
        tmp_path, service.run_store, Scope(customer="OTHER", tenant="DEV"), service.connections
    )
    assert not other.templates() and not other.runs()
    with pytest.raises(KeyError):
        other.get_run(plan["id"])
    with pytest.raises(KeyError):
        other.template_artifact(plan["template_id"])


def test_viewer_cannot_import_plan_or_execute(live, tmp_path):
    service, _ = live
    plan = plan_for(service)
    viewer = LiveService(
        tmp_path,
        service.run_store,
        service.scope.model_copy(update={"role": "viewer"}),
        service.connections,
    )
    with pytest.raises(PermissionError):
        viewer.import_template(exported(), "No", approved=True)
    with pytest.raises(PermissionError):
        viewer.start_run(plan["id"])


@pytest.mark.parametrize(
    "archive",
    [
        exported("<flow/>", "../Flow.iflw"),
        exported("<flow/>", "readme.txt"),
        exported("<flow>password=unapproved-private-value</flow>"),
        exported('<!DOCTYPE f [<!ENTITY x SYSTEM "file:///etc/passwd">]><f>&x;</f>'),
        b"not a zip",
    ],
)
def test_invalid_or_secret_bearing_templates_fail_before_storage(live, archive):
    service, _ = live
    with pytest.raises(ValueError):
        service.import_template(archive, "Bad", approved=True)
    assert not service.templates()


def test_artifact_integrity_is_checked_before_any_request(live):
    service, tenant = live
    plan = plan_for(service)
    (service.directory / ("plan-" + plan["id"] + ".zip")).write_bytes(exported("<flow/>"))
    with pytest.raises(ValueError, match="integrity"):
        service.start_run(plan["id"])
    assert not tenant.requests


def test_secret_body_is_rejected_but_valid_json_whitespace_is_accepted(live):
    service, _ = live
    with pytest.raises(ValueError, match="secrets cannot be stored"):
        plan_for(
            service,
            test={
                "path": "/http/agent/test",
                "body": '{"password":"never-store"}',
                "response_contains": "ok",
            },
        )
    assert plan_for(service)["id"]


def test_runtime_contract_is_validated_before_any_write(live):
    service, tenant = live
    plan = plan_for(
        service, test={"path": "/outside/test", "body": "{}", "response_contains": "ok"}
    )
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["status"] == "failed" and not writes(tenant) and not tenant.requests


@pytest.mark.parametrize(
    "test",
    [
        {"path": "/http/agent/test", "body": "é" * 32769, "response_contains": "ok"},
        {"path": "/http/agent/test", "body": "{}", "response_contains": "x" * 4001},
        {
            "path": "/http/agent/test",
            "body": "{}",
            "response_contains": "ok",
            "expected_status": 500,
        },
    ],
)
def test_invalid_test_contract_cannot_be_planned(live, test):
    service, tenant = live
    with pytest.raises(ValueError):
        plan_for(service, test=test)
    assert not tenant.requests


def test_full_management_and_runtime_http_chain_preserves_exact_request_body(live):
    from pydantic import SecretStr

    from sap_cua.runtime.sap_api.testing import RuntimeTestClient

    service, tenant = live
    tenant.runtime_base = "https://runtime.example"
    tenant.runtime_token_url = "https://runtime-auth.example/token"
    tenant.runtime_client_id = SecretStr("fixture-runtime-id")
    tenant.runtime_client_secret = SecretStr("fixture-runtime-secret")
    requests = []
    original_body = '{ "hello" : "world" }'

    def runtime_handler(request):
        requests.append(request)
        if request.url.host == "runtime-auth.example":
            assert request.method == "POST"
            return httpx.Response(200, json={"access_token": "fixture-runtime-token"})
        assert str(request.url) == "https://runtime.example/http/agent/test"
        assert request.content.decode() == original_body
        assert request.headers["Authorization"] == "Bearer fixture-runtime-token"
        tenant.started = datetime.now(UTC)
        return httpx.Response(200, headers={"SAP_MessageProcessingLogID": "MESSAGE"}, text="ok")

    tenant.test_client = lambda: RuntimeTestClient(
        tenant, transport=httpx.MockTransport(runtime_handler)
    )
    plan = plan_for(
        service, test={"path": "/http/agent/test", "body": original_body, "response_contains": "ok"}
    )
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["success"] and len(requests) == 2 and tenant.mpl_reads == 1
    assert len(writes(tenant)) == 3
    serialized = json.dumps(result)
    assert "fixture-runtime-secret" not in serialized and "fixture-runtime-token" not in serialized
    assert result["steps"][4]["result"]["assertions"]["response_contains_expected_text"]


def test_successful_execution_indexes_only_sanitized_phase_memory(live):
    service, _ = live
    collected = []

    class Ingestor:
        def ingest(self, doc, scope):
            collected.append((doc, scope))

    service.ingestor = Ingestor()
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["knowledge_ingested"] and len(collected) == 1
    doc, scope = collected[0]
    data = json.loads(doc.content)
    assert data["backend"] == "sap_api" and len(data["phases"]) == 6
    assert doc.provenance_kind == "verified_execution" and doc.tenant_scope == scope.tenant
    assert "world" not in doc.content and "response_contains" not in doc.content


def test_indexing_failure_never_replays_or_fails_successful_sap_job(live):
    service, tenant = live

    class Ingestor:
        def ingest(self, doc, scope):
            raise RuntimeError("private-indexer-error")

    service.ingestor = Ingestor()
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["success"] and result["knowledge_error"] == "RuntimeError"
    assert len(writes(tenant)) == 3 and tenant.test_count == 1
    assert "private-indexer-error" not in json.dumps(result)


def test_failed_execution_never_indexes_verified_memory(live):
    service, tenant = live
    tenant.message_wrong = True

    class Ingestor:
        def ingest(self, doc, scope):
            pytest.fail("Failed execution must not enter verified memory")

    service.ingestor = Ingestor()
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert not result["success"] and not result["knowledge_ingested"]


def test_unknown_write_evidence_records_attempt_without_payloads(live):
    service, tenant = live
    tenant.write_timeout = "IntegrationDesigntimeArtifacts"
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["steps"][-1]["result"]["outcome"] == "unknown"
    assert result["steps"][-1]["result"]["success"] is False
    assert "data" not in result["steps"][-1]["result"]


def test_routes_enforce_session_scope_and_immutable_plan_contract(live, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from sap_cua.api.main import create_app

    service, _tenant = live
    monkeypatch.delenv("SAP_CUA_DATABASE_URL", raising=False)
    app = create_app(tmp_path / "app", test_mode=True)
    with TestClient(app) as client:
        app.state.live = service
        assert client.get("/api/live/templates").status_code == 401
        client.get("/")
        assert client.post("/api/live/plans/nonexistent/run").status_code == 403
        headers = {"x-sap-cua": "workbench"}
        imported = client.post(
            "/api/live/templates",
            headers=headers,
            data={"title": "Fixture", "approved": "true"},
            files={"file": ("flow.zip", exported(), "application/zip")},
        )
        assert imported.status_code == 201
        template = imported.json()
        assert client.get(template["artifact_url"]).content == service.template_artifact(
            template["id"]
        )
        request = {
            "template_id": template["id"],
            "parameters": {"ADDRESS": "https://receiver.example"},
            "package_id": "PKG",
            "iflow_id": "FLOW",
            "name": "Flow",
            "test": {"path": "/http/agent/test", "body": "{}", "response_contains": "ok"},
        }
        response = client.post("/api/live/plans", headers=headers, json=request)
        assert response.status_code == 201
        plan = response.json()
        assert client.get("/api/live/plans/" + plan["id"]).json() == plan
        assert client.get(plan["artifact_url"]).content.startswith(b"PK")
        assert (
            client.post("/api/live/plans/" + plan["id"] + "/run", headers=headers).status_code
            == 202
        )
        assert finished(service, plan["id"])["success"]
        assert (
            client.post("/api/live/plans/" + plan["id"] + "/run", headers=headers).status_code
            == 409
        )
        download = client.get("/api/live/runs/" + plan["id"] + "/export")
        assert download.status_code == 200 and download.json()["success"]
        assert download.headers["content-disposition"].startswith("attachment;")
        assert client.get("/api/live/runs/nonexistent").status_code == 404


def test_total_job_deadline_expires_after_slow_preflight_before_first_write(live):
    service, tenant = live
    clock = [100.0]
    service.monotonic = lambda: clock[0]
    original = tenant.handler

    def slow_preflight(request):
        response = original(request)
        if request.method == "GET":
            clock[0] += 65
        return response

    tenant.handler = slow_preflight
    plan = plan_for(service)
    assert plan["max_seconds"] == 300
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["status"] == "failed" and "duration budget" in result["error"]
    assert not writes(tenant) and tenant.test_count == 0
    assert not service.status()["active_run_id"]


def test_total_job_deadline_stops_runtime_poll_without_resending_test(live):
    service, tenant = live
    clock = [100.0]
    service.monotonic = lambda: clock[0]
    original = tenant.handler

    def slow_mpl(request):
        response = original(request)
        if (
            request.url.path.endswith("/MessageProcessingLogs")
            and request.url.params.get("$top") != "1"
        ):
            clock[0] += 301
        return response

    tenant.handler = slow_mpl
    plan = plan_for(service)
    service.start_run(plan["id"])
    result = finished(service, plan["id"])
    assert result["status"] == "failed" and "duration budget" in result["error"]
    assert tenant.test_count == 1 and tenant.mpl_reads == 1


def identity_archive(manifest):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("META-INF/MANIFEST.MF", manifest)
        z.writestr("src/Flow.iflw", "<flow/>")
    return output.getvalue()


def test_manifest_identity_is_exposed_and_conflicting_plan_is_denied(live):
    service, tenant = live
    archive = identity_archive(
        "Manifest-Version: 1.0\r\nBundle-SymbolicName: FL\r\n OW;singleton:=true\r\n\r\n"
    )
    template = service.import_template(archive, "Identity fixture", approved=True)
    assert template["artifact_id"] == "FLOW" and template["source_identity"] == "manifest_declared"
    assert service.template_artifact(template["id"]) == archive
    payload = {
        "template_id": template["id"],
        "package_id": "PKG",
        "iflow_id": "WRONG",
        "name": "Flow",
        "test": {"path": "/http/agent/test", "body": "{}", "response_contains": "ok"},
    }
    with pytest.raises(ValueError, match="manifest identity"):
        service.create_plan(LivePlanRequest(**payload))
    assert not tenant.requests and not service.runs()
    payload["iflow_id"] = "FLOW"
    plan = service.create_plan(LivePlanRequest(**payload))
    assert plan["source_artifact_id"] == "FLOW"


def test_missing_manifest_is_explicitly_undeclared_not_tenant_validated(live):
    service, _ = live
    template = service.import_template(exported(), "Source-only fixture", approved=True)
    assert template["artifact_id"] is None and template["source_identity"] == "not_declared"
    assert not template["tenant_validated"]
