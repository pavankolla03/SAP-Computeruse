import json

import pytest
from fastapi.testclient import TestClient

from sap_cua.api.main import create_app
from sap_cua.engineering.service import RAGService
from sap_cua.rag.embeddings import HashEmbedding, TokenOverlapReranker
from sap_cua.rag.schemas import Scope
from sap_cua.rag.store import MemoryKnowledgeStore
from sap_cua.services.workbench import RunStore

H = {"x-sap-cua": "workbench"}


def service(tmp_path, scope=None):
    return RAGService(
        MemoryKnowledgeStore(),
        HashEmbedding(),
        TokenOverlapReranker(),
        RunStore(tmp_path),
        scope or Scope(customer="acme", tenant="dev"),
    )


def document():
    return {
        "title": "OAuth guide",
        "source": "Team handbook",
        "content": "OAuth 401 adapter authorization troubleshooting",
        "collection": "sap_docs",
        "approved": True,
    }


@pytest.fixture
def workspace(tmp_path):
    r = service(tmp_path)
    with TestClient(create_app(tmp_path, test_mode=True, rag_service=r)) as c:
        c.get("/")
        yield c, r


def test_saved_plan_retrieval_and_completed_plan_retention(workspace):
    c, _r = workspace
    plan = c.post("/api/rag/plans", headers=H, json={"requirement": "Create HTTPS to HTTP"}).json()
    assert c.get("/api/rag/runs/" + plan["id"]).json()["plan"] == plan
    run = c.post("/api/rag/plans/" + plan["id"] + "/run", headers=H, json={}).json()
    assert run["success"] and run["plan"] == plan
    assert c.post("/api/rag/plans/" + plan["id"] + "/run", headers=H, json={}).status_code == 409


def test_run_and_export_enforce_tenant_scope(workspace):
    c, r = workspace
    other = service(r.run_store.path.parent, Scope(customer="other", tenant="dev"))
    plan = other.create_plan("Create package")
    assert c.get("/api/rag/runs/" + plan.id).status_code == 404
    assert c.get("/api/rag/runs/" + plan.id + "/export").status_code == 404


def test_export_sanitizes_old_records_and_downloads_json(workspace):
    c, r = workspace
    plan = r.create_plan("Create package")
    # Simulate an old record that predates sanitization, to exercise export defense.
    record = r.get_run(plan.id)
    record["client_secret"] = "must-not-escape"
    with r.run_store.connect() as db:
        db.execute("UPDATE runs SET body=? WHERE id=?", (json.dumps(record), plan.id))
    assert "must-not-escape" not in c.get("/api/rag/runs/" + plan.id).text
    assert "must-not-escape" not in c.get("/api/rag/runs").text
    response = c.get("/api/rag/runs/" + plan.id + "/export")
    assert response.status_code == 200 and response.headers["content-type"] == "application/json"
    assert response.headers["content-disposition"].startswith('attachment; filename="sap-run-')
    assert "must-not-escape" not in response.text


def test_document_import_is_incremental_scoped_and_retrievable(workspace):
    c, r = workspace
    first = c.post("/api/rag/knowledge", headers=H, json=document())
    assert first.status_code == 201 and first.json()["changed"]
    second = c.post("/api/rag/knowledge", headers=H, json=document())
    assert not second.json()["changed"]
    assert c.post(
        "/api/rag/knowledge", headers=H, json={**document(), "content": "OAuth 401 updated guide"}
    ).json()["changed"]
    hits = c.post(
        "/api/rag/search", headers=H, json={"query": "OAuth 401", "collections": ["sap_docs"]}
    ).json()["hits"]
    assert len(hits) == 1 and "updated guide" in hits[0]["content"]
    assert hits[0]["customer_scope"] == "acme" and hits[0]["tenant_scope"] == "dev"
    assert not r.retriever.search("OAuth 401", Scope(customer="other", tenant="dev"))
    assert r.retriever.search("OAuth 401", r.scope)  # Generic docs participate in normal routing.


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant": "other"},
        {"approved": False},
        {"facts": {"package_prefix": "BAD_"}},
        {"collection": "trajectories"},
        {"content": " " * 3},
        {"content": "x" * 25001},
    ],
)
def test_invalid_or_forged_knowledge_rejected(workspace, extra):
    c, _ = workspace
    assert c.post("/api/rag/knowledge", headers=H, json={**document(), **extra}).status_code == 422


def test_viewer_cannot_ingest(workspace):
    c, r = workspace
    r.scope = r.scope.model_copy(update={"role": "viewer"})
    assert c.post("/api/rag/knowledge", headers=H, json=document()).status_code == 403


@pytest.mark.parametrize(
    "path,body",
    [
        ("/plans", {"requirement": "  "}),
        ("/search", {"query": "\n"}),
        ("/search", {"query": "OAuth", "collections": ["unknown"]}),
        ("/search", {"query": "OAuth", "collections": []}),
    ],
)
def test_invalid_search_and_requirement_are_validation_errors(workspace, path, body):
    c, _ = workspace
    assert c.post("/api/rag" + path, headers=H, json=body).status_code == 422
