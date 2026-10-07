"""Unit tests for SAP semantic action language."""

from __future__ import annotations

import pytest

from sap_cua.sap.actions import (
    ACTION_DEFINITIONS,
    SAPActionType,
    get_action_definition,
    validate_action_arguments,
    ActionRisk,
    ActionDefinition,
)


class TestAllActionsRegistered:
    """Every SAPActionType enum member must have a complete ActionDefinition."""

    def test_every_action_type_has_definition(self):
        missing = [a for a in SAPActionType if a not in ACTION_DEFINITIONS]
        assert missing == [], f"Missing definitions for: {missing}"

    def test_definition_count_matches_enum(self):
        assert len(ACTION_DEFINITIONS) == len(list(SAPActionType))

    def test_all_definitions_have_non_empty_fields(self):
        required_fields = {
            "action_type", "arguments", "required_args", "preferred_executor",
            "fallback_executors", "risk", "expected_state", "preconditions",
            "permission_requirements", "reversibility", "security_risk_notes",
        }
        for action_type, definition in ACTION_DEFINITIONS.items():
            assert definition.action_type == action_type
            assert isinstance(definition.arguments, dict)
            assert len(definition.arguments) > 0, f"{action_type}: arguments dict is empty"
            assert isinstance(definition.required_args, list)
            assert isinstance(definition.preferred_executor, str)
            assert len(definition.preferred_executor) > 0
            assert isinstance(definition.fallback_executors, list)
            assert len(definition.fallback_executors) > 0
            assert isinstance(definition.risk, ActionRisk)
            assert isinstance(definition.expected_state, str)
            assert len(definition.expected_state) > 0, f"{action_type}: expected_state is empty"
            assert isinstance(definition.preconditions, list)
            assert len(definition.preconditions) > 0, f"{action_type}: preconditions is empty"
            assert isinstance(definition.permission_requirements, list)
            assert len(definition.permission_requirements) > 0, f"{action_type}: permission_requirements is empty"
            assert isinstance(definition.reversibility, bool)
            assert isinstance(definition.security_risk_notes, str)

    def test_required_args_are_subset_of_arguments(self):
        for action_type, definition in ACTION_DEFINITIONS.items():
            for arg in definition.required_args:
                assert arg in definition.arguments, \
                    f"{action_type}: required arg '{arg}' not in arguments dict"

    def test_all_risk_values_are_valid(self):
        valid_risks = {r.value for r in ActionRisk}
        for action_type, definition in ACTION_DEFINITIONS.items():
            assert definition.risk.value in valid_risks, \
                f"{action_type}: invalid risk '{definition.risk}'"

    def test_specific_navigation_actions_defined(self):
        nav_actions = [
            SAPActionType.OPEN_INTEGRATION_SUITE,
            SAPActionType.OPEN_CLOUD_INTEGRATION,
            SAPActionType.OPEN_DESIGN,
            SAPActionType.OPEN_MONITOR,
            SAPActionType.OPEN_SECURITY_MATERIAL,
            SAPActionType.OPEN_MPL,
            SAPActionType.OPEN_EVENT_MESH,
            SAPActionType.OPEN_API_MANAGEMENT,
        ]
        for action in nav_actions:
            assert action in ACTION_DEFINITIONS

    def test_specific_package_actions_defined(self):
        for action in [SAPActionType.UPDATE_PACKAGE, SAPActionType.DELETE_PACKAGE]:
            assert action in ACTION_DEFINITIONS

    def test_specific_iflow_actions_defined(self):
        for action in [
            SAPActionType.OPEN_IFLOW, SAPActionType.COPY_IFLOW, SAPActionType.SAVE_IFLOW,
            SAPActionType.UNDEPLOY_IFLOW, SAPActionType.DELETE_IFLOW,
        ]:
            assert action in ACTION_DEFINITIONS

    def test_specific_component_actions_defined(self):
        for action in [
            SAPActionType.ADD_SENDER, SAPActionType.ADD_RECEIVER,
            SAPActionType.ADD_CONTENT_MODIFIER, SAPActionType.ADD_ROUTER,
            SAPActionType.ADD_GENERAL_SPLITTER, SAPActionType.ADD_ITERATING_SPLITTER,
            SAPActionType.ADD_GATHER, SAPActionType.ADD_MULTICAST,
            SAPActionType.ADD_REQUEST_REPLY, SAPActionType.ADD_PROCESS_DIRECT,
            SAPActionType.ADD_EXCEPTION_SUBPROCESS,
        ]:
            assert action in ACTION_DEFINITIONS

    def test_specific_scripting_actions_defined(self):
        for action in [
            SAPActionType.ADD_GROOVY_SCRIPT, SAPActionType.ADD_XSLT,
            SAPActionType.ADD_MESSAGE_MAPPING,
        ]:
            assert action in ACTION_DEFINITIONS

    def test_specific_adapter_actions_defined(self):
        for action in [
            SAPActionType.CONFIGURE_HTTP, SAPActionType.CONFIGURE_SFTP,
            SAPActionType.CONFIGURE_ODATA_V2, SAPActionType.CONFIGURE_ODATA_V4,
            SAPActionType.CONFIGURE_SOAP, SAPActionType.CONFIGURE_JMS,
            SAPActionType.CONFIGURE_EVENT_MESH,
        ]:
            assert action in ACTION_DEFINITIONS

    def test_specific_monitoring_actions_defined(self):
        for action in [SAPActionType.QUERY_MPL, SAPActionType.GET_TRACE, SAPActionType.RETRY_MESSAGE]:
            assert action in ACTION_DEFINITIONS

    def test_specific_apim_actions_defined(self):
        for action in [
            SAPActionType.CREATE_API_PROVIDER, SAPActionType.CREATE_API_PROXY,
            SAPActionType.ADD_API_POLICY, SAPActionType.DEPLOY_API_PROXY,
        ]:
            assert action in ACTION_DEFINITIONS

    def test_specific_security_actions_defined(self):
        for action in [SAPActionType.UPDATE_SECURITY_MATERIAL, SAPActionType.CONFIGURE_OAUTH]:
            assert action in ACTION_DEFINITIONS

    def test_specific_testing_actions_defined(self):
        for action in [SAPActionType.RUN_TEST, SAPActionType.VERIFY_DEPLOYMENT]:
            assert action in ACTION_DEFINITIONS


