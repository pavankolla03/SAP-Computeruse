from __future__ import annotations

import os
from pathlib import Path

from sap_cua.engineering.execution import EngineeringEngine
from sap_cua.engineering.planner import SAPPlanner
from sap_cua.engineering.schemas import SemanticPlan
from sap_cua.rag.ingestion import Ingestor
from sap_cua.rag.retrieval import Retriever
from sap_cua.rag.schemas import Scope


class RAGService:
    def __init__(self, store, embeddings, reranker, run_store, scope):
        self.store = store
        self.scope = scope
        self.run_store = run_store
        self.ingestor = Ingestor(store, embeddings)
        self.retriever = Retriever(store, embeddings, reranker)
        self.planner = SAPPlanner(self.retriever)
        self.engine = EngineeringEngine(run_store, self.retriever, self.ingestor)

    @classmethod
    def from_environment(cls, run_store):
        from sap_cua.rag.embeddings import CrossEncoderReranker, FastTextEmbedding
        from sap_cua.rag.store import PostgresKnowledgeStore

        dsn = os.getenv("SAP_CUA_DATABASE_URL", "")
        if not dsn:
            return None
        cache = os.getenv("SAP_CUA_EMBEDDING_CACHE", ".sap-cua/embedding-cache")
        scope = Scope(
            customer=os.getenv("SAP_CUA_CUSTOMER", "local"),
            tenant=os.getenv("SAP_CUA_TENANT", "dev"),
            role="engineer",
        )
        store = PostgresKnowledgeStore(dsn)
        return cls(store, FastTextEmbedding(cache), CrossEncoderReranker(cache), run_store, scope)

    def seed(self):
        scope = self.scope.model_copy(update={"role": "admin"})
        return self.ingestor.ingest_jsonl(Path(__file__).parents[1] / "rag/seed.jsonl", scope)

    def create_plan(self, requirement, backend="sandbox"):
        import time

        plan = self.planner.plan(requirement, self.scope, backend=backend)
        self.run_store.save(
            {
                "id": plan.id,
                "created": time.time(),
                "status": "planned",
                "customer": self.scope.customer,
                "tenant": self.scope.tenant,
                "plan": plan.model_dump(),
                "instruction": plan.requirement,
                "success": False,
                "steps": [],
            }
        )
        return plan

    def get_run(self, id):
        result = self.run_store.get(id)
        if result and (result.get("customer"), result.get("tenant")) == (
            self.scope.customer,
            self.scope.tenant,
        ):
            return result
        return None

    def execute_plan(self, id):
        record = self.get_run(id)
        if not record:
            raise KeyError("Plan not found")
        if record["status"] != "planned":
            raise ValueError("Plan already executed; create a new plan instead of replaying writes")
        plan = SemanticPlan.model_validate(record["plan"])
        if plan.blockers or plan.backend != "sandbox":
            raise ValueError("Plan is blocked: " + "; ".join(plan.blockers))
        if self.scope.role == "viewer":
            raise PermissionError("Viewer cannot execute")
        if not self.run_store.claim_plan(id, self.scope.customer, self.scope.tenant):
            raise ValueError("Plan already claimed; replay denied")
        try:
            return self.engine.run(plan, self.scope)
        except Exception as exc:
            record.update(status="failed", success=False, error=type(exc).__name__)
            self.run_store.save(record)
            raise

    def runs(self):
        return self.run_store.list_scope(self.scope.customer, self.scope.tenant)
