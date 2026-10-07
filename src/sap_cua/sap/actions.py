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


# Action registry — every SAPActionType gets a full definition.
ACTION_DEFINITIONS: dict[SAPActionType, ActionDefinition] = {
    # ── Navigation ──────────────────────────────────────────────────────────
    SAPActionType.OPEN_INTEGRATION_SUITE: ActionDefinition(
        action_type=SAPActionType.OPEN_INTEGRATION_SUITE,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="INTEGRATION_SUITE_OPEN",
        preconditions=["User is authenticated", "Tenant is reachable"],
        permission_requirements=["IntegrationSuiteViewer"],
    ),
    SAPActionType.OPEN_CLOUD_INTEGRATION: ActionDefinition(
        action_type=SAPActionType.OPEN_CLOUD_INTEGRATION,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="CLOUD_INTEGRATION_OPEN",
        preconditions=["Integration Suite is accessible"],
        permission_requirements=["IntegrationSuiteViewer"],
    ),
    SAPActionType.OPEN_DESIGN: ActionDefinition(
        action_type=SAPActionType.OPEN_DESIGN,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="DESIGN_VIEW_OPEN",
        preconditions=["Cloud Integration is open"],
        permission_requirements=["IntegrationFlowDesigner"],
    ),
    SAPActionType.OPEN_MONITOR: ActionDefinition(
        action_type=SAPActionType.OPEN_MONITOR,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="MONITOR_VIEW_OPEN",
        preconditions=["Cloud Integration is open"],
        permission_requirements=["MessageMonitoringViewer"],
    ),
    SAPActionType.OPEN_SECURITY_MATERIAL: ActionDefinition(
        action_type=SAPActionType.OPEN_SECURITY_MATERIAL,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="SECURITY_MATERIAL_VIEW_OPEN",
        preconditions=["Integration Suite is open"],
        permission_requirements=["SecurityMaterialViewer"],
    ),
    SAPActionType.OPEN_MPL: ActionDefinition(
        action_type=SAPActionType.OPEN_MPL,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="MPL_VIEW_OPEN",
        preconditions=["Monitor is open"],
        permission_requirements=["MessageMonitoringViewer"],
    ),
    SAPActionType.OPEN_EVENT_MESH: ActionDefinition(
        action_type=SAPActionType.OPEN_EVENT_MESH,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="EVENT_MESH_OPEN",
        preconditions=["Integration Suite is open"],
        permission_requirements=["EventMeshViewer"],
    ),
    SAPActionType.OPEN_API_MANAGEMENT: ActionDefinition(
        action_type=SAPActionType.OPEN_API_MANAGEMENT,
        arguments={"url": str},
        required_args=["url"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="API_MANAGEMENT_OPEN",
        preconditions=["Integration Suite is open"],
        permission_requirements=["APIManagementViewer"],
    ),

    # ── Package Management ──────────────────────────────────────────────────
    SAPActionType.CREATE_PACKAGE: ActionDefinition(
        action_type=SAPActionType.CREATE_PACKAGE,
        arguments={"name": str, "description": str},
        required_args=["name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="PACKAGE_CREATED",
        preconditions=["Design view is open"],
        permission_requirements=["PackageDeveloper"],
    ),
    SAPActionType.UPDATE_PACKAGE: ActionDefinition(
        action_type=SAPActionType.UPDATE_PACKAGE,
        arguments={"package_id": str, "name": str, "description": str},
        required_args=["package_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="PACKAGE_UPDATED",
        preconditions=["Package exists", "No active deployments blocking update"],
        permission_requirements=["PackageDeveloper"],
        security_risk_notes="Changing package name may break references in deployed artifacts.",
    ),
    SAPActionType.DELETE_PACKAGE: ActionDefinition(
        action_type=SAPActionType.DELETE_PACKAGE,
        arguments={"package_id": str},
        required_args=["package_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="PACKAGE_DELETED",
        preconditions=["Package exists", "Package has no iFlows or all iFlows are undeployed"],
        permission_requirements=["PackageAdministrator"],
        reversibility=False,
        security_risk_notes="Irreversible. Deletion removes all iFlows and configurations permanently.",
    ),

    # ── iFlow Management ────────────────────────────────────────────────────
    SAPActionType.CREATE_IFLOW: ActionDefinition(
        action_type=SAPActionType.CREATE_IFLOW,
        arguments={"package_id": str, "name": str, "template": str},
        required_args=["package_id", "name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="IFLOW_CREATED",
        preconditions=["Package exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.OPEN_IFLOW: ActionDefinition(
        action_type=SAPActionType.OPEN_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="playwright",
        fallback_executors=["gui"],
        risk=ActionRisk.LOW,
        expected_state="IFLOW_EDITOR_OPEN",
        preconditions=["iFlow exists", "Design view is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.COPY_IFLOW: ActionDefinition(
        action_type=SAPActionType.COPY_IFLOW,
        arguments={"package_id": str, "iflow_id": str, "new_name": str, "target_package_id": str},
        required_args=["package_id", "iflow_id", "new_name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="IFLOW_COPIED",
        preconditions=["Source iFlow exists", "Target package exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
        security_risk_notes="Copied iFlow inherits sender/receiver configurations; review credentials before deployment.",
    ),
    SAPActionType.SAVE_IFLOW: ActionDefinition(
        action_type=SAPActionType.SAVE_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.LOW,
        expected_state="IFLOW_SAVED",
        preconditions=["iFlow editor is open", "iFlow exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.DEPLOY_IFLOW: ActionDefinition(
        action_type=SAPActionType.DEPLOY_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="DEPLOYED",
        preconditions=["iFlow exists", "iFlow is not already deployed"],
        permission_requirements=["IntegrationFlowDeployer"],
        security_risk_notes="Deployment activates the integration in the tenant runtime.",
    ),
    SAPActionType.UNDEPLOY_IFLOW: ActionDefinition(
        action_type=SAPActionType.UNDEPLOY_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="UNDEPLOYED",
        preconditions=["iFlow is currently deployed"],
        permission_requirements=["IntegrationFlowDeployer"],
        security_risk_notes="Undeplying stops message processing. Dependent systems may fail.",
        reversibility=False,
    ),
    SAPActionType.DELETE_IFLOW: ActionDefinition(
        action_type=SAPActionType.DELETE_IFLOW,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="IFLOW_DELETED",
        preconditions=["iFlow exists", "iFlow is undeployed"],
        permission_requirements=["IntegrationFlowAdministrator"],
        reversibility=False,
        security_risk_notes="Irreversible. All configuration and message history is removed.",
    ),

    # ── Components ──────────────────────────────────────────────────────────
    SAPActionType.ADD_SENDER: ActionDefinition(
        action_type=SAPActionType.ADD_SENDER,
        arguments={"package_id": str, "iflow_id": str, "adapter": str, "config": dict},
        required_args=["package_id", "iflow_id", "adapter"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="SENDER_ADDED",
        preconditions=["iFlow editor is open", "iFlow exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_RECEIVER: ActionDefinition(
        action_type=SAPActionType.ADD_RECEIVER,
        arguments={"package_id": str, "iflow_id": str, "adapter": str, "config": dict},
        required_args=["package_id", "iflow_id", "adapter"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="RECEIVER_ADDED",
        preconditions=["iFlow editor is open", "iFlow exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_CONTENT_MODIFIER: ActionDefinition(
        action_type=SAPActionType.ADD_CONTENT_MODIFIER,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="CONTENT_MODIFIER_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_ROUTER: ActionDefinition(
        action_type=SAPActionType.ADD_ROUTER,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="ROUTER_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_GENERAL_SPLITTER: ActionDefinition(
        action_type=SAPActionType.ADD_GENERAL_SPLITTER,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="GENERAL_SPLITTER_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_ITERATING_SPLITTER: ActionDefinition(
        action_type=SAPActionType.ADD_ITERATING_SPLITTER,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="ITERATING_SPLITTER_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_GATHER: ActionDefinition(
        action_type=SAPActionType.ADD_GATHER,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="GATHER_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_MULTICAST: ActionDefinition(
        action_type=SAPActionType.ADD_MULTICAST,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="MULTICAST_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_REQUEST_REPLY: ActionDefinition(
        action_type=SAPActionType.ADD_REQUEST_REPLY,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="REQUEST_REPLY_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_PROCESS_DIRECT: ActionDefinition(
        action_type=SAPActionType.ADD_PROCESS_DIRECT,
        arguments={"package_id": str, "iflow_id": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="PROCESS_DIRECT_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.ADD_EXCEPTION_SUBPROCESS: ActionDefinition(
        action_type=SAPActionType.ADD_EXCEPTION_SUBPROCESS,
        arguments={"package_id": str, "iflow_id": str, "trigger_type": str, "config": dict},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="EXCEPTION_SUBPROCESS_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),

    # ── Scripting / Mapping ─────────────────────────────────────────────────
    SAPActionType.ADD_GROOVY_SCRIPT: ActionDefinition(
        action_type=SAPActionType.ADD_GROOVY_SCRIPT,
        arguments={"package_id": str, "iflow_id": str, "script_content": str, "config": dict},
        required_args=["package_id", "iflow_id", "script_content"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="GROOVY_SCRIPT_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
        security_risk_notes="Groovy scripts run in the integration runtime. Malicious scripts can exfiltrate data.",
    ),
    SAPActionType.ADD_XSLT: ActionDefinition(
        action_type=SAPActionType.ADD_XSLT,
        arguments={"package_id": str, "iflow_id": str, "xslt_content": str, "config": dict},
        required_args=["package_id", "iflow_id", "xslt_content"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="XSLT_MAPPING_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
        security_risk_notes="XSLT transformations can be used for XXE injection if external entities are resolved.",
    ),
    SAPActionType.ADD_MESSAGE_MAPPING: ActionDefinition(
        action_type=SAPActionType.ADD_MESSAGE_MAPPING,
        arguments={"package_id": str, "iflow_id": str, "source_schema": str, "target_schema": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="MESSAGE_MAPPING_ADDED",
        preconditions=["iFlow editor is open"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),

    # ── Adapters ────────────────────────────────────────────────────────────
    SAPActionType.CONFIGURE_HTTPS: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_HTTPS,
        arguments={"address": str, "path": str, "port": int, "credential_name": str},
        required_args=["address"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="HTTPS_CONFIGURED",
        preconditions=["Sender/receiver component exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.CONFIGURE_HTTP: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_HTTP,
        arguments={"address": str, "path": str, "port": int, "method": str},
        required_args=["address"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="HTTP_CONFIGURED",
        preconditions=["Sender/receiver component exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.CONFIGURE_SFTP: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_SFTP,
        arguments={"host": str, "port": int, "username": str, "credential_name": str, "directory": str},
        required_args=["host", "credential_name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="SFTP_CONFIGURED",
        preconditions=["Sender/receiver component exists", "SFTP host is reachable"],
        permission_requirements=["IntegrationFlowDeveloper"],
        security_risk_notes="SFTP credentials must be stored in Security Material; never hardcode secrets.",
    ),
    SAPActionType.CONFIGURE_ODATA_V2: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_ODATA_V2,
        arguments={"service_url": str, "credential_name": str, "entity_set": str},
        required_args=["service_url"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="ODATA_V2_CONFIGURED",
        preconditions=["Sender/receiver component exists", "OData service is accessible"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.CONFIGURE_ODATA_V4: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_ODATA_V4,
        arguments={"service_url": str, "credential_name": str, "entity_set": str},
        required_args=["service_url"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="ODATA_V4_CONFIGURED",
        preconditions=["Sender/receiver component exists", "OData V4 service is accessible"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.CONFIGURE_SOAP: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_SOAP,
        arguments={"wsdl_url": str, "operation": str, "credential_name": str},
        required_args=["wsdl_url", "operation"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.LOW,
        expected_state="SOAP_CONFIGURED",
        preconditions=["Sender/receiver component exists", "WSDL is accessible"],
        permission_requirements=["IntegrationFlowDeveloper"],
    ),
    SAPActionType.CONFIGURE_JMS: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_JMS,
        arguments={"queue_name": str, "connection_factory": str, "credential_name": str},
        required_args=["queue_name", "connection_factory"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="JMS_CONFIGURED",
        preconditions=["JMS provider is configured", "Queue exists"],
        permission_requirements=["IntegrationFlowDeveloper"],
        security_risk_notes="JMS queue names and credentials must be validated to prevent injection.",
    ),
    SAPActionType.CONFIGURE_EVENT_MESH: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_EVENT_MESH,
        arguments={"topic_name": str, "credential_name": str},
        required_args=["topic_name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright", "gui"],
        risk=ActionRisk.MEDIUM,
        expected_state="EVENT_MESH_CONFIGURED",
        preconditions=["Event Mesh instance exists", "Topic exists or can be created"],
        permission_requirements=["IntegrationFlowDeveloper", "EventMeshAdministrator"],
    ),

    # ── Monitoring ──────────────────────────────────────────────────────────
    SAPActionType.QUERY_MPL: ActionDefinition(
        action_type=SAPActionType.QUERY_MPL,
        arguments={"iflow_key": str, "status": str, "time_range": str},
        required_args=[],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.LOW,
        expected_state="MPL_QUERIED",
        preconditions=["iFlow is deployed"],
        permission_requirements=["MessageMonitoringViewer"],
    ),
    SAPActionType.GET_TRACE: ActionDefinition(
        action_type=SAPActionType.GET_TRACE,
        arguments={"message_id": str, "iflow_key": str},
        required_args=["message_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.LOW,
        expected_state="TRACE_RETRIEVED",
        preconditions=["Message exists in MPL"],
        permission_requirements=["MessageMonitoringViewer"],
    ),
    SAPActionType.RETRY_MESSAGE: ActionDefinition(
        action_type=SAPActionType.RETRY_MESSAGE,
        arguments={"message_id": str, "iflow_key": str},
        required_args=["message_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="MESSAGE_RETRIED",
        preconditions=["Message status is FAILED or ERROR"],
        permission_requirements=["MessageMonitoringOperator"],
        security_risk_notes="Retrying failed messages may cause duplicate processing if the original succeeded after all.",
    ),

    # ── API Management ──────────────────────────────────────────────────────
    SAPActionType.CREATE_API_PROVIDER: ActionDefinition(
        action_type=SAPActionType.CREATE_API_PROVIDER,
        arguments={"name": str, "service_url": str, "credential_name": str, "api_type": str},
        required_args=["name", "service_url"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="API_PROVIDER_CREATED",
        preconditions=["API Management is accessible"],
        permission_requirements=["APIDeveloper"],
    ),
    SAPActionType.CREATE_API_PROXY: ActionDefinition(
        action_type=SAPActionType.CREATE_API_PROXY,
        arguments={"name": str, "provider_id": str, "path": str},
        required_args=["name", "provider_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="API_PROXY_CREATED",
        preconditions=["API Provider exists"],
        permission_requirements=["APIDeveloper"],
    ),
    SAPActionType.ADD_API_POLICY: ActionDefinition(
        action_type=SAPActionType.ADD_API_POLICY,
        arguments={"proxy_name": str, "policy_type": str, "config": dict},
        required_args=["proxy_name", "policy_type"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.MEDIUM,
        expected_state="API_POLICY_ADDED",
        preconditions=["API Proxy exists", "Policy type is supported"],
        permission_requirements=["APIDeveloper"],
        security_risk_notes="Policies such as OAuth or spike-arrest directly affect API security posture.",
    ),
    SAPActionType.DEPLOY_API_PROXY: ActionDefinition(
        action_type=SAPActionType.DEPLOY_API_PROXY,
        arguments={"proxy_name": str, "environment": str},
        required_args=["proxy_name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="API_PROXY_DEPLOYED",
        preconditions=["API Proxy exists", "Proxy has at least one policy"],
        permission_requirements=["APIOperator"],
        security_risk_notes="Deploying a proxy exposes the API to external consumers; review policies before deploying.",
    ),

    # ── Security ────────────────────────────────────────────────────────────
    SAPActionType.CREATE_SECURITY_MATERIAL: ActionDefinition(
        action_type=SAPActionType.CREATE_SECURITY_MATERIAL,
        arguments={"type": str, "name": str, "config": dict},
        required_args=["type", "name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="SECURITY_MATERIAL_CREATED",
        preconditions=["Security Material view is open"],
        permission_requirements=["SecurityMaterialAdministrator"],
        reversibility=False,
        security_risk_notes="Credential material is sensitive; creation should follow least-privilege and audit logging.",
    ),
    SAPActionType.UPDATE_SECURITY_MATERIAL: ActionDefinition(
        action_type=SAPActionType.UPDATE_SECURITY_MATERIAL,
        arguments={"name": str, "type": str, "config": dict},
        required_args=["name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="SECURITY_MATERIAL_UPDATED",
        preconditions=["Security Material exists"],
        permission_requirements=["SecurityMaterialAdministrator"],
        security_risk_notes="Updating credentials affects all integrations that reference the material.",
    ),
    SAPActionType.CONFIGURE_OAUTH: ActionDefinition(
        action_type=SAPActionType.CONFIGURE_OAUTH,
        arguments={"client_id": str, "client_secret": str, "token_url": str, "scope": str, "credential_name": str},
        required_args=["client_id", "token_url", "credential_name"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.HIGH,
        expected_state="OAUTH_CONFIGURED",
        preconditions=["Security Material exists for OAuth client credentials"],
        permission_requirements=["SecurityMaterialAdministrator"],
        security_risk_notes="OAuth client secrets must never be logged or returned in plain text.",
    ),

    # ── Testing / Verification ──────────────────────────────────────────────
    SAPActionType.RUN_TEST: ActionDefinition(
        action_type=SAPActionType.RUN_TEST,
        arguments={"package_id": str, "iflow_id": str, "test_payload": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.LOW,
        expected_state="TEST_COMPLETED",
        preconditions=["iFlow is deployed", "Test runner is available"],
        permission_requirements=["IntegrationFlowTester"],
    ),
    SAPActionType.VERIFY_DEPLOYMENT: ActionDefinition(
        action_type=SAPActionType.VERIFY_DEPLOYMENT,
        arguments={"package_id": str, "iflow_id": str},
        required_args=["package_id", "iflow_id"],
        preferred_executor="sap_api",
        fallback_executors=["playwright"],
        risk=ActionRisk.LOW,
        expected_state="DEPLOYMENT_VERIFIED",
        preconditions=["iFlow is deployed", "Health endpoint is reachable"],
        permission_requirements=["IntegrationFlowDeployer"],
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

    for arg, value in arguments.items():
        expected = definition.arguments.get(arg)
        if expected is not None and not isinstance(value, expected):
            errors.append(f"Argument {arg} must be {expected.__name__}")
        elif arg in definition.required_args and isinstance(value, str) and not value.strip():
            errors.append(f"Required argument {arg} cannot be empty")

    return errors
