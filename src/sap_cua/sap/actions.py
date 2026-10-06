"""SAP Semantic Action Language — typed action definitions for Integration Suite operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ActionRisk(str, Enum):
    """Risk classification for actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SAPActionType(str, Enum):
    """All supported SAP semantic actions."""
    # Navigation
    OPEN_INTEGRATION_SUITE = "OPEN_INTEGRATION_SUITE"
    OPEN_CLOUD_INTEGRATION = "OPEN_CLOUD_INTEGRATION"
    OPEN_DESIGN = "OPEN_DESIGN"
    OPEN_MONITOR = "OPEN_MONITOR"
    OPEN_SECURITY_MATERIAL = "OPEN_SECURITY_MATERIAL"
    NAV_OPEN_MPL = "OPEN_MPL"
    OPEN_EVENT_MESH = "OPEN_EVENT_MESH"
    OPEN_API_MANAGEMENT = "OPEN_API_MANAGEMENT"

    # Package Management
    CREATE_PACKAGE = "CREATE_PACKAGE"
    UPDATE_PACKAGE = "UPDATE_PACKAGE"
    DELETE_PACKAGE = "DELETE_PACKAGE"

    # iFlow Management
    CREATE_IFLOW = "CREATE_IFLOW"
    OPEN_IFLOW = "OPEN_IFLOW"
    COPY_IFLOW = "COPY_IFLOW"
    SAVE_IFLOW = "SAVE_IFLOW"
    DEPLOY_IFLOW = "DEPLOY_IFLOW"
    UNDEPLOY_IFLOW = "UNDEPLOY_IFLOW"
    DELETE_IFLOW = "DELETE_IFLOW"

    # Components
    ADD_SENDER = "ADD_SENDER"
    ADD_RECEIVER = "ADD_RECEIVER"
    ADD_CONTENT_MODIFIER = "ADD_CONTENT_MODIFIER"
    ADD_ROUTER = "ADD_ROUTER"
    ADD_GENERAL_SPLITTER = "ADD_GENERAL_SPLITTER"
    ADD_ITERATING_SPLITTER = "ADD_ITERATING_SPLITTER"
    ADD_GATHER = "ADD_GATHER"
    ADD_MULTICAST = "ADD_MULTICAST"
    ADD_REQUEST_REPLY = "ADD_REQUEST_REPLY"
    ADD_PROCESS_DIRECT = "ADD_PROCESS_DIRECT"
    ADD_EXCEPTION_SUBPROCESS = "ADD_EXCEPTION_SUBPROCESS"

    # Scripting/Mapping
    ADD_GROOVY_SCRIPT = "ADD_GROOVY_SCRIPT"
    ADD_XSLT = "ADD_XSLT"
    ADD_MESSAGE_MAPPING = "ADD_MESSAGE_MAPPING"

    # Adapters
    CONFIGURE_HTTPS = "CONFIGURE_HTTPS"
    CONFIGURE_HTTP = "CONFIGURE_HTTP"
    CONFIGURE_SFTP = "CONFIGURE_SFTP"
    CONFIGURE_ODATA_V2 = "CONFIGURE_ODATA_V2"
    CONFIGURE_ODATA_V4 = "CONFIGURE_ODATA_V4"
    CONFIGURE_SOAP = "CONFIGURE_SOAP"
    CONFIGURE_JMS = "CONFIGURE_JMS"
    CONFIGURE_EVENT_MESH = "CONFIGURE_EVENT_MESH"

    # Monitoring
    QUERY_MPL = "QUERY_MPL"
    OPEN_MPL = "OPEN_MPL"
    GET_TRACE = "GET_TRACE"
    RETRY_MESSAGE = "RETRY_MESSAGE"

    # API Management
    CREATE_API_PROVIDER = "CREATE_API_PROVIDER"
    CREATE_API_PROXY = "CREATE_API_PROXY"
    ADD_API_POLICY = "ADD_API_POLICY"
    DEPLOY_API_PROXY = "DEPLOY_API_PROXY"

    # Security
    CREATE_SECURITY_MATERIAL = "CREATE_SECURITY_MATERIAL"
    UPDATE_SECURITY_MATERIAL = "UPDATE_SECURITY_MATERIAL"
    CONFIGURE_OAUTH = "CONFIGURE_OAUTH"

    # Testing/Verification
    RUN_TEST = "RUN_TEST"
    VERIFY_DEPLOYMENT = "VERIFY_DEPLOYMENT"


