import json
import pytest
from fastapi.testclient import TestClient
from sap_cua.api.main import create_app
from sap_cua.services.workbench import RunStore, Workflow, example_workflow, execute_workflow


def test_full_workflow_and_persistence(tmp_path):
    result = execute_workflow(Workflow(**example_workflow()), RunStore(tmp_path))
    assert result["success"] is True
    assert len(result["steps"]) == 5
    assert result["verification"]["success"] is True
    assert RunStore(tmp_path).get(result["id"]) == result
    assert result["model"] == "scripted_workflow"


def test_verifier_cannot_be_satisfied_by_action_success(tmp_path):
    plan = example_workflow()
    plan["verification"] = {"type": "mpl_success", "iflow_key": "DEMO:HELLO"}
    result = execute_workflow(Workflow(**plan), RunStore(tmp_path))
    assert all(s["result"]["success"] for s in result["steps"])
    assert result["success"] is False


def test_step_budget_prevents_any_execution(tmp_path):
    plan = Workflow(**example_workflow(), max_steps=1)
    store = RunStore(tmp_path)
    with pytest.raises(ValueError, match="budget"):
        execute_workflow(plan, store)
    assert store.list() == []


def test_failure_stops_remaining_actions(tmp_path):
    plan = example_workflow()
    plan["actions"].insert(1, plan["actions"][0])
    result = execute_workflow(Workflow(**plan), RunStore(tmp_path))
    assert len(result["steps"]) == 2
    assert not result["success"]


def test_session_origin_host_and_run_api(tmp_path):
    with TestClient(create_app(tmp_path, test_mode=True)) as client:
        assert client.get("/api/runs").status_code == 401
        assert client.get("/", headers={"host": "evil.test"}).status_code == 400
        assert client.get("/").status_code == 200
        assert client.get("/api/runs", headers={"origin": "https://evil.test"}).status_code == 403
        assert client.post("/api/runs", json=example_workflow()).status_code == 403
        response = client.post(
            "/api/runs", json=example_workflow(), headers={"x-sap-cua": "workbench"}
        )
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert len(client.get("/api/runs").json()) == 1


def test_restart_marks_incomplete_no_replay(tmp_path):
    store = RunStore(tmp_path)
    store.save({"id": "one", "created": 1, "status": "running", "steps": []})
    store.recover_interrupted()
    assert store.get("one")["status"] == "interrupted"


def test_secret_redacted_in_persistent_run(tmp_path):
    plan = example_workflow()
    plan["actions"][0]["arguments"]["description"] = "password=secret123456"
    execute_workflow(Workflow(**plan), RunStore(tmp_path))
    assert "secret123456" not in json.dumps(RunStore(tmp_path).list())
