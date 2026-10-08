"""Durable local workflow runs, independent verification, and bounded execution."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sap_cua.sap.actions import get_action_definition, validate_action_arguments
from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.security import sanitize_data
from sap_cua.services.executor_router import ExecutorContext, ExecutorRouter
from sap_cua.services.verifier import verify_task_state
from sap_cua.types import SAPAction, RiskLevel


class Workflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=4000)
    actions: list[SAPAction] = Field(min_length=1, max_length=100)
    verification: dict[str, Any]
    max_duration_seconds: int = Field(60, ge=1, le=300)
    max_steps: int = Field(25, ge=1, le=100)


def example_workflow() -> dict[str, Any]:
    def action(intent: str, **args: Any) -> dict[str, Any]:
        return {"intent": intent, "executor": "sap_api", "arguments": args, "expected_state": ""}

    return {
        "instruction": "Create a demo integration package and deploy an HTTPS flow in the local sandbox.",
        "actions": [
            action("CREATE_PACKAGE", name="Demo"),
            action("CREATE_IFLOW", package_id="DEMO", name="Hello"),
            action("ADD_SENDER", package_id="DEMO", iflow_id="HELLO", adapter="HTTPS"),
            action(
                "ADD_CONTENT_MODIFIER",
                package_id="DEMO",
                iflow_id="HELLO",
                config={"body": "Hello SAP"},
            ),
            action("DEPLOY_IFLOW", package_id="DEMO", iflow_id="HELLO"),
        ],
        "verification": {
            "all": [
                {"type": "iflow_deployed", "package_id": "DEMO", "iflow_id": "HELLO"},
                {
                    "type": "sender_adapter",
                    "package_id": "DEMO",
                    "iflow_id": "HELLO",
                    "adapter_type": "HTTPS",
                },
            ]
        },
    }


class RunStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "runs.sqlite3"
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created REAL NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL)"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, body: dict[str, Any]) -> None:
        safe = sanitize_data(body)
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?)",
                (safe["id"], safe["created"], safe["status"], json.dumps(safe)),
            )

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT body FROM runs ORDER BY created DESC LIMIT 100").fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_scope(self, customer: str, tenant: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT body FROM runs WHERE json_extract(body,'$.customer')=?
                   AND json_extract(body,'$.tenant')=? ORDER BY created DESC LIMIT 100""",
                (customer, tenant),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def claim_plan(self, run_id: str, customer: str, tenant: str) -> bool:
        """Atomically prevent concurrent execution and replay of semantic plans."""
        with self.connect() as db:
            result = db.execute(
                """UPDATE runs SET status='running',
                   body=json_set(body,'$.status','running','$.owner_pid',?)
                   WHERE id=? AND status='planned'
                   AND json_extract(body,'$.customer')=? AND json_extract(body,'$.tenant')=?""",
                (os.getpid(), run_id, customer, tenant),
            )
            return result.rowcount == 1

    def recover_interrupted(self) -> None:
        # A process restart never replays possibly completed actions.
        with self.connect() as db:
            rows = db.execute("SELECT body FROM runs WHERE status='running'").fetchall()
        for row in rows:
            body = json.loads(row[0])
            pid = body.get("owner_pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    continue
                except ProcessLookupError:
                    pass
                except PermissionError:
                    continue
            body.update(
                status="interrupted",
                success=False,
                error="Process stopped before completion; actions were not replayed",
            )
            self.save(body)


def execute_workflow(workflow: Workflow, store: RunStore) -> dict[str, Any]:
    # Validate the ENTIRE plan before changing sandbox state.
    if len(workflow.actions) > workflow.max_steps:
        raise ValueError("Workflow exceeds the step budget")
    for action in workflow.actions:
        errors = validate_action_arguments(action.intent, action.arguments)
        if errors:
            raise ValueError("; ".join(errors))
    if not workflow.verification:
        raise ValueError("An independent verifier is required")
    env = SAPMockEnvironment()  # Fresh, isolated, resettable state for every run.
    router = ExecutorRouter(api_available=True)
    run = {
        "id": str(uuid.uuid4()),
        "created": time.time(),
        "status": "running",
        "success": False,
        "owner_pid": os.getpid(),
        "backend": "mock",
        "model": "scripted_workflow",
        "instruction": workflow.instruction,
        "steps": [],
        "verification": {},
        "cost_usd": 0,
        "error": None,
    }
    start = time.monotonic()
    store.save(run)
    try:
        for action in workflow.actions:
            if time.monotonic() - start > workflow.max_duration_seconds:
                raise TimeoutError("Execution time budget exceeded")
            definition = get_action_definition(action.intent)
            action = action.model_copy(
                update={
                    "risk": RiskLevel(definition.risk.value),
                    "expected_state": definition.expected_state,
                }
            )
            result = router.execute(action, ExecutorContext(sap_env=env))
            run["steps"].append({"action": action.model_dump(mode="json"), "result": result})
            store.save(run)
            if result.get("success") is not True:
                raise RuntimeError(result.get("error") or "Action failed")
        run["verification"] = verify_task_state(env, workflow.verification)
        run["success"] = run["verification"].get("success") is True
        run["status"] = "succeeded" if run["success"] else "failed"
        if not run["success"]:
            run["error"] = "Final state did not satisfy the task verifier"
    except Exception as exc:
        run.update(status="failed", error=str(exc), success=False)
    run["duration_ms"] = round((time.monotonic() - start) * 1000)
    run["state"] = {"packages": env.packages, "iflows": env.iFlows}
    store.save(run)
    return store.get(run["id"])


def capabilities() -> dict[str, Any]:
    from sap_cua.model.opencua import MODEL_ID, MODEL_REVISION

    model_path = Path(os.getenv("SAP_CUA_MODEL_PATH", ".models/OpenCUA-7B"))
    index = model_path / "model.safetensors.index.json"
    complete = False
    if index.exists():
        try:
            shards = set(json.loads(index.read_text())["weight_map"].values())
            complete = (
                bool(shards)
                and all((model_path / s).is_file() for s in shards)
                and all(
                    (model_path / f).is_file()
                    for f in (
                        "config.json",
                        "tokenizer_config.json",
                        "tiktoken.model",
                        "preprocessor_config.json",
                        "modeling_opencua.py",
                    )
                )
            )
        except (ValueError, KeyError):
            pass
    return {
        "version": "0.2.0",
        "sandbox": "ready",
        "sap_live": "configured"
        if all(
            os.getenv(k)
            for k in ("SAP_API_BASE_URL", "SAP_TOKEN_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET")
        )
        else "credentials_required",
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "downloaded": complete,
            "sap_finetuned": False,
            "inference": "unvalidated",
        },
        "training": "CUDA and a verified screenshot dataset required",
        "rl": "not_implemented",
        "executors": {
            "mock": "ready",
            "sap_api": "contract_tested_not_tenant_validated",
            "playwright": "sandbox_only",
            "gui": "browser_only",
            "mcp": "not_connected",
            "code": "disabled",
        },
    }
