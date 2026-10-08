"""Verified semantic sandbox execution. No live writes are enabled by this engine."""

from __future__ import annotations

import copy
import os
import time

from sap_cua.engineering.budget import Budget
from sap_cua.engineering.schemas import SemanticPlan
from sap_cua.rag.schemas import KnowledgeObject, Scope
from sap_cua.security import sanitize_data


class SandboxGateway:
    def __init__(self):
        self.packages = {}
        self.flows = {}
        self.mpl = []
        self.sequence = 0
        self.faults = {}

    def execute(self, step):
        a = step.args
        action = step.action
        key = a.get("iflow_id")
        flow = self.flows.get(key)
        if action == "CREATE_PACKAGE":
            if a["package_id"] in self.packages:
                raise ValueError("Package already exists")
            self.packages[a["package_id"]] = {"name": a["name"]}
        elif action == "CREATE_IFLOW":
            if a["package_id"] not in self.packages:
                raise ValueError("Package missing")
            if key in self.flows:
                raise ValueError("Flow already exists")
            self.flows[key] = {
                "package_id": a["package_id"],
                "components": ["Start", "End"],
                "adapters": {},
                "saved": False,
                "deployed": False,
                "tests": [],
            }
        elif action == "CONFIGURE_ADAPTER":
            if flow is None:
                raise ValueError("Flow missing")
            flow["adapters"][a["direction"]] = {
                "adapter": a["adapter"],
                "config": copy.deepcopy(a["config"]),
            }
            flow["saved"] = False
        elif action == "ADD_COMPONENT":
            if flow is None or a["after"] not in flow["components"]:
                raise ValueError("Insertion anchor missing")
            if a["component"] not in flow["components"]:
                flow["components"].insert(flow["components"].index(a["after"]) + 1, a["component"])
            flow["saved"] = False
        elif action == "SAVE_IFLOW":
            if not flow or not {"sender", "receiver"}.issubset(flow["adapters"]):
                raise ValueError("Sender and receiver must be configured")
            flow["saved"] = True
        elif action == "DEPLOY_IFLOW":
            if not flow or not flow["saved"]:
                raise ValueError("Flow is not saved")
            flow["deployed"] = True
        elif action == "RUN_TEST":
            if not flow or not flow["deployed"]:
                raise ValueError("Flow is not deployed")
            self.sequence += 1
            failure = self.faults.pop(key, None)
            record = {
                "id": f"message-{self.sequence}",
                "iflow_id": key,
                "status": "FAILED" if failure else "COMPLETED",
                "error": failure,
                "response_status": 503 if failure else 200,
                "created": time.time(),
            }
            flow["tests"].append(record)
            self.mpl.append(record)
            if failure:
                return {
                    "success": False,
                    "error_class": failure,
                    "message_id": record["id"],
                    "retry_safe": True,
                }
            return {"success": True, "message_id": record["id"], "response_status": 200}
        elif action == "QUERY_MPL":
            entries = [entry for entry in self.mpl if not key or entry["iflow_id"] == key]
            return {"success": True, "entries": copy.deepcopy(entries), "observed": True}
        elif action == "DIAGNOSE_ERROR":
            code = a.get("error_class")
            supported = code in ("401", "429", "timeout")
            return {
                "success": supported,
                "diagnosis": {
                    "401": "Check credential alias and OAuth token configuration without revealing secrets",
                    "429": "Respect Retry-After and reduce request rate",
                    "timeout": "Check destination reachability and service latency",
                }.get(code),
                "repair_performed": False,
            }
        else:
            raise ValueError("Unsupported semantic action: " + action)
        return {"success": True}

    def verify(self, spec, result):
        kind = spec.get("type")
        flow = self.flows.get(spec.get("iflow_id"))
        success = False
        evidence = {}
        if kind == "package_exists":
            success = spec["package_id"] in self.packages
        elif kind == "iflow_exists":
            success = bool(flow and flow["package_id"] == spec["package_id"])
        elif kind == "adapter":
            observed = (flow or {}).get("adapters", {}).get(spec["direction"], {})
            success = observed.get("adapter") == spec["adapter"] and observed.get(
                "config"
            ) == spec.get("config")
            evidence = observed
        elif kind == "component":
            success = bool(flow and spec["component"] in flow["components"])
        elif kind in ("saved", "deployed"):
            success = bool(flow and flow[kind])
        elif kind in ("test_response", "mpl_completed"):
            latest = (flow or {}).get("tests", [])
            record = latest[-1] if latest else {}
            # Correlate to this run's latest functional test, not any historical completed MPL.
            success = record.get("status") == "COMPLETED" and record.get("response_status") == 200
            evidence = copy.deepcopy(record)
        elif kind == "mpl_observed":
            success = result.get("observed") is True
            evidence = {"count": len(result.get("entries", []))}
        elif kind == "diagnosis_supported":
            success = bool(result.get("diagnosis"))
            evidence = {"diagnostic_only": True}
        return {"success": success, "type": kind, "evidence": evidence}


