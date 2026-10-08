"""Executable simulator tasks and measured retrieval metrics, never live SAP claims."""

import json
import time
from collections import Counter

from sap_cua.engineering.planner import SAPPlanner
from sap_cua.rag.evaluation import RETRIEVAL_CASES, retrieval_metrics

TASKS = [
    "Create a package called BenchPackage",
    "Create an HTTPS to HTTP integration flow",
    "Create HTTPS to OData V2 integration",
    "Create HTTPS to OData V4 integration",
    "Create SFTP to OData V4 integration",
    "Create SOAP to REST integration",
    "JMS to HTTP integration flow",
    "Create Event Mesh to OData V4 integration",
    "Create HTTPS Content Modifier to HTTP",
    "Create HTTPS Router to OData V4",
    "Create HTTPS Content Modifier Router to OData V4",
    "Create HTTPS Splitter to HTTP",
    "Create HTTPS with JMS retry to OData V4",
    "Create HTTPS exception subprocess to HTTP",
    "Create SFTP Content Modifier to OData V2",
    "Create HTTPS Router with error handling to HTTP",
    "Create HTTPS Splitter Router to OData V4",
    "Diagnose failing flow with HTTP 401",
    "Diagnose failing flow with HTTP 429",
    "Diagnose failing flow with timeout",
]


def run_benchmark(service, output):
    from sap_cua.rag.retrieval import Retriever

    no_trajectories = SAPPlanner(
        Retriever(
            service.store,
            service.retriever.embeddings,
            service.retriever.reranker,
            include_trajectories=False,
        )
    )
    records = []
    for mode in ("tools_only", "rag_plan_only", "rag_tools", "rag_tools_trajectory"):
        for index, task in enumerate(TASKS):
            start = time.monotonic()
            planner = (
                SAPPlanner()
                if mode == "tools_only"
                else service.planner
                if mode == "rag_tools_trajectory"
                else no_trajectories
            )
            plan = planner.plan(task, service.scope, use_rag=mode != "tools_only")
            if mode == "rag_plan_only":
                result = {
                    "success": None,
                    "status": "plan_only",
                    "steps": [],
                    "usage": {
                        "cost_usd": 0,
                        "model_calls": 0,
                        "retries": 0,
                        "human_interventions": 0,
                    },
                }
            else:
                result = service.engine.run(
                    plan, service.scope, record_knowledge=mode == "rag_tools_trajectory"
                )
            records.append(
                {
                    "task_id": f"sapbench-v1-{index + 1:02}",
                    "mode": mode,
                    "backend": "sandbox",
                    "success": result["success"],
                    "status": result["status"],
                    "plan_valid": not plan.blockers,
                    "time_ms": round((time.monotonic() - start) * 1000),
                    "actions": len(result["steps"]),
                    "usage": result["usage"],
                    "retrieved_ids": [s["id"] for s in plan.sources],
                    "executor_mix": dict(Counter(s["executor"] for s in result["steps"])),
                }
            )
    retrieval = []
    for query, relevant in RETRIEVAL_CASES:
        hits = service.retriever.search(query, service.scope, limit=5)
        retrieval.append(
            {
                "query": query,
                "expected": relevant,
                "retrieved": [h.id for h in hits],
                **retrieval_metrics([h.id for h in hits], relevant),
            }
        )
    summary = {
        mode: {
            "tasks": len(rows := [r for r in records if r["mode"] == mode]),
            "successes": sum(r["success"] is True for r in rows),
            "executed": sum(r["success"] is not None for r in rows),
            "mean_ms": round(sum(r["time_ms"] for r in rows) / len(rows)),
        }
        for mode in ("tools_only", "rag_plan_only", "rag_tools", "rag_tools_trajectory")
    }
    report = {
        "scope": "synthetic simulator only",
        "live_sap": False,
        "model_comparison": False,
        "summary": summary,
        "retrieval": retrieval,
        "runs": records,
        "notes": [
            "Same deterministic planner across executed modes. Equal success is not evidence of RAG uplift.",
            "Plan-only mode does not execute and has null task success.",
            "Trajectory mode adds sandbox successes; replay gain is not assumed.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report
