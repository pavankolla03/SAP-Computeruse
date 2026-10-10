"""Fail-closed live observations: deployment acceptance is not business success."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sap_cua.runtime.sap_api import identifier


def entity(response):
    data = response.get("data")
    return data if response.get("success") is True and isinstance(data, dict) else None


def verify_package(client, package_id):
    identifier(package_id)
    observed = entity(client.get_package(package_id))
    return {
        "success": bool(observed and observed.get("Id") == package_id),
        "type": "package_exists",
        "package_id": package_id,
    }


def verify_iflow(client, package_id, iflow_id):
    identifier(package_id)
    identifier(iflow_id)
    observed = entity(client.get_iflow(iflow_id))
    return {
        "success": bool(
            observed and observed.get("Id") == iflow_id and observed.get("PackageId") == package_id
        ),
        "type": "iflow_exists",
        "package_id": package_id,
        "iflow_id": iflow_id,
    }


def verify_deployment(
    client,
    iflow_id,
    task_id,
    *,
    timeout=60,
    poll_interval=2,
    max_polls=30,
    monotonic: Callable = time.monotonic,
    sleep: Callable = time.sleep,
):
    identifier(iflow_id)
    identifier(task_id)
    if (
        not math.isfinite(timeout)
        or not 0 < timeout <= 300
        or not math.isfinite(poll_interval)
        or not 0 < poll_interval <= 30
        or not 1 <= max_polls <= 100
    ):
        raise ValueError("Invalid deployment observation budget")
    deadline = monotonic() + timeout
    checks = []
    result = {
        "success": False,
        "type": "deployment",
        "iflow_id": iflow_id,
        "task_id": task_id,
        "business_test_verified": False,
        "checks": checks,
        "reason": "observation_budget_exhausted",
    }
    for _ in range(max_polls):
        if monotonic() >= deadline:
            break
        build = entity(client.deployment_status(task_id))
        # Status text is constrained; raw SAP errors/payloads never enter evidence.
        build_status = build.get("Status") if build else None
        if build_status not in ("SUCCESS", "FAIL", "DEPLOYING", "FAIL_ON_LICENSE_ERROR"):
            result["reason"] = "unrecognized_build_response"
            return result
        checks.append({"stage": "build", "status": build_status})
        if monotonic() >= deadline:
            break
        if build_status in ("FAIL", "FAIL_ON_LICENSE_ERROR"):
            result["reason"] = "build_failed"
            return result
        if build_status == "SUCCESS":
            runtime = entity(client.runtime_status(iflow_id))
            runtime_status = str(runtime.get("Status", "")).upper() if runtime else ""
            if (
                not runtime
                or runtime.get("Id") != iflow_id
                or runtime_status not in ("STARTED", "STARTING", "STOPPING", "ERROR")
            ):
                result["reason"] = "unrecognized_runtime_response"
                return result
            checks.append({"stage": "runtime", "status": runtime_status})
            if monotonic() >= deadline:
                break
            if runtime_status == "STARTED":
                result.update(success=True, reason="build_success_and_runtime_started")
                return result
            if runtime_status in ("ERROR", "STOPPING"):
                result["reason"] = "runtime_not_ready"
                return result
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(poll_interval, remaining))
    return result


def parse_sap_time(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", value)
    try:
        if match:
            return datetime.fromtimestamp(int(match[1]) / 1000, tz=UTC)
        stamp = datetime.fromisoformat(value)
        return stamp.astimezone(UTC) if stamp.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def verify_message(client, iflow_id, message_id, not_before: datetime):
    identifier(iflow_id)
    identifier(message_id)
    if not_before.tzinfo is None:
        raise ValueError("Test start must have a timezone")
    response = client.query_mpl(
        {
            "$filter": f"MessageGuid eq '{message_id}'",
        },
        limit=2,
    )
    payload = entity(response)
    rows = payload.get("results") if payload else None
    reason = "unexpected_mpl_response"
    success = False
    if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
        row = rows[0]
        artifact = row.get("IntegrationArtifact")
        artifact_id = (
            artifact.get("Id") if isinstance(artifact, dict) else row.get("IntegrationFlowName")
        )
        identity_consistent = (
            "IntegrationFlowName" not in row or row["IntegrationFlowName"] == artifact_id
        )
        started = parse_sap_time(row.get("LogStart"))
        ended = parse_sap_time(row.get("LogEnd"))
        success = (
            row.get("MessageGuid") == message_id
            and artifact_id == iflow_id
            and identity_consistent
            and row.get("Status") == "COMPLETED"
            and started is not None
            and ended is not None
            and started >= not_before
            and ended >= started
        )
        reason = (
            "fresh_correlated_message_completed"
            if success
            else "message_identity_time_or_status_mismatch"
        )
    return {
        "success": bool(success),
        "type": "mpl_completed",
        "iflow_id": iflow_id,
        "message_id": message_id,
        "reason": reason,
        "business_payload_verified": False,
    }
