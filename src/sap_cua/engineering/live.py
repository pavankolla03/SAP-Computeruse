"""Durable, scoped SAP DEV jobs built from explicitly approved exported templates."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
import uuid
import zipfile
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sap_cua.engineering.templates import IFlowTemplateEngine
from sap_cua.runtime.sap_api.verification import (
    entity,
    verify_deployment,
    verify_iflow,
    verify_message,
    verify_package,
)
from sap_cua.security import redact_secrets, sanitize_data

MAX_ARCHIVE = 20_000_000
IDENTIFIER = r"^[A-Za-z][A-Za-z0-9_]{0,100}$"
PHASES = [
    ("preflight", "Check DEV access and target availability"),
    ("package", "Create or observe the selected package"),
    ("upload", "Upload the approved rendered iFlow"),
    ("deployment", "Deploy and observe build/runtime readiness"),
    ("test", "Send one controlled test and assert its response"),
    ("message", "Verify its fresh, correlated completed message log"),
]


class LiveTest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=2000)
    method: Literal["POST"] = "POST"
    body: str = Field(max_length=65536)
    content_type: Literal["application/json", "application/xml", "text/plain"] = "application/json"
    expected_status: int = Field(default=200, ge=200, le=299)
    response_contains: str = Field(min_length=1, max_length=4000)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value):
        from urllib.parse import urlsplit

        parsed = urlsplit(value)
        if (
            not value.startswith("/")
            or value.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in value
            or any(c.isspace() or ord(c) < 32 for c in value)
            or "%" in value
            or any(p in (".", "..") for p in value.split("/"))
        ):
            raise ValueError("Use an absolute runtime path without a host, query or traversal")
        return value

    @field_validator("body")
    @classmethod
    def bounded_bytes(cls, value):
        if len(value.encode("utf-8")) > 65536:
            raise ValueError("Test body exceeds the 65,536 byte limit")
        return value

    @field_validator("response_contains")
    @classmethod
    def nonblank_assertion(cls, value):
        if not value.strip():
            raise ValueError("A nonempty functional response assertion is required")
        return value


class LivePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    template_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    parameters: dict[str, str] = Field(default_factory=dict, max_length=64)
    package_id: str = Field(pattern=IDENTIFIER)
    iflow_id: str = Field(pattern=IDENTIFIER)
    name: str = Field(min_length=1, max_length=200)
    test: LiveTest

    @field_validator("parameters")
    @classmethod
    def bounded_parameters(cls, values):
        if any(
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,60}", key)
            or len(value) > 4000
            or "\n" in value
            or "\r" in value
            for key, value in values.items()
        ):
            raise ValueError("Invalid template parameter")
        return values


class LiveBusy(ValueError):
    pass


class Cancelled(RuntimeError):
    pass


class LiveFailure(RuntimeError):
    pass


def _contains_sensitive(value):
    """Detect redaction while allowing harmless embedded JSON reformatting."""
    if isinstance(value, dict):
        safe = sanitize_data(value)
        return any(
            safe[key] == "[REDACTED]" and item != "[REDACTED]" or _contains_sensitive(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return any(_contains_sensitive(item) for item in value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            return _contains_sensitive(parsed)
        return redact_secrets(value)[0] != value
    return False


def _private_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _bundle_identity(content):
    """Read the OSGi main-section identity without modifying approved source bytes."""
    from sap_cua.runtime.sap_api import identifier

    lines = []
    for line in content.splitlines():
        if not line:
            break
        if line.startswith(" "):
            if not lines:
                raise ValueError("Invalid manifest continuation")
            lines[-1] += line[1:]
        else:
            lines.append(line)
    identities = []
    for line in lines:
        key, separator, value = line.partition(":")
        if separator and key.lower() == "bundle-symbolicname":
            identities.append(identifier(value.split(";", 1)[0].strip()))
    if len(identities) > 1:
        raise ValueError("Ambiguous manifest identity")
    return identities[0] if identities else None


def _inspect_archive(archive: bytes):
    if len(archive) > MAX_ARCHIVE:
        raise ValueError("Template exceeds the archive limit")
    parameters = set()
    artifact_id = None
    manifest_seen = False
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        if len(source.infolist()) > 1000:
            raise ValueError("Too many archive entries")
        total = 0
        for info in source.infolist():
            total += info.file_size
            if info.file_size > MAX_ARCHIVE or total > 100_000_000:
                raise ValueError("Expanded template exceeds the archive limit")
            if info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Encrypted entries and symbolic links are not accepted")
            data = source.read(info)
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                # Opaque binaries cannot be reviewed for embedded credentials.
                raise ValueError("Templates must contain reviewable UTF-8 source files") from None
            if info.filename.lower() == "meta-inf/manifest.mf":
                if manifest_seen:
                    raise ValueError("Ambiguous template manifest")
                manifest_seen = True
                artifact_id = _bundle_identity(content)
            _, findings = redact_secrets(content)
            if any(f["type"] not in ("REDACTED_EMAIL", "REDACTED_CARD") for f in findings):
                raise ValueError(
                    "Template may contain credentials; use managed credential references"
                )
            if Path(info.filename).suffix in (".xml", ".iflw"):
                parameters.update(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", content))
    if len(parameters) > 64:
        raise ValueError("Too many template parameters")
    # The renderer performs traversal, duplicate, XML and entry-presence validation.
    digest = hashlib.sha256(archive).hexdigest()
    IFlowTemplateEngine().render(
        archive, {key: "REVIEW_VALUE" for key in parameters}, approved_sha256=digest
    )
    return digest, sorted(parameters), artifact_id


class LiveService:
    def __init__(self, directory, run_store, scope, connections, retriever=None, ingestor=None):
        self.run_store = run_store
        self.scope = scope
        self.connections = connections
        self.retriever = retriever
        self.ingestor = ingestor
        identity = hashlib.sha256((scope.customer + "\0" + scope.tenant).encode()).hexdigest()
        self.directory = Path(directory) / "live" / identity
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self._lock = threading.Lock()
        self._active_id = None
        self._cancel = threading.Event()
        self._thread = None
        self.max_job_seconds = 300
        self.monotonic = time.monotonic
        self._deadline = None
        self.message_timeout = 60
        self.poll_interval = 2
        self.max_message_polls = 30

    def _writer(self):
        if self.scope.role == "viewer":
            raise PermissionError("This role cannot change or execute SAP content")

    def status(self):
        status = dict(self.connections.status())
        status.setdefault("blockers", [])
        return {**status, "active_run_id": self._active_id}

    def templates(self):
        return [json.loads(p.read_text()) for p in sorted(self.directory.glob("template-*.json"))]

    def _template(self, template_id):
        if not re.fullmatch(r"[a-f0-9]{32}", template_id):
            raise KeyError("Template not found")
        path = self.directory / ("template-" + template_id + ".json")
        if not path.is_file():
            raise KeyError("Template not found")
        return json.loads(path.read_text())

    def import_template(self, archive, title, *, approved):
        self._writer()
        if approved is not True:
            raise PermissionError("Approve the reviewed exported template before importing")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError("Template title must be 1–200 characters")
        if sanitize_data(title) != title:
            raise ValueError("Template title must not contain sensitive content")
        try:
            digest, parameters, artifact_id = _inspect_archive(archive)
        except Exception as exc:
            raise ValueError("Invalid or unreadable exported template") from exc
        template_id = uuid.uuid4().hex
        metadata = {
            "id": template_id,
            "title": title.strip(),
            "sha256": digest,
            "parameters": parameters,
            "artifact_id": artifact_id,
            "source_identity": "manifest_declared" if artifact_id else "not_declared",
            "created": time.time(),
            "customer": self.scope.customer,
            "tenant": self.scope.tenant,
            "approved": True,
            "validated_xml": True,
            "tenant_validated": False,
            "size_bytes": len(archive),
            "artifact_url": f"/api/live/templates/{template_id}/artifact",
        }
        _private_write(self.directory / ("template-" + template_id + ".zip"), archive)
        _private_write(
            self.directory / ("template-" + template_id + ".json"),
            json.dumps(metadata).encode(),
        )
        return metadata

    def template_artifact(self, template_id):
        metadata = self._template(template_id)
        archive = (self.directory / ("template-" + template_id + ".zip")).read_bytes()
        if hashlib.sha256(archive).hexdigest() != metadata["sha256"]:
            raise ValueError("Approved template integrity check failed")
        return archive

    def create_plan(self, request: LivePlanRequest):
        self._writer()
        body = request.model_dump()
        if _contains_sensitive(body):
            raise ValueError(
                "Use synthetic test data and managed credential references; secrets cannot be stored in plans"
            )
        template = self._template(request.template_id)
        if template.get("artifact_id") and template["artifact_id"] != request.iflow_id:
            raise ValueError(
                "Selected iFlow ID must match the approved template manifest identity; automatic cloning is not supported"
            )
        archive = self.template_artifact(request.template_id)
        rendered = IFlowTemplateEngine().render(
            archive, request.parameters, approved_sha256=template["sha256"]
        )
        status = self.status()
        from sap_cua.runtime.sap_api.profiles import runtime_path

        runtime_path(request.test.path, status.get("profile", {}).get("allowed_test_prefix", "/"))
        blockers = list(status.get("blockers", []))
        if not status.get("configured"):
            blockers.append("Configure the SAP DEV connection and runtime test credentials")
        if not status.get("execution_enabled"):
            blockers.append("Enable execution for the configured DEV tenant")
        run_id = uuid.uuid4().hex
        immutable_request = json.dumps(body, ensure_ascii=False).encode()
        request_sha = hashlib.sha256(immutable_request).hexdigest()
        plan = {
            **body,
            "id": run_id,
            "type": "live_template",
            "backend": "sap_api",
            "max_seconds": self.max_job_seconds,
            "template_title": template["title"],
            "source_artifact_id": template.get("artifact_id"),
            "source_identity": template.get("source_identity", "not_declared"),
            "template_sha256": template["sha256"],
            "artifact_sha256": rendered["sha256"],
            "request_sha256": request_sha,
            "test_body_sha256": hashlib.sha256(request.test.body.encode()).hexdigest(),
            "connection_revision": status.get("connection_revision"),
            "tenant_host": status.get("tenant_host"),
            "blockers": list(dict.fromkeys(blockers)),
            "steps": [
                {"id": key, "action": title, "verification": "Independent SAP observation required"}
                for key, title in PHASES
            ],
            "artifact_url": f"/api/live/plans/{run_id}/artifact",
            "sources": [],
            "assumptions": [
                "The approved template defines the complete integration behavior.",
                "An existing iFlow is never overwritten; writes and test sends are never retried.",
                "Response assertion and correlated MPL establish only this supplied test contract.",
            ],
        }
        if self.retriever:
            try:
                hits = self.retriever.search(template["title"], self.scope, limit=3)
                plan["sources"] = [h.model_dump() for h in hits]
            except Exception:  # noqa: BLE001 - retrieval cannot authorize or stop the approved job
                plan["knowledge_note"] = (
                    "Knowledge retrieval unavailable; template contract is unchanged"
                )
        _private_write(self.directory / ("plan-" + run_id + ".zip"), rendered["artifact"])
        _private_write(self.directory / ("plan-" + run_id + ".json"), immutable_request)
        record = {
            "id": run_id,
            "created": time.time(),
            "status": "planned",
            "success": False,
            "backend": "sap_api",
            "type": "live_template",
            "customer": self.scope.customer,
            "tenant": self.scope.tenant,
            "instruction": "Deploy and test approved template: " + template["title"],
            "plan": plan,
            "steps": [],
            "error": None,
        }
        self.run_store.save(record)
        return sanitize_data(plan)

    def get_run(self, run_id):
        record = self.run_store.get(run_id)
        if not record or (record.get("customer"), record.get("tenant"), record.get("type")) != (
            self.scope.customer,
            self.scope.tenant,
            "live_template",
        ):
            raise KeyError("Live run not found")
        safe = sanitize_data(record)
        if self._active_id == run_id:
            safe["cancellation_requested"] = self._cancel.is_set()
        return safe

    def runs(self):
        return sanitize_data(
            [
                r
                for r in self.run_store.list_scope(self.scope.customer, self.scope.tenant)
                if r.get("type") == "live_template"
            ]
        )

    def plan_artifact(self, run_id):
        record = self.get_run(run_id)
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise KeyError("Live run not found")
        archive = (self.directory / ("plan-" + run_id + ".zip")).read_bytes()
        if hashlib.sha256(archive).hexdigest() != record["plan"]["artifact_sha256"]:
            raise ValueError("Rendered artifact integrity check failed")
        return archive

    def _immutable_request(self, run_id, plan):
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise KeyError("Live run not found")
        raw = (self.directory / ("plan-" + run_id + ".json")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != plan["request_sha256"]:
            raise ValueError("Immutable request integrity check failed")
        return LivePlanRequest.model_validate_json(raw).model_dump()

    def start_run(self, run_id):
        self._writer()
        record = self.get_run(run_id)
        status = self.status()
        if record["status"] != "planned":
            raise ValueError("This plan has already been claimed; create a new plan")
        if record["plan"]["blockers"]:
            raise ValueError("Resolve configuration blockers and generate a new plan")
        if (
            not status.get("configured")
            or not status.get("execution_enabled")
            or status.get("connection_revision") != record["plan"]["connection_revision"]
        ):
            raise ValueError("Connection changed or execution is disabled; generate a new plan")
        self.plan_artifact(run_id)
        self._immutable_request(run_id, record["plan"])
        if not self._lock.acquire(blocking=False):
            raise LiveBusy("A live job is already active")
        try:
            if not self.run_store.claim_plan(run_id, self.scope.customer, self.scope.tenant):
                raise ValueError("Plan already claimed; replay denied")
            self._active_id = run_id
            self._cancel = threading.Event()
            self._thread = threading.Thread(
                target=self._run, args=(run_id,), name="sap-live-" + run_id, daemon=True
            )
            self._thread.start()
        except Exception:
            self._active_id = None
            self._lock.release()
            raise
        return {"id": run_id, "status": "running"}

    def cancel(self, run_id):
        self._writer()
        record = self.get_run(run_id)
        if self._active_id != run_id or record["status"] != "running":
            raise ValueError("This job is not active")
        self._cancel.set()
        return {"id": run_id, "status": "running", "cancellation_requested": True}

    def _check_cancel(self):
        if self._deadline is not None and self.monotonic() >= self._deadline:
            raise LiveFailure(
                "Live job exceeded its total duration budget; completed changes were not rolled back"
            )
        if self._cancel.is_set():
            raise Cancelled("Cancellation requested; completed SAP changes were not rolled back")

    def _save_step(self, run, stage, *, status="running", result=None, verification=None):
        if run["steps"] and run["steps"][-1]["stage"] == stage:
            entry = run["steps"][-1]
        else:
            entry = {"stage": stage, "started": time.time()}
            run["steps"].append(entry)
        entry.update(status=status)
        if result is not None:
            entry["result"] = sanitize_data(result)
        if verification is not None:
            entry["verification"] = sanitize_data(verification)
        self.run_store.save(run)

    @staticmethod
    def _write_evidence(response):
        return {key: response.get(key) for key in ("success", "status_code", "outcome")}

    def _record_knowledge(self, run):
        run["knowledge_ingested"] = False
        if not run.get("success") or not self.ingestor:
            return
        from sap_cua.rag.schemas import KnowledgeObject

        try:
            # Public phase outcomes only: no request/response payloads or credentials.
            doc = KnowledgeObject(
                id="trajectory-" + run["id"],
                document_type="trajectory",
                collection="trajectories",
                topic="approved_template_dev",
                title="Verified approved-template DEV workflow",
                content=json.dumps(
                    {
                        "backend": "sap_api",
                        "template_sha256": run["plan"]["template_sha256"],
                        "phases": [
                            {"stage": s["stage"], "verified": s["status"] == "succeeded"}
                            for s in run["steps"]
                        ],
                        "verification": run["verification"],
                    }
                ),
                source="verified-run:" + run["id"],
                provenance_kind="verified_execution",
                customer_scope=self.scope.customer,
                tenant_scope=self.scope.tenant,
                security_classification="internal",
                approved=True,
                tags=["verified", "sap_api"],
                applicable_actions=[
                    "CREATE_PACKAGE",
                    "CREATE_IFLOW",
                    "DEPLOY_IFLOW",
                    "RUN_TEST",
                    "QUERY_MPL",
                ],
            )
            self.ingestor.ingest(doc, self.scope)
            run["knowledge_ingested"] = True
        except Exception as exc:  # noqa: BLE001 - indexing failure must never repeat a SAP write
            run["knowledge_error"] = type(exc).__name__

    def _require(self, response, label):
        if response.get("success") is not True:
            outcome = response.get("outcome", "rejected")
            raise LiveFailure(
                label
                + ": "
                + (
                    "outcome unknown; do not replay"
                    if outcome == "unknown"
                    else "request or verification failed"
                )
            )

    def _sleep(self, seconds):
        self._check_cancel()
        if self._deadline is not None:
            seconds = min(seconds, max(0, self._deadline - self.monotonic()))
        self._cancel.wait(seconds)
        self._check_cancel()

    def _run(self, run_id):
        run = self.get_run(run_id)
        plan = run["plan"]
        started = self.monotonic()
        self._deadline = started + plan["max_seconds"]
        run.update(
            status="running",
            owner_pid=os.getpid(),
            success=False,
            cleanup={
                "automatic_rollback": False,
                "created_package": False,
                "uploaded_iflow": False,
                "package_id": plan["package_id"],
                "iflow_id": plan["iflow_id"],
                "note": "Inspect tenant state before manually removing resources; uncertain writes were not replayed",
            },
            usage={"write_attempts": 0, "test_attempts": 0, "retries": 0},
        )
        self.run_store.save(run)
        try:
            plan = {**plan, **self._immutable_request(run_id, plan)}
            with self.connections.lease(plan["connection_revision"]) as profile:
                from sap_cua.runtime.sap_api.profiles import runtime_path

                # Validate all controllable test inputs before the first tenant write.
                LiveTest.model_validate(plan["test"])
                runtime_path(plan["test"]["path"], profile.allowed_test_prefix)
                with profile.api_client(allow_mutations=True) as api:
                    self._check_cancel()
                    self._save_step(run, "preflight")
                    from sap_cua.runtime.sap_api.connection import probe_connection

                    probe = probe_connection(api)
                    self._require(probe, "Read access")
                    package = api.get_package(plan["package_id"])
                    package_entity = entity(package)
                    package_exists = bool(
                        package_entity and package_entity.get("Id") == plan["package_id"]
                    )
                    if not package_exists and package.get("status_code") != 404:
                        raise LiveFailure("Package target could not be verified")
                    flow = api.get_iflow(plan["iflow_id"])
                    if flow.get("status_code") != 404:
                        raise LiveFailure(
                            "Target iFlow exists or absence could not be verified; overwrite denied"
                        )
                    self._save_step(
                        run,
                        "preflight",
                        status="succeeded",
                        result={
                            "read_access": True,
                            "package_exists": package_exists,
                            "iflow_absent": True,
                        },
                    )

                    self._check_cancel()
                    self._save_step(run, "package")
                    if not package_exists:
                        run["usage"]["write_attempts"] += 1
                        self.run_store.save(run)
                        response = api.create_package(
                            plan["package_id"], package_id=plan["package_id"]
                        )
                        self._save_step(run, "package", result=self._write_evidence(response))
                        self._require(response, "Create package")
                        run["cleanup"]["created_package"] = True
                    verified = verify_package(api, plan["package_id"])
                    self._require(verified, "Package identity")
                    self._save_step(run, "package", status="succeeded", verification=verified)

                    self._check_cancel()
                    self._save_step(run, "upload")
                    archive = self.plan_artifact(run_id)
                    run["usage"]["write_attempts"] += 1
                    self.run_store.save(run)
                    response = api.create_iflow(
                        plan["package_id"],
                        plan["name"],
                        artifact_zip=archive,
                        iflow_id=plan["iflow_id"],
                    )
                    self._save_step(run, "upload", result=self._write_evidence(response))
                    self._require(response, "Upload iFlow")
                    run["cleanup"]["uploaded_iflow"] = True
                    verified = verify_iflow(api, plan["package_id"], plan["iflow_id"])
                    self._require(verified, "Uploaded iFlow identity")
                    self._save_step(run, "upload", status="succeeded", verification=verified)

                    self._check_cancel()
                    self._save_step(run, "deployment")
                    run["usage"]["write_attempts"] += 1
                    self.run_store.save(run)
                    response = api.deploy_iflow(plan["package_id"], plan["iflow_id"])
                    self._save_step(run, "deployment", result=self._write_evidence(response))
                    self._require(response, "Deploy iFlow")
                    task = entity(response)
                    task_id = task.get("task_id") if task else None
                    if not isinstance(task_id, str) or not task_id:
                        raise LiveFailure(
                            "Deployment accepted without an observable task identifier"
                        )
                    verified = verify_deployment(api, plan["iflow_id"], task_id, sleep=self._sleep)
                    self._require(verified, "Deployment readiness")
                    self._save_step(run, "deployment", status="succeeded", verification=verified)

                    self._check_cancel()
                    self._save_step(run, "test")
                    run["usage"]["test_attempts"] += 1
                    self.run_store.save(run)
                    tester = profile.test_client()
                    with tester if hasattr(tester, "__enter__") else nullcontext(tester) as client:
                        result = client.send(plan["test"])
                    # Persist only bounded evidence, never response bodies or HTTP headers.
                    safe_test = {
                        key: result.get(key)
                        for key in (
                            "success",
                            "status_code",
                            "message_id",
                            "started_at",
                            "assertions",
                            "outcome",
                            "error",
                        )
                    }
                    self._save_step(run, "test", result=safe_test)
                    self._require(result, "Functional test")
                    message_id = result.get("message_id")
                    stamp = result.get("started_at")
                    if not isinstance(message_id, str) or not isinstance(stamp, str):
                        raise LiveFailure("Runtime test did not yield trusted message correlation")
                    not_before = datetime.fromisoformat(stamp)
                    if not_before.tzinfo is None:
                        raise LiveFailure("Runtime test start lacks a timezone")
                    self._save_step(run, "test", status="succeeded")

                    self._check_cancel()
                    self._save_step(run, "message")
                    deadline = time.monotonic() + self.message_timeout
                    verified = {"success": False, "reason": "observation_budget_exhausted"}
                    for _ in range(self.max_message_polls):
                        self._check_cancel()
                        if time.monotonic() >= deadline:
                            break
                        verified = verify_message(api, plan["iflow_id"], message_id, not_before)
                        if time.monotonic() >= deadline:
                            verified = {"success": False, "reason": "observation_budget_exhausted"}
                            break
                        if verified["success"]:
                            break
                        self._sleep(min(self.poll_interval, max(0, deadline - time.monotonic())))
                    self._save_step(run, "message", result=verified)
                    self._require(verified, "Fresh correlated MPL")
                    self._save_step(run, "message", status="succeeded", verification=verified)
                    self._check_cancel()
                    run.update(
                        status="succeeded",
                        success=True,
                        verification={
                            "success": True,
                            "response_asserted": True,
                            "fresh_mpl_completed": True,
                        },
                    )
        except Cancelled as exc:
            run.update(status="cancelled", success=False, error=str(exc))
        except LiveFailure as exc:
            run.update(status="failed", success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - persist failure without secret exception text
            # Third-party exception text may contain service credentials or payloads.
            run.update(
                status="failed",
                success=False,
                error="Live job stopped ("
                + type(exc).__name__
                + "); inspect evidence before retrying",
            )
        finally:
            self._record_knowledge(run)
            if run["steps"] and run["steps"][-1]["status"] == "running":
                run["steps"][-1]["status"] = run["status"]
            run["duration_ms"] = round((self.monotonic() - started) * 1000)
            run["cancellation_requested"] = self._cancel.is_set()
            try:
                self.run_store.save(run)
            finally:
                self._active_id = None
                self._deadline = None
                self._lock.release()