class TestHighRiskActions:
    """High-risk actions must have reversibility=False and security notes."""

    def test_delete_package_is_high_risk(self):
        definition = get_action_definition(SAPActionType.DELETE_PACKAGE)
        assert definition.risk == ActionRisk.HIGH
        assert definition.reversibility is False

    def test_create_security_material_is_high_risk(self):
        definition = get_action_definition(SAPActionType.CREATE_SECURITY_MATERIAL)
        assert definition.risk == ActionRisk.HIGH
        assert definition.reversibility is False

    def test_high_risk_actions_have_security_notes(self):
        high_risk_actions = [
            a for a, d in ACTION_DEFINITIONS.items() if d.risk == ActionRisk.HIGH
        ]
        assert len(high_risk_actions) > 0
        for action in high_risk_actions:
            definition = ACTION_DEFINITIONS[action]
            assert len(definition.security_risk_notes) > 0


class TestActionDefinitionAccessors:
    """Tests for get_action_definition and validate_action_arguments."""

    def test_get_action_definition_exists(self):
        definition = get_action_definition(SAPActionType.CREATE_PACKAGE)
        assert definition is not None
        assert definition.action_type == SAPActionType.CREATE_PACKAGE

    def test_get_action_definition_any_registered(self):
        # All action types are now registered — this should never return None
        for action_type in SAPActionType:
            result = get_action_definition(action_type)
            assert result is not None, f"{action_type} not registered"

    def test_create_package_definition(self):
        definition = get_action_definition(SAPActionType.CREATE_PACKAGE)
        assert "name" in definition.required_args
        assert definition.risk == ActionRisk.MEDIUM

    def test_deploy_iflow_definition(self):
        definition = get_action_definition(SAPActionType.DEPLOY_IFLOW)
        assert "package_id" in definition.required_args
        assert "iflow_id" in definition.required_args

    def test_validate_action_args_missing(self):
        errors = validate_action_arguments(SAPActionType.CREATE_PACKAGE, {})
        assert any("name" in e for e in errors)

    def test_validate_action_args_present(self):
        errors = validate_action_arguments(SAPActionType.CREATE_PACKAGE, {"name": "TEST"})
        assert len(errors) == 0

    def test_validate_action_args_unknown_type(self):
        errors = validate_action_arguments("not_a_real_type", {})  # type: ignore[arg-type]
        assert len(errors) > 0
        assert "Unknown action type" in errors[0]
