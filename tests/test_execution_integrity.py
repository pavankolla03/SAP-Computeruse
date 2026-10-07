"""Regression tests for execution, verification, and benchmark integrity."""
from sap_cua.agent.agent_loop import AgentLoop
from sap_cua.api.routes.agent import RunRequest, run_agent
from sap_cua.evaluation.sapbench.generator import generate_task
from sap_cua.evaluation.sapbench.runner import BenchmarkConfig, BenchmarkRunner
from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.services.executor_router import ExecutorContext, ExecutorRouter
from sap_cua.services.verifier import verify_task_state
from sap_cua.types import ExecutorType, ModelResponse, SAPAction, TaskDefinition


class ScriptedModel:
    """Deterministic test fixture; never a claimed model baseline."""
    def __init__(self, actions):
        self.actions = actions
        self.reset()

    def reset(self):
        self.index = 0

    def act(self, instruction, image, history):
        intent, args = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return ModelResponse(intent=intent, arguments=args,
                             executor=ExecutorType.SAP_API, confidence=1.0)


def test_router_cannot_succeed_without_executor():
    action = SAPAction(intent="CREATE_PACKAGE", arguments={"name": "PKG"},
                       executor=ExecutorType.SAP_API, expected_state="CREATED")
    result = ExecutorRouter(api_available=True).execute(action)
    assert result["success"] is False


def test_router_rejects_wrong_argument_type_before_mutation():
    env = SAPMockEnvironment()
    action = SAPAction(intent="CREATE_PACKAGE", arguments={"name": 42},
                       executor=ExecutorType.SAP_API, expected_state="CREATED")
    result = ExecutorRouter(True).execute(action, ExecutorContext(sap_env=env))
    assert result["success"] is False
    assert env.packages == {}


def test_mock_rejects_unimplemented_actions():
    result = SAPMockEnvironment().execute_action("SAVE_IFLOW", {"package_id": "P", "iflow_id": "F"})
    assert result["success"] is False


def test_mock_deployment_is_not_successful_message_processing():
    env = SAPMockEnvironment()
    env.create_package("P")
    env.create_iflow("P", "F")
    env.deploy_iflow("P", "F")
    assert env.query_mpl() == []


def test_loop_preserves_arguments_and_verifies_entire_goal():
    model = ScriptedModel([
        ("CREATE_PACKAGE", {"name": "P"}),
        ("CREATE_IFLOW", {"package_id": "P", "name": "F"}),
        ("DEPLOY_IFLOW", {"package_id": "P", "iflow_id": "F"}),
    ])
    loop = AgentLoop(model=model, max_steps=3)
    result = loop.run("Create and deploy F in P", verification={
        "type": "iflow_deployed", "package_id": "P", "iflow_id": "F"})
    assert result["success"] is True
    assert result["steps"] == 3
    assert result["actions"][0]["verification"]["success"] is False
    assert loop.sap_env.iFlows["P:F"]["status"] == "DEPLOYED"
    assert result["backend"] == "mock"


def test_high_confidence_and_successful_subtask_do_not_complete_task():
    loop = AgentLoop(ScriptedModel([("CREATE_PACKAGE", {"name": "WRONG"})]), max_steps=3)
    result = loop.run("Create RIGHT", verification={"type": "package_exists", "package_id": "RIGHT"})
    assert result["success"] is False
    assert result["steps"] == 3


def test_missing_verifier_cannot_claim_completion():
    result = AgentLoop(ScriptedModel([("CREATE_PACKAGE", {"name": "P"})]), max_steps=1).run("Create P")
    assert result["success"] is False
    assert "unverified" in result["error"]


def test_repeated_runs_reset_mock_environment():
    loop = AgentLoop(ScriptedModel([("CREATE_PACKAGE", {"name": "P"})]), max_steps=1)
    for _ in range(2):
        result = loop.run("Create P", verification={"type": "package_exists", "package_id": "P"})
        assert result["success"] is True


def test_verifier_requires_nonempty_valid_checks():
    env = SAPMockEnvironment()
    for spec in (None, {}, {"all": []}, {"all": [None]}, {"type": "unsupported"},
                 {"type": "package_exists"}, {"type": "http_response", "url": "https://example.com"}):
        assert verify_task_state(env, spec)["success"] is False


def test_benchmark_runs_actions_verifies_and_resets(tmp_path):
    runner = BenchmarkRunner(BenchmarkConfig(max_steps=1, output_dir=str(tmp_path)))
    runner.model = ScriptedModel([("CREATE_PACKAGE", {"name": "P"})])
    task = TaskDefinition(task_id="t", instruction="Create P",
                          verify={"type": "package_exists", "package_id": "P"})
    result = runner._run_task(task, 0)
    assert result.success is True
    assert len(result.actions) == 1
    assert result.trajectory.final_verification["success"] is True
    assert runner.env.packages == {}


def test_benchmark_rejects_confidence_without_goal(tmp_path):
    runner = BenchmarkRunner(BenchmarkConfig(max_steps=3, output_dir=str(tmp_path)))
    runner.model = ScriptedModel([("CREATE_PACKAGE", {"name": "WRONG"})])
    result = runner._run_task(TaskDefinition(task_id="t", instruction="Create RIGHT",
        verify={"type": "package_exists", "package_id": "RIGHT"}), 0)
    assert result.success is False
    assert result.trajectory.final_verification["success"] is False


def test_benchmark_applies_setup(tmp_path):
    runner = BenchmarkRunner(BenchmarkConfig(max_steps=1, output_dir=str(tmp_path)))
    runner.model = ScriptedModel([("CREATE_IFLOW", {"package_id": "P", "name": "F"})])
    task = TaskDefinition(task_id="t", instruction="Create F", setup={"type": "create_package", "name": "P"},
                          verify={"type": "iflow_exists", "package_id": "P", "iflow_id": "F"})
    assert runner._run_task(task, 0).success is True
    assert runner.env.iFlows == {}


def test_template_criteria_use_same_identifiers_as_instruction():
    task = generate_task("create_iflow", seed=12)
    import re
    assert re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", str(task.model_dump())) is None
    assert task.setup["name"] == task.verify["package_id"]
    assert task.verify["iflow_id"] in task.instruction


def test_api_uses_execution_and_unique_task_ids(monkeypatch):
    monkeypatch.setattr("sap_cua.agent.agent_loop.get_model",
                        lambda _: ScriptedModel([("CREATE_PACKAGE", {"name": "P"})]))
    req = RunRequest(instruction="Create P", max_steps=1,
                     verification={"type": "package_exists", "package_id": "P"})
    first, second = run_agent(req), run_agent(req)
    assert first.success and second.success
    assert first.task_id != second.task_id
    assert first.steps[0]["result"]["result"]["package_id"] == "P"
