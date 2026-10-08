"""Run in CI with pgvector service; isolated random tenant and document keys."""

import os
import uuid

import pytest

from sap_cua.rag.embeddings import HashEmbedding, TokenOverlapReranker
from sap_cua.rag.ingestion import Ingestor
from sap_cua.rag.retrieval import Retriever
from sap_cua.rag.schemas import KnowledgeObject, Scope
from sap_cua.rag.store import PostgresKnowledgeStore


@pytest.mark.skipif(
    not os.getenv("SAP_CUA_TEST_DATABASE_URL"), reason="PostgreSQL integration DSN not configured"
)
def test_postgres_incremental_and_tenant_filter():
    store = PostgresKnowledgeStore(os.environ["SAP_CUA_TEST_DATABASE_URL"])
    store.migrate()
    scope = Scope(customer="test-" + uuid.uuid4().hex, tenant="dev")
    embedding = HashEmbedding()
    ingest = Ingestor(store, embedding)
    retrieve = Retriever(store, embedding, TokenOverlapReranker())
    doc = KnowledgeObject(
        id="tenant-only",
        document_type="text",
        collection="security",
        topic="OAuth",
        title="OAuth 401",
        content="OAuth 401 private guidance",
        source="internal:test",
        customer_scope=scope.customer,
        tenant_scope="dev",
        security_classification="internal",
        approved=True,
    )
    assert ingest.ingest(doc, scope)["changed"]
    assert not ingest.ingest(doc, scope)["changed"]
    hits = retrieve.search("OAuth 401", scope)
    assert any(h.customer_scope == scope.customer for h in hits)
    assert not any(
        h.customer_scope == scope.customer
        for h in retrieve.search("OAuth 401", Scope(customer="other", tenant="dev"))
    )
    assert ingest.ingest(
        doc.model_copy(update={"content": "OAuth 401 updated private guidance"}), scope
    )["changed"]
    assert (
        len([h for h in retrieve.search("OAuth 401", scope) if h.customer_scope == scope.customer])
        == 1
    )
