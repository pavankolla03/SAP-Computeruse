from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=4000)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement: str = Field(min_length=1, max_length=4000)
    backend: Literal["sandbox", "sap_api"] = "sandbox"


def service(request):
    instance = request.app.state.rag
    if instance is None:
        raise HTTPException(
            503,
            "RAG database is not configured. Run sap-cua rag init with SAP_CUA_DATABASE_URL set.",
        )
    return instance


@router.get("/status")
def status(request: Request):
    r = service(request)
    return {
        "backend": "postgresql_pgvector",
        "scope": r.scope.model_dump(),
        "collections": r.store.counts(r.scope) if hasattr(r.store, "counts") else {},
        "embedding": r.retriever.embeddings.version,
        "reranker": r.retriever.reranker.version,
        "training_required": False,
    }


@router.post("/search")
def search(query: Query, request: Request):
    r = service(request)
    return {"hits": [hit.model_dump() for hit in r.retriever.search(query.query, r.scope)]}


@router.post("/plans", status_code=201)
def plan(payload: PlanRequest, request: Request):
    r = service(request)
    return r.create_plan(payload.requirement, payload.backend).model_dump()


@router.post("/plans/{id}/run")
def execute(id: str, request: Request):
    try:
        return service(request).execute_plan(id)
    except KeyError as exc:
        raise HTTPException(404, "Plan not found") from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/runs")
def runs(request: Request):
    return service(request).runs()


@router.get("/metrics")
def metrics(request: Request):
    service(request)
    import json

    from sap_cua.engineering.telemetry import metrics_snapshot

    return json.loads(metrics_snapshot())
