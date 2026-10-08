"""Conservative deterministic requirement compiler with retrievable evidence.

Only supported patterns compile. Free-form unknown requirements remain blocked;
retrieved instructions never alter permissions, tenant scope or execution code.
"""

from __future__ import annotations

import re
import uuid

from sap_cua.engineering.schemas import SemanticPlan, SemanticStep
from sap_cua.rag.schemas import Scope


class SAPPlanner:
    name = "deterministic_sap_patterns_v1"

    def __init__(self, retriever=None):
        self.retriever = retriever

    def plan(self, requirement: str, scope: Scope, *, backend="sandbox", use_rag=True):
        if not 1 <= len(requirement.strip()) <= 4000:
            raise ValueError("Requirement must be 1–4000 characters")
        hits = self.retriever.search(requirement, scope) if use_rag and self.retriever else []
        sources = [h.model_dump() for h in hits]
        ids = [h.id for h in hits]
        q = requirement.lower()
        run_id = uuid.uuid4().hex[:12]
        standards = {}
        for hit in hits:
            if hit.collection == "customer_standards" and hit.customer_scope == scope.customer:
                standards.update(hit.facts)
        prefix = standards.get("package_prefix", "AGENT_")
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,30}", prefix):
            raise ValueError("Retrieved naming standard is invalid")
        package = prefix + run_id.upper()
        flow = "FLOW_" + run_id.upper()
        steps = []
        blockers = []
        pattern = "UNSUPPORTED"

        def add(action, args=None, verification=None, executor="sap_api", risk="medium"):
            id = f"step-{len(steps) + 1}"
            steps.append(
                SemanticStep(
                    id=id,
                    action=action,
                    args=args or {},
                    depends_on=[steps[-1].id] if steps else [],
                    preferred_executor=executor,
                    risk=risk,
                    verification=verification or {},
                    source_ids=ids,
                    preconditions=["Previous step independently verified"] if steps else [],
                )
            )

        if scope.role == "viewer":
            blockers.append("Viewer role cannot create or deploy integrations")
        if any(
            word in q
            for word in (
                "production",
                " prod",
                "delete",
                "undeploy",
                "rotate credential",
                "trust configuration",
                "role administration",
            )
        ):
            blockers.append(
                "Production/destructive/security changes require a separately approved scope"
            )
        if any(
            word in q for word in ("failing", "failed", "fix ", "repair ", "401", "429", "timeout")
        ):
            pattern = "DIAGNOSE_FAILURE"
            code = (
                "401"
                if "401" in q
                else "429"
                if "429" in q
                else "timeout"
                if "timeout" in q
                else "unknown"
            )
            add("QUERY_MPL", {"error_class": code}, {"type": "mpl_observed"}, risk="low")
            add(
                "DIAGNOSE_ERROR",
                {"error_class": code},
                {"type": "diagnosis_supported"},
                executor="mcp",
                risk="low",
            )
            if "fix " in q or "repair " in q:
                blockers.append(
                    "Repair requires an observed tenant failure and approved configuration change; this compiler only diagnoses known errors"
                )
            if code == "unknown":
                blockers.append("A target iFlow and observed failure are required for repair")
        elif "package" in q and not any(
            x in q for x in ("iflow", "flow", "integration for", "odata", "https", "sftp", "jms")
        ):
            pattern = "CREATE_PACKAGE"
            name = re.search(
                r'(?:called|named)\s+["\']?([A-Za-z][A-Za-z0-9_]{0,60})', requirement, re.IGNORECASE
            )
            if name:
                package = name.group(1)
            add(
                "CREATE_PACKAGE",
                {"package_id": package, "name": package},
                {"type": "package_exists", "package_id": package},
            )
        elif any(
            x in q
            for x in (
                "https",
                "sftp",
                "soap",
                "odata",
                "jms",
                "event mesh",
                "processdirect",
                "iflow",
                "integration flow",
            )
        ):
            sender = (
                "SFTP"
                if "sftp" in q
                else "SOAP"
                if re.match(r"(?:create\s+)?soap", q)
                else "JMS"
                if q.startswith("jms")
                else "EventMesh"
                if "event mesh" in q
                else "HTTPS"
            )
            receiver = (
                "ODataV4"
                if re.search(r"odata\s*(v?4)", q)
                else "ODataV2"
                if "odata" in q
                else "SOAP"
                if "soap" in q and sender != "SOAP"
                else "HTTP"
            )
            pattern = f"{sender.upper()}_TO_{receiver.upper()}"
            base = {"package_id": package, "iflow_id": flow}
            add(
                "CREATE_PACKAGE",
                {"package_id": package, "name": package},
                {"type": "package_exists", "package_id": package},
            )
            add("CREATE_IFLOW", {**base, "name": flow}, {"type": "iflow_exists", **base})
            add(
                "CONFIGURE_ADAPTER",
                {
                    **base,
                    "direction": "sender",
                    "adapter": sender,
                    "config": {"address": "/agent/" + run_id},
                },
                {"type": "adapter", "direction": "sender", "adapter": sender, **base},
                executor="template",
            )
            components = []
            if "modifier" in q:
                components.append("ContentModifier")
            if "router" in q:
                components.append("Router")
            if "splitter" in q:
                components.append("Splitter")
            if "groovy" in q:
                blockers.append(
                    "Groovy generation requires a tested, approved code pattern; arbitrary code is not deployed"
                )
            if "jms" in q and sender != "JMS":
                components.append("JMSRetry")
            if "exception" in q or "error handling" in q:
                components.append("ExceptionSubprocess")
            for component in components:
                add(
                    "ADD_COMPONENT",
                    {
                        **base,
                        "component": component,
                        "after": components[components.index(component) - 1]
                        if components.index(component) > 0
                        else "Start",
                    },
                    {"type": "component", "component": component, **base},
                    executor="template",
                )
            credential = (
                standards.get("s4_credential_alias", "S4_OAUTH")
                if receiver.startswith("OData")
                else None
            )
            if credential is not None and (
                not isinstance(credential, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", credential)
            ):
                raise ValueError("Invalid credential alias reference")
            config = {
                "address": "${property.RECEIVER_URL}",
                "method": "POST",
                "credential_alias": credential,
            }
            add(
                "CONFIGURE_ADAPTER",
                {**base, "direction": "receiver", "adapter": receiver, "config": config},
                {"type": "adapter", "direction": "receiver", "adapter": receiver, **base},
                executor="template",
            )
            add("SAVE_IFLOW", base, {"type": "saved", **base}, executor="template")
            add("DEPLOY_IFLOW", base, {"type": "deployed", **base})
            add(
                "RUN_TEST",
                {**base, "payload": {"message": "agent-smoke-test"}},
                {"type": "test_response", **base},
            )
            add("QUERY_MPL", base, {"type": "mpl_completed", **base}, risk="low")
            if backend != "sandbox":
                blockers += [
                    "An approved exported SAP iFlow template is required for artifact construction",
                    "Configure and validate receiver endpoint and credential alias before live deployment",
                ]
            if "servicenow" in q:
                blockers.append(
                    "ServiceNow destination and approved error payload contract are required"
                )
        else:
            blockers.append("No supported deterministic SAP pattern matched this requirement")
        if any(
            word in q
            for word in ("transform", "mapping", "xslt", "multicast", "gather", "api proxy")
        ):
            blockers.append(
                "This requirement needs an approved transformation/component contract beyond the supported sandbox compiler"
            )
        if "processdirect" in q or "process direct" in q:
            blockers.append(
                "Layered ProcessDirect construction requires an approved multi-flow template"
            )
        for step in steps:
            if step.action == "CONFIGURE_ADAPTER":
                step.verification["config"] = dict(step.args["config"])
        if backend == "sap_api":
            blockers.append(
                "Live execution requires tenant capability validation and explicit run-scoped permission"
            )
        assumptions = [
            "Run-owned resource names are unique.",
            "Sandbox simulates SAP semantics and is not a tenant benchmark.",
        ]
        if pattern not in ("CREATE_PACKAGE", "DIAGNOSE_FAILURE", "UNSUPPORTED"):
            assumptions.append(
                "Receiver URL is externalized; any S4_OAUTH alias is a placeholder until tenant standards confirm it."
            )
        return SemanticPlan(
            id=run_id,
            requirement=requirement,
            planner=self.name,
            backend=backend,
            customer=scope.customer,
            tenant=scope.tenant,
            pattern=pattern,
            steps=steps,
            sources=sources,
            assumptions=assumptions,
            blockers=blockers,
        )
