import argparse
import json
import os
from pathlib import Path

from sap_cua.engineering.service import RAGService
from sap_cua.rag.embeddings import CrossEncoderReranker, FastTextEmbedding
from sap_cua.rag.schemas import Scope
from sap_cua.rag.store import PostgresKnowledgeStore
from sap_cua.services.workbench import RunStore


def main(args):
    p = argparse.ArgumentParser(prog="sap-cua rag")
    p.add_argument("action", choices=["init", "search", "plan", "run", "ingest", "benchmark"])
    p.add_argument("value", nargs="?")
    p.add_argument("--data-dir", default=os.getenv("SAP_CUA_DATA_DIR", ".sap-cua"))
    opts = p.parse_args(args)
    store = PostgresKnowledgeStore(os.getenv("SAP_CUA_DATABASE_URL", ""))
    if opts.action == "init":
        store.migrate()
    cache = os.getenv("SAP_CUA_EMBEDDING_CACHE", ".sap-cua/embedding-cache")
    scope = Scope(
        customer=os.getenv("SAP_CUA_CUSTOMER", "local"),
        tenant=os.getenv("SAP_CUA_TENANT", "dev"),
        role="admin" if opts.action in ("init", "ingest") else "engineer",
    )
    r = RAGService(
        store,
        FastTextEmbedding(cache),
        CrossEncoderReranker(cache),
        RunStore(Path(opts.data_dir)),
        scope,
    )
    if opts.action == "init":
        result = {"ingestion": r.seed(), "collections": store.counts(scope)}
    elif opts.action == "search":
        result = [hit.model_dump() for hit in r.retriever.search(opts.value or "", scope)]
    elif opts.action == "plan":
        result = r.create_plan(opts.value or "").model_dump()
    elif opts.action == "run":
        result = r.execute_plan(r.create_plan(opts.value or "").id)
    elif opts.action == "ingest":
        result = r.ingestor.ingest_jsonl(Path(opts.value), scope)
    else:
        from sap_cua.engineering.benchmark import run_benchmark

        result = run_benchmark(r, Path(opts.data_dir) / "rag-benchmark.json")
    print(json.dumps(result, indent=2, default=str))
    return 0