class EngineeringEngine:
    def __init__(self, run_store, retriever=None, ingestor=None):
        self.run_store = run_store
        self.retriever = retriever
        self.ingestor = ingestor

    @staticmethod
    def _execute(gateway, step):
        from sap_cua.engineering.telemetry import actions, tracer

        with tracer.start_as_current_span("sap.semantic_action") as span:
            span.set_attribute("sap.action", step.action)
            span.set_attribute("sap.backend", "sandbox")
            result = gateway.execute(step)
            verification = gateway.verify(step.verification, result)
            span.set_attribute("sap.verified", bool(verification["success"]))
            actions.add(1, {"action": step.action, "verified": str(bool(verification["success"]))})
            return result, verification

    def run(self, plan: SemanticPlan, scope: Scope, *, gateway=None, record_knowledge=True):
        if (plan.customer, plan.tenant) != (scope.customer, scope.tenant):
            raise PermissionError("Plan belongs to another tenant")
        if scope.role == "viewer":
            raise PermissionError("Viewer cannot execute")
        if plan.backend != "sandbox":
            raise PermissionError(
                "Live plan execution is not enabled until tenant capability validation"
            )
        if plan.blockers:
            raise ValueError("Plan is blocked: " + "; ".join(plan.blockers))
        if not plan.steps or len(plan.steps) > 100:
            raise ValueError("Plan step count is outside budget")
        from sap_cua.engineering.actions import validate_step

        for step in plan.steps:
            validate_step(step)
        gateway = gateway or SandboxGateway()
        budget = Budget(plan.max_task_cost_usd)
        start = time.monotonic()
        run = {
            "owner_pid": os.getpid(),
            "id": plan.id,
            "created": time.time(),
            "status": "running",
            "success": False,
            "instruction": plan.requirement,
            "customer": scope.customer,
            "tenant": scope.tenant,
            "backend": "sandbox",
            "planner": plan.planner,
            "sources": plan.sources,
            "steps": [],
            "usage": {
                "model_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "api_calls": 0,
                "retries": 0,
                "human_interventions": 0,
                "cost_usd": 0,
            },
            "error": None,
        }
        self.run_store.save(run)
        completed = set()
        try:
            for step in plan.steps:
                if time.monotonic() - start > plan.max_seconds:
                    raise TimeoutError("Run duration budget exhausted")
                if not set(step.depends_on).issubset(completed):
                    raise ValueError("Plan dependencies are not satisfied")
                budget.reserve(step.id, 0)
                result, verification = self._execute(gateway, step)
                attempts = []
                if not verification["success"] and result.get("retry_safe") is True:
                    for retry in range(plan.max_recovery_attempts):
                        error_class = result.get("error_class", "unknown")
                        if error_class not in ("429", "timeout", "503"):
                            break
                        playbooks = (
                            self.retriever.search("recover " + error_class, scope, limit=3)
                            if self.retriever
                            else []
                        )
                        attempts.append(
                            {
                                "attempt": retry + 1,
                                "error_class": error_class,
                                "diagnostic": "Retry idempotent synthetic test after transient fault",
                                "sources": [p.id for p in playbooks],
                            }
                        )
                        run["usage"]["retries"] += 1
                        result, verification = self._execute(gateway, step)
                        if verification["success"]:
                            break
                budget.settle(step.id, 0)
                run["steps"].append(
                    sanitize_data(
                        {
                            "action": step.model_dump(),
                            "result": result,
                            "verification": verification,
                            "recovery": attempts,
                            "executor": "sandbox:" + step.preferred_executor,
                        }
                    )
                )
                self.run_store.save(run)
                if not result.get("success") or not verification["success"]:
                    raise RuntimeError("Action or independent verification failed: " + step.action)
                completed.add(step.id)
            run.update(
                success=True,
                status="succeeded",
                verification={"success": True, "checks": len(run["steps"])},
            )
        except Exception as exc:  # noqa: BLE001 - persist failure and never replay uncertain writes
            run.update(status="failed", error=str(exc), verification={"success": False})
        run["duration_ms"] = round((time.monotonic() - start) * 1000)
        run["usage"]["cost_usd"] = float(budget.spent)
        run["knowledge_ingested"] = False
        if run["success"] and record_knowledge and self.ingestor:
            try:
                doc = KnowledgeObject(
                    id="trajectory-" + plan.id,
                    document_type="trajectory",
                    collection="trajectories",
                    topic=plan.pattern,
                    title=plan.requirement[:200],
                    content=__import__("json").dumps(
                        sanitize_data(
                            {
                                "requirement": plan.requirement,
                                "actions": [s.action for s in plan.steps],
                                "verification": run["verification"],
                                "backend": "sandbox",
                            }
                        )
                    ),
                    source="verified-run:" + plan.id,
                    provenance_kind="verified_execution",
                    customer_scope=scope.customer,
                    tenant_scope=scope.tenant,
                    security_classification="internal",
                    approved=True,
                    tags=["verified", "sandbox"],
                    applicable_actions=[s.action for s in plan.steps],
                )
                self.ingestor.ingest(doc, scope)
                run["knowledge_ingested"] = True
            except Exception as exc:  # noqa: BLE001 - persist failure and never replay uncertain writes
                run["knowledge_error"] = type(exc).__name__
        self.run_store.save(run)
        return self.run_store.get(run["id"])
