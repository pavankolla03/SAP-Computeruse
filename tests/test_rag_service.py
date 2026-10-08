from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from sap_cua.api.main import create_app
from sap_cua.engineering.service import RAGService
from sap_cua.rag.embeddings import HashEmbedding, TokenOverlapReranker
from sap_cua.rag.schemas import Scope
from sap_cua.rag.sources import source_document
from sap_cua.rag.store import MemoryKnowledgeStore
from sap_cua.services.workbench import RunStore


def make_service(path):
    return RAGService(
        MemoryKnowledgeStore(),
        HashEmbedding(),
        TokenOverlapReranker(),
        RunStore(path),
        Scope(customer="test", tenant="dev"),
    )


def test_atomic_claim_across_connections(tmp_path):
    r = make_service(tmp_path)
    plan = r.create_plan("Create HTTPS to HTTP")

    def claim(_):
        return RunStore(tmp_path).claim_plan(plan.id, "test", "dev")

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(claim, range(20))) == 1
    with pytest.raises(ValueError):
        r.execute_plan(plan.id)


def test_scoped_plan_api_and_replay(tmp_path):
    r = make_service(tmp_path)
    with TestClient(create_app(tmp_path, test_mode=True, rag_service=r)) as client:
        assert (
            client.post("/api/rag/plans", json={"requirement": "Create HTTPS HTTP"}).status_code
            == 401
        )
        client.get("/")
        headers = {"x-sap-cua": "workbench"}
        forged = client.post(
            "/api/rag/plans",
            headers=headers,
            json={"requirement": "Create HTTPS HTTP", "tenant": "other"},
        )
        assert forged.status_code == 422
        plan = client.post(
            "/api/rag/plans", headers=headers, json={"requirement": "Create HTTPS HTTP"}
        ).json()
        run = client.post("/api/rag/plans/" + plan["id"] + "/run", headers=headers, json={})
        assert run.status_code == 200 and run.json()["success"]
        assert (
            client.post(
                "/api/rag/plans/" + plan["id"] + "/run", headers=headers, json={}
            ).status_code
            == 409
        )
        assert client.get("/api/runs/" + plan["id"]).status_code == 404
        assert not client.get("/api/runs").json()
        assert client.get("/api/rag/metrics").status_code == 200


def test_blocked_plan_has_no_actions(tmp_path):
    r = make_service(tmp_path)
    plan = r.create_plan("Create HTTPS to HTTP in production")
    with pytest.raises(ValueError):
        r.execute_plan(plan.id)
    assert r.get_run(plan.id)["status"] == "planned"


def test_approved_html_ingestion_strips_active_content():
    metadata = dict(  # noqa: C408
        id="doc",
        document_type="text",
        collection="security",
        topic="OAuth",
        title="OAuth",
        source="internal:test",
        approved=True,
        license="owned",
    )
    doc = source_document(
        b"<h1>OAuth</h1><script>steal()</script><p>401 troubleshooting</p>",
        metadata,
        content_type="text/html",
    )
    assert "steal" not in doc.content and "401" in doc.content
    with pytest.raises(ValueError):
        source_document(b"x", {**metadata, "approved": False}, content_type="text/plain")


def test_adapter_verifier_checks_configuration(tmp_path):
    from sap_cua.engineering.execution import SandboxGateway
    from sap_cua.engineering.planner import SAPPlanner

    r = make_service(tmp_path)
    plan = SAPPlanner().plan("Create HTTPS to HTTP", r.scope)
    gateway = SandboxGateway()
    for step in plan.steps[:3]:
        result = gateway.execute(step)
    assert gateway.verify(step.verification, result)["success"]
    gateway.flows[step.args["iflow_id"]]["adapters"]["sender"]["config"]["address"] = "wrong"
    assert not gateway.verify(step.verification, result)["success"]


def test_budget_blocks_provider_before_inference():
    from sap_cua.engineering.budget import Budget
    from sap_cua.providers import BudgetedProvider

    class Provider:
        name = "test"

        def ground(self, *args):
            raise AssertionError("Must not call provider")

    with pytest.raises(RuntimeError):
        BudgetedProvider(Provider(), Budget(0), 1).ground("", None, [])


def test_router_priority_and_uncertain_write_no_fallback(tmp_path):
    from sap_cua.engineering.router import Binding, HybridRouter

    step = make_service(tmp_path).create_plan("Create package").steps[0]
    calls = []

    def timeout(step):
        calls.append("api")
        raise TimeoutError()

    def dom(step):
        calls.append("dom")
        return {"success": True}

    router = HybridRouter(
        [
            Binding("playwright", lambda _: True, dom, lambda *args: {"success": True}),
            Binding("sap_api", lambda _: True, timeout, lambda *args: {"success": True}),
        ],
        lambda *args: True,
    )
    result = router.execute(step, Scope(customer="test", tenant="dev"))
    assert result["outcome"] == "unknown" and calls == ["api"]


def test_unsupported_requirements_remain_blocked(tmp_path):
    r = make_service(tmp_path)
    for text in [
        "Create HTTPS to OData with JSON transformation",
        "Fix HTTP 401",
        "Delete HTTPS integration",
        "Create ProcessDirect integration",
    ]:
        assert r.create_plan(text).blockers
