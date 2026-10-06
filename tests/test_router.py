"""Unit tests for the executor router."""

from __future__ import annotations

import pytest

from sap_cua.services.executor_router import ExecutorRouter
from sap_cua.types import SAPAction, ExecutorType, RiskLevel


@pytest.fixture
def router():
    return ExecutorRouter(api_available=True)


def test_api_preferred_for_create_package(router: ExecutorRouter):
    action = SAPAction(
        intent="CREATE_PACKAGE",
        executor=ExecutorType.SAP_API,
        arguments={"name": "TEST"},
        expected_state="CREATED",
        risk=RiskLevel.LOW,
    )
    result = router.route(action)
    assert result.executor == ExecutorType.SAP_API


def test_gui_fallback_for_component(router: ExecutorRouter):
    action = SAPAction(
        intent="ADD_ROUTER",
        executor=ExecutorType.MCP,
        arguments={},
        expected_state="ROUTER_ADDED",
        risk=RiskLevel.LOW,
    )
    result = router.route(action)
    assert result.executor == ExecutorType.MCP


def test_router_without_api(router: ExecutorRouter):
    router.api_available = False
    action = SAPAction(
        intent="CREATE_IFLOW",
        executor=ExecutorType.SAP_API,
        arguments={"package_id": "PKG", "name": "FLOW"},
        expected_state="CREATED",
        risk=RiskLevel.LOW,
    )
    result = router.route(action)
    assert result.executor != ExecutorType.SAP_API


def test_router_records_reason(router: ExecutorRouter):
    action = SAPAction(
        intent="CREATE_PACKAGE",
        executor=ExecutorType.SAP_API,
        arguments={"name": "TEST"},
        expected_state="CREATED",
        risk=RiskLevel.LOW,
    )
    router.route(action)
    assert len(router.get_last_reason()) > 0