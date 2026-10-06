"""Unit tests for SAP-CUA core types."""

from __future__ import annotations

import pytest

from sap_cua.types import (
    ActionResult,
    ExecutorType,
    GUIAction,
    GUIActionType,
    RiskLevel,
    SAPAction,
    SAPState,
    Page,
    SAPModule,
)


def test_gui_action_creation():
    action = GUIAction(type=GUIActionType.CLICK, x=0.5, y=0.5)
    assert action.type == GUIActionType.CLICK
    assert action.x == 0.5
    assert action.y == 0.5


def test_gui_action_drag():
    action = GUIAction(type=GUIActionType.DRAG, x=0.1, y=0.1, x2=0.5, y2=0.5)
    assert action.x2 == 0.5
    assert action.y2 == 0.5


def test_sap_action_defaults():
    action = SAPAction(
        intent="CREATE_PACKAGE",
        executor=ExecutorType.SAP_API,
        expected_state="CREATED",
    )
    assert action.confidence == 0.0
    assert action.risk == RiskLevel.LOW
    assert action.requires_approval is False


def test_sap_action_with_gui():
    action = SAPAction(
        intent="CLICK",
        executor=ExecutorType.GUI,
        gui_action=GUIAction(type=GUIActionType.CLICK, x=0.5, y=0.5),
        expected_state="CLICKED",
    )
    assert action.gui_action is not None
    assert action.gui_action.type == GUIActionType.CLICK


def test_sap_state_defaults():
    state = SAPState()
    assert state.page == Page.UNKNOWN
    assert state.module is None
    assert state.resolution == (1440, 900)


def test_action_result_success():
    action = SAPAction(
        intent="TEST",
        executor=ExecutorType.GUI,
        expected_state="OK",
    )
    result = ActionResult(action=action, success=True, observed_state="OK")
    assert result.success is True
    assert result.duration_ms == 0


def test_executor_types():
    assert ExecutorType.SAP_API.value == "sap_api"
    assert ExecutorType.PLAYWRIGHT.value == "playwright"
    assert ExecutorType.GUI.value == "gui"
    assert ExecutorType.MCP.value == "mcp"
    assert ExecutorType.TERMINAL.value == "terminal"
    assert ExecutorType.CODE.value == "code"


def test_risk_levels():
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.HIGH.value == "high"
    assert RiskLevel.CRITICAL.value == "critical"


def test_sap_action_serialization():
    action = SAPAction(
        intent="CREATE_PACKAGE",
        executor=ExecutorType.SAP_API,
        arguments={"name": "TEST"},
        expected_state="CREATED",
    )
    data = action.model_dump()
    assert data["intent"] == "CREATE_PACKAGE"
    assert data["executor"] == "sap_api"
    assert data["arguments"]["name"] == "TEST"