@dataclass
class ActionDefinition:
    """Definition of a SAP semantic action."""
    action_type: SAPActionType
    arguments: dict[str, type] = field(default_factory=dict)
    required_args: list[str] = field(default_factory=list)
    preferred_executor: str = "sap_api"
    fallback_executors: list[str] = field(default_factory=lambda: ["playwright", "gui"])
    risk: ActionRisk = ActionRisk.LOW
    expected_state: str = ""
    preconditions: list[str] = field(default_factory=list)
    permission_requirements: list[str] = field(default_factory=list)
    reversibility: bool = True
    security_risk_notes: str = ""


# Action registry
ACTION_DEFINITIONS: dict[SAPActionType, ActionDefinition] = {
    SAPActionType.CREATE_PACKAGE: ActionDefinition(
        action_type=SAPActionType.CREATE_PACKAGE,
        arguments={"name": str, "description": str},
        required_args=["name"],
        risk=ActionRisk.MEDIUM,
        expected_state="PACKAGE_CREATED",
    ),
    SAPActionType.CREATE_IFLOW: ActionDefinition(
        action_type=SAPActionType.CREATE_IFLOW,
        arguments={"package_id": str, "name": str, "template": str},
        required_args=["package_id", "name"],
        risk=ActionRisk.MEDIUM,
        expected_state="IFLOW_CREATED",
    ),
    SAPActionType.DEPLOY_IFLOW: ActionDefinition(
        action_type=SAPActionType.DEPLOY_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        risk=ActionRisk.MEDIUM,
        expected_state="DEPLOYED",
    ),
    SAPActionType.CONFIGURE_HTTPS: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_HTTPS,
        arguments={"address": str, "path": str, "port": int, "credential_name": str},
        required_args=["address"],
        risk=ActionRisk.LOW,
        expected_state="HTTPS_CONFIGURED",
    ),
    SAPActionType.ADD_EXCEPTION_SUBPROCESS: ActionDefinition(
        action_type=SAPActionType.ADD_EXCEPTION_SUBPROCESS,
        arguments={"trigger_type": str},
        required_args=[],
        risk=ActionRisk.LOW,
        expected_state="EXCEPTION_SUBPROCESS_ADDED",
    ),
    SAPActionType.CREATE_SECURITY_MATERIAL: ActionDefinition(
        action_type=SAPActionType.CREATE_SECURITY_MATERIAL,
        arguments={"type": str, "name": str},
        required_args=["type", "name"],
        risk=ActionRisk.HIGH,
        expected_state="SECURITY_MATERIAL_CREATED",
        reversibility=False,
    ),
    SAPActionType.DELETE_PACKAGE: ActionDefinition(
        action_type=SAPActionType.DELETE_PACKAGE,
        arguments={"package_id": str},
        required_args=["package_id"],
        risk=ActionRisk.HIGH,
        expected_state="PACKAGE_DELETED",
        reversibility=False,
    ),
}


def get_action_definition(action_type: SAPActionType) -> ActionDefinition | None:
    """Get the definition for a given action type."""
    return ACTION_DEFINITIONS.get(action_type)


def validate_action_arguments(action_type: SAPActionType, arguments: dict[str, Any]) -> list[str]:
    """Validate arguments against action definition. Returns list of errors."""
    definition = get_action_definition(action_type)
    if definition is None:
        return [f"Unknown action type: {action_type}"]

    errors: list[str] = []
    for arg in definition.required_args:
        if arg not in arguments:
            errors.append(f"Missing required argument: {arg}")

    return errors
