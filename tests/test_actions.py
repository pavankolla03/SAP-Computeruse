"""Unit tests for SAP semantic action language."""

from __future__ import annotations

import pytest

from sap_cua.sap.actions import (
    ACTION_DEFINITIONS,
    SAPActionType,
    get_action_definition,
    validate_action_arguments,
    ActionRisk,
)


def test_get_action_definition_exists():
    definition = get_action_definition(SAPActionType.CREATE_PACKAGE)
    assert definition is not None
    assert definition.action_type == SAPActionType.CREATE_PACKAGE


def test_get_action_definition_not_in_registry():
    result = get_action_definition(SAPActionType.ADD_MULTICAST)
    assert result is None


def test_create_package_definition():
    definition = get_action_definition(SAPActionType.CREATE_PACKAGE)
    assert "name" in definition.required_args
    assert definition.risk == ActionRisk.MEDIUM


def test_deploy_iflow_definition():
    definition = get_action_definition(SAPActionType.DEPLOY_IFLOW)
    assert "package_id" in definition.required_args
    assert "iflow_id" in definition.required_args


def test_validate_action_args_missing():
    errors = validate_action_arguments(SAPActionType.CREATE_PACKAGE, {})
    assert any("name" in e for e in errors)


def test_validate_action_args_present():
    errors = validate_action_arguments(SAPActionType.CREATE_PACKAGE, {"name": "TEST"})
    assert len(errors) == 0


def test_all_actions_registered():
    assert len(ACTION_DEFINITIONS) > 0
    assert SAPActionType.CREATE_PACKAGE in ACTION_DEFINITIONS
    assert SAPActionType.CREATE_IFLOW in ACTION_DEFINITIONS
    assert SAPActionType.DEPLOY_IFLOW in ACTION_DEFINITIONS


def test_delete_package_is_high_risk():
    definition = get_action_definition(SAPActionType.DELETE_PACKAGE)
    assert definition.risk == ActionRisk.HIGH
    assert definition.reversibility is False