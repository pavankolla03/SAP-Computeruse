from sap_cua.services.executor_router import ExecutorRouter
from sap_cua.types import SAPAction


def action():
    return SAPAction(
        intent="DEPLOY_IFLOW",
        executor="sap_api",
        arguments={"package_id": "DEMO", "iflow_id": "FLOW"},
        expected_state="",
        risk="low",
        requires_approval=False,
    )


def test_model_cannot_lower_authoritative_action_risk():
    seen = []
    bindings = {"sap_api": {"intents": {"DEPLOY_IFLOW"}, "execute": lambda _: {"success": True}}}
    router = ExecutorRouter(
        True, bindings=bindings, authorize=lambda a: seen.append(a.risk.value) or False
    )
    assert not router.execute(action())["success"]
    assert seen != ["low"]


def test_timeout_does_not_trigger_second_executor():
    calls = []

    def write(_):
        calls.append("api")
        raise TimeoutError()

    bindings = {
        "sap_api": {"intents": {"DEPLOY_IFLOW"}, "execute": write},
        "playwright": {"intents": {"DEPLOY_IFLOW"}, "execute": lambda _: calls.append("browser")},
    }
    result = ExecutorRouter(True, bindings=bindings, authorize=lambda _: True).execute(action())
    assert result["outcome"] == "unknown"
    assert calls == ["api"]


def test_no_implicit_authorization():
    bindings = {"sap_api": {"intents": {"DEPLOY_IFLOW"}, "execute": lambda _: {"success": True}}}
    assert not ExecutorRouter(True, bindings=bindings).execute(action())["success"]
