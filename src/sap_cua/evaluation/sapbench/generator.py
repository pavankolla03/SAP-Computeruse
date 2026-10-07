"""SAPBench task generator and schemas for SAP-specific evaluation.

Expanded to 100+ templates across 5 difficulty levels.
"""

from __future__ import annotations

import random
import string
from typing import Any

from sap_cua.sap.actions import SAPActionType, get_action_definition
from sap_cua.types import TaskDefinition


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _r(n: int) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _fill(s: str) -> str:
    return (
        s.replace("{rand4}", _r(4))
        .replace("{rand5}", _r(5))
        .replace("{rand6}", _r(6))
        .replace("{rand8}", _r(8))
    )


def _ver(task_id: str, tid: str) -> dict[str, Any]:
    return {"type": "mpl_success", "task_id": task_id, "iflow_id": tid}


def _clean(tid: str, pid: str) -> dict[str, Any]:
    return {"type": "delete_iflow", "package_id": pid, "iflow_id": tid}


# ─── Template Builder ──────────────────────────────────────────────────────────

def _nav(inst: str, mod: str = "Cloud Integration", page: str = "", variables: dict | None = None) -> dict[str, Any]:
    result = {
        "instruction": inst,
        "module": mod,
        "difficulty": 1,
        "category": "navigation",
        "verify": {"type": "page_visible", "page": page or inst.split()[-1].lower()},
    }
    if variables:
        result["variables"] = variables
    return result


def _cfg(inst: str, actions: list[dict], verify: dict, setup: dict | None = None,
         cleanup: dict | None = None, mod: str = "Cloud Integration", diff: int = 2,
         variables: dict | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "instruction": inst,
        "module": mod,
        "difficulty": diff,
        "category": "configuration",
        "actions": actions,
        "verify": verify,
    }
    if setup:
        result["setup"] = setup
    if cleanup:
        result["cleanup"] = cleanup
    if variables:
        result["variables"] = variables
    return result


def _int(inst: str, actions: list[dict], verify: dict,
         setup: dict | None = None, cleanup: dict | None = None,
         variables: dict | None = None) -> dict[str, Any]:
    return _cfg(inst, actions, verify, setup=setup, cleanup=cleanup,
                diff=3, variables=variables)


def _dbg(inst: str, actions: list[dict], verify: dict,
         variables: dict | None = None) -> dict[str, Any]:
    return _cfg(inst, actions, verify, diff=4, mod="Cloud Integration", variables=variables)


def _arch(inst: str, actions: list[dict], verify: dict,
          setup: dict | None = None, cleanup: dict | None = None,
          variables: dict | None = None) -> dict[str, Any]:
    return _cfg(inst, actions, verify, setup=setup, cleanup=cleanup,
                diff=5, variables=variables)


# ─── 100+ Task Templates ───────────────────────────────────────────────────────

TASK_TEMPLATES: dict[str, dict[str, Any]] = {}

# ── Level 1: Navigation (15 tasks) ────────────────────────────────────────────

TASK_TEMPLATES["nav_open_suite"] = _nav(
    "Open the SAP Integration Suite.", page="integration_suite")
TASK_TEMPLATES["nav_open_ci"] = _nav(
    "Navigate to Cloud Integration.", page="cloud_integration")
TASK_TEMPLATES["nav_open_design"] = _nav(
    "Open the Design view.", page="design")
TASK_TEMPLATES["nav_open_monitor"] = _nav(
    "Open the Monitoring dashboard.", page="monitor")
TASK_TEMPLATES["nav_open_mpl"] = _nav(
    "Open Message Processing Logs (MPL).", page="mpl")
TASK_TEMPLATES["nav_open_security"] = _nav(
    "Navigate to Security Material.", page="security_material")
TASK_TEMPLATES["nav_open_api_mgmt"] = _nav(
    "Open API Management.", mod="API Management", page="api_management")
TASK_TEMPLATES["nav_open_event_mesh"] = _nav(
    "Open Event Mesh.", mod="Event Mesh", page="event_mesh")
TASK_TEMPLATES["nav_open_deploy"] = _nav(
    "Open the Deploy view.", page="deploy")
TASK_TEMPLATES["nav_open_connectivity"] = _nav(
    "Open the Connectivity view.", page="connectivity")
TASK_TEMPLATES["nav_open_credentials"] = _nav(
    "Open the Credentials view.", page="credentials")
TASK_TEMPLATES["nav_open_adapter_config"] = _nav(
    "Open the Adapter Configuration.", page="adapter_config")
TASK_TEMPLATES["nav_find_package"] = _nav(
    "Locate the package named {package_name} in Integration Packages.",
    variables={"package_name": "SALES"}, page="packages")
TASK_TEMPLATES["nav_open_iflow"] = _nav(
    "Open the iFlow {iflow_name} from package {package_name}.",
    variables={"package_name": "SALES", "iflow_name": "SalesOrderSync"})
TASK_TEMPLATES["nav_open_iflow_editor"] = _nav(
    "Open the iFlow editor for {iflow_name}.",
    variables={"iflow_name": "SalesOrderSync"}, page="iflow_editor")

# ── Level 2: Basic Configuration (20 tasks) ──────────────────────────────────

pid = "TEST_PKG_{rand6}"
tid = "TestFlow_{rand4}"

TASK_TEMPLATES["create_package"] = _cfg(
    "Create a package named {package_name} with description 'Test package created by SAP-CUA'.",
    [{"intent": "CREATE_PACKAGE"}],
    {"type": "package_exists", "package_id": "{package_name}"},
    variables={"package_name": "CUA_PKG_{rand6}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["create_iflow"] = _cfg(
    "Create an iFlow named {iflow_name} in package {package_name}.",
    [{"intent": "CREATE_IFLOW"}],
    {"type": "iflow_exists", "package_id": "{package_name}", "iflow_id": "{iflow_name}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_iflow", "package_id": "{package_name}", "iflow_id": "{iflow_name}"},
    variables={"package_name": "CUA_PKG_{rand6}", "iflow_name": "CUA_IFLOW_{rand4}"},
)

TASK_TEMPLATES["copy_iflow"] = _cfg(
    "Copy the iFlow {iflow_name} in package {package_name}.",
    [{"intent": "COPY_IFLOW"}],
    {"type": "iflow_exists"},
    variables={"iflow_name": "SalesOrderSync", "package_name": "SALES"},
)

TASK_TEMPLATES["save_iflow"] = _cfg(
    "Save the iFlow {iflow_name} after making a change.",
    [{"intent": "SAVE_IFLOW"}],
    {"type": "iflow_saved"},
    variables={"iflow_name": "SalesOrderSync", "package_name": "SALES"},
)

TASK_TEMPLATES["deploy_iflow"] = _cfg(
    "Deploy iFlow {iflow_name} in package {package_name}.",
    [{"intent": "DEPLOY_IFLOW"}],
    {"type": "iflow_deployed"},
    setup={"type": "create_iflow", "package_id": "{package_name}", "name": "{iflow_name}"},
    cleanup={"type": "delete_iflow"},
    variables={"package_name": "CUA_PKG_{rand6}", "iflow_name": "CUA_IFLOW_{rand4}"},
)

TASK_TEMPLATES["undeploy_iflow"] = _cfg(
    "Undeploy iFlow {iflow_name} from package {package_name}.",
    [{"intent": "UNDEPLOY_IFLOW"}],
    {"type": "iflow_undeployed"},
    variables={"iflow_name": "SalesOrderSync", "package_name": "SALES"},
)

TASK_TEMPLATES["add_https_sender"] = _cfg(
    "Add an HTTPS sender to iFlow {iflow_name} in package {package_name}.",
    [{"intent": "ADD_SENDER", "adapter": "HTTPS"}],
    {"type": "sender_adapter", "adapter": "HTTPS"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_http_receiver"] = _cfg(
    "Add an HTTP receiver to iFlow {iflow_name} in package {package_name}.",
    [{"intent": "ADD_RECEIVER", "adapter": "HTTP"}],
    {"type": "receiver_adapter", "adapter": "HTTP"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_odata_v2_receiver"] = _cfg(
    "Add an OData V2 receiver to iFlow {iflow_name}.",
    [{"intent": "ADD_RECEIVER", "adapter": "OData V2"}],
    {"type": "receiver_adapter", "adapter": "OData V2"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_odata_v4_receiver"] = _cfg(
    "Add an OData V4 receiver to iFlow {iflow_name}.",
    [{"intent": "ADD_RECEIVER", "adapter": "OData V4"}],
    {"type": "receiver_adapter", "adapter": "OData V4"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_sftp_sender"] = _cfg(
    "Add an SFTP sender to iFlow {iflow_name}.",
    [{"intent": "ADD_SENDER", "adapter": "SFTP"}],
    {"type": "sender_adapter", "adapter": "SFTP"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_soap_sender"] = _cfg(
    "Add a SOAP sender to iFlow {iflow_name}.",
    [{"intent": "ADD_SENDER", "adapter": "SOAP"}],
    {"type": "sender_adapter", "adapter": "SOAP"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_jms_receiver"] = _cfg(
    "Add a JMS receiver to iFlow {iflow_name}.",
    [{"intent": "ADD_RECEIVER", "adapter": "JMS"}],
    {"type": "receiver_adapter", "adapter": "JMS"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_content_modifier"] = _cfg(
    "Add a Content Modifier to iFlow {iflow_name}.",
    [{"intent": "ADD_CONTENT_MODIFIER"}],
    {"type": "component_present", "component": "ContentModifier"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_groovy_script"] = _cfg(
    "Add a Groovy Script step to iFlow {iflow_name}.",
    [{"intent": "ADD_GROOVY_SCRIPT"}],
    {"type": "component_present", "component": "GroovyScript"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_message_mapping"] = _cfg(
    "Add a Message Mapping to iFlow {iflow_name}.",
    [{"intent": "ADD_MESSAGE_MAPPING"}],
    {"type": "component_present", "component": "MessageMapping"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["create_security_material"] = _cfg(
    "Create a User Credentials security material named {cred_name}.",
    [{"intent": "CREATE_SECURITY_MATERIAL"}],
    {"type": "security_material_exists", "name": "{cred_name}"},
    variables={"cred_name": "CUA_CRED_{rand6}"},
    mod="Security Material",
    cleanup={"type": "delete_security_material", "name": "{cred_name}"},
)

TASK_TEMPLATES["configure_oauth"] = _cfg(
    "Configure OAuth2 client credentials for iFlow {iflow_name}.",
    [{"intent": "CONFIGURE_OAUTH"}],
    {"type": "oauth_configured"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_router"] = _cfg(
    "Add a Router to iFlow {iflow_name} to route messages based on payload.",
    [{"intent": "ADD_ROUTER"}],
    {"type": "component_present", "component": "Router"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_request_reply"] = _cfg(
    "Add a Request Reply pattern to iFlow {iflow_name}.",
    [{"intent": "ADD_REQUEST_REPLY"}],
    {"type": "component_present", "component": "RequestReply"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_process_direct"] = _cfg(
    "Add a ProcessDirect channel to iFlow {iflow_name}.",
    [{"intent": "ADD_PROCESS_DIRECT"}],
    {"type": "component_present", "component": "ProcessDirect"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_exception_subprocess"] = _cfg(
    "Add an exception subprocess to iFlow {iflow_name}.",
    [{"intent": "ADD_EXCEPTION_SUBPROCESS"}],
    {"type": "component_present", "component": "ExceptionSubprocess"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_general_splitter"] = _cfg(
    "Add a General Splitter to iFlow {iflow_name}.",
    [{"intent": "ADD_GENERAL_SPLITTER"}],
    {"type": "component_present", "component": "GeneralSplitter"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_gather"] = _cfg(
    "Add a Gather step to iFlow {iflow_name}.",
    [{"intent": "ADD_GATHER"}],
    {"type": "component_present", "component": "Gather"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_iflow"},
)

TASK_TEMPLATES["add_xslt"] = _cfg(
    "Add an XSLT mapping to iFlow {iflow_name}.",
    [{"intent": "ADD_XSLT"}],
    {"type": "component_present", "component": "XSLT"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_ifflow"},
)

TASK_TEMPLATES["delete_iflow"] = _cfg(
    "Delete the iFlow {iflow_name} from package {package_name}.",
    [{"intent": "DELETE_IFLOW"}],
    {"type": "iflow_deleted", "iflow_id": "{iflow_name}"},
    variables={"package_name": pid, "iflow_name": tid},
    cleanup={"type": "delete_package"},
)

# ── Level 3: Integration Development (20 tasks) ────────────────────────────────

TASK_TEMPLATES["int_https_odata_v4"] = _int(
    "Create an HTTPS to OData V4 integration iFlow named {iflow_name} in package {package_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
    ],
    {"type": "iflow_with_adapters", "sender": "HTTPS", "receiver": "OData V4"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
    variables={"package_name": "INT_HTOD_{rand6}", "iflow_name": "HTTPS_ODataV4_{rand4}"},
)

TASK_TEMPLATES["int_https_odata_v2"] = _int(
    "Create an HTTPS to OData V2 integration iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V2"},
    ],
    {"type": "iflow_with_adapters", "sender": "HTTPS", "receiver": "OData V2"},
    variables={"package_name": "INT_HTOD2_{rand6}", "iflow_name": "HTTPS_ODataV2_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_sftp_mapping_s4"] = _int(
    "Create an SFTP to S/4HANA integration with message mapping iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "SFTP"},
        {"intent": "ADD_MESSAGE_MAPPING"},
    ],
    {"type": "iflow_with_adapters", "sender": "SFTP"},
    variables={"package_name": "INT_SFTP_{rand6}", "iflow_name": "SFTP_S4_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_jms_http"] = _int(
    "Create a JMS to HTTP integration iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "JMS"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
    ],
    {"type": "iflow_with_adapters", "sender": "JMS", "receiver": "HTTP"},
    variables={"package_name": "INT_JMS_{rand6}", "iflow_name": "JMS_HTTP_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_soap_rest"] = _int(
    "Create a SOAP to REST integration iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "SOAP"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
    ],
    {"type": "iflow_with_adapters", "sender": "SOAP", "receiver": "HTTP"},
    variables={"package_name": "INT_SOAP_{rand6}", "iflow_name": "SOAP_REST_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_splitter_mapping_gather"] = _int(
    "Add a General Splitter, message mapping, and Gather to iFlow {iflow_name}.",
    [
        {"intent": "ADD_GENERAL_SPLITTER"},
        {"intent": "ADD_MESSAGE_MAPPING"},
        {"intent": "ADD_GATHER"},
    ],
    {"type": "components_present", "components": ["GeneralSplitter", "MessageMapping", "Gather"]},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_router"] = _int(
    "Add a Router to iFlow {iflow_name} to route messages based on payload content.",
    [{"intent": "ADD_ROUTER"}],
    {"type": "component_present", "component": "Router"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_request_reply"] = _int(
    "Add a Request Reply pattern to iFlow {iflow_name}.",
    [{"intent": "ADD_REQUEST_REPLY"}],
    {"type": "component_present", "component": "RequestReply"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_process_direct"] = _int(
    "Add a ProcessDirect channel to iFlow {iflow_name}.",
    [{"intent": "ADD_PROCESS_DIRECT"}],
    {"type": "component_present", "component": "ProcessDirect"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_iterating_splitter"] = _int(
    "Add an Iterating Splitter to iFlow {iflow_name}.",
    [{"intent": "ADD_ITERATING_SPLITTER"}],
    {"type": "component_present", "component": "IteratingSplitter"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_multicast"] = _int(
    "Add a Multicast step to iFlow {iflow_name} to send to multiple receivers.",
    [{"intent": "ADD_MULTICAST"}],
    {"type": "component_present", "component": "Multicast"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_exception_subprocess"] = _int(
    "Add an exception subprocess to iFlow {iflow_name} for error handling.",
    [{"intent": "ADD_EXCEPTION_SUBPROCESS"}],
    {"type": "component_present", "component": "ExceptionSubprocess"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_groovy_script"] = _int(
    "Add a Groovy Script step to transform messages in iFlow {iflow_name}.",
    [{"intent": "ADD_GROOVY_SCRIPT"}],
    {"type": "component_present", "component": "GroovyScript"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_xslt_mapping"] = _int(
    "Add an XSLT mapping step to iFlow {iflow_name}.",
    [{"intent": "ADD_XSLT"}],
    {"type": "component_present", "component": "XSLT"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_content_modifier"] = _int(
    "Add a Content Modifier with header and property modifications to iFlow {iflow_name}.",
    [{"intent": "ADD_CONTENT_MODIFIER"}],
    {"type": "component_present", "component": "ContentModifier"},
    variables={"package_name": pid, "iflow_name": tid},
)

TASK_TEMPLATES["int_sftp_mapping_deploy"] = _int(
    "Create an SFTP polling integration with mapping, deploy it and verify MPL.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "CONFIGURE_SFTP"},
        {"intent": "ADD_MESSAGE_MAPPING"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "INT_SFTP_{rand6}", "iflow_name": "SFTP_Map_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_https_idoc"] = _int(
    "Create an HTTPS to IDoc integration iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "SOAP"},
    ],
    {"type": "iflow_with_adapters", "sender": "HTTPS", "receiver": "SOAP"},
    variables={"package_name": "INT_IDOC_{rand6}", "iflow_name": "HTTPS_IDoc_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_event_mesh_jms"] = _int(
    "Create an Event Mesh to JMS integration iFlow named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "Event Mesh"},
        {"intent": "ADD_RECEIVER", "adapter": "JMS"},
    ],
    {"type": "iflow_with_adapters", "sender": "Event Mesh", "receiver": "JMS"},
    variables={"package_name": "INT_EM_{rand6}", "iflow_name": "EM_JMS_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["int_http_odata_v4_mapping"] = _int(
    "Create an HTTP to OData V4 integration with message mapping named {iflow_name}.",
    [
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTP"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_MESSAGE_MAPPING"},
    ],
    {"type": "iflow_with_adapters", "sender": "HTTP", "receiver": "OData V4"},
    variables={"package_name": "INT_HOD4_{rand6}", "iflow_name": "HTTP_ODataV4_{rand4}"},
    setup={"type": "create_package", "name": "{package_name}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

# ── Level 4: Debugging (20 tasks) ──────────────────────────────────────────────

TASK_TEMPLATES["debug_401_auth"] = _dbg(
    "The iFlow {iflow_name} is failing with HTTP 401. Diagnose and fix the authentication issue.",
    [{"intent": "QUERY_MPL"}, {"intent": "OPEN_SECURITY_MATERIAL"}],
    {"type": "mpl_success"},
    variables={"iflow_name": "SalesOrderSync", "package_name": "SALES"},
)

TASK_TEMPLATES["debug_403_forbidden"] = _dbg(
    "The iFlow is returning HTTP 403 Forbidden. Investigate the authorization issue.",
    [{"intent": "QUERY_MPL"}, {"intent": "GET_TRACE"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_404_not_found"] = _dbg(
    "The iFlow is getting HTTP 404 Not Found. Check the endpoint configuration.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_HTTPS"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_500_server_error"] = _dbg(
    "The integration is returning HTTP 500. Diagnose the server-side error.",
    [{"intent": "QUERY_MPL"}, {"intent": "GET_TRACE"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_503_unavailable"] = _dbg(
    "The receiver endpoint is returning HTTP 503 Service Unavailable. Fix the configuration.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_HTTPS"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_unknown_host"] = _dbg(
    "The iFlow is failing with UnknownHostException. Fix the endpoint configuration.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_HTTPS"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_timeout"] = _dbg(
    "The integration is timing out. Diagnose and fix the timeout configuration.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_HTTPS"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_mapping_error"] = _dbg(
    "The message mapping is failing. Fix the mapping configuration.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_MESSAGE_MAPPING"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_xpath_error"] = _dbg(
    "The XPath expression in the Content Modifier is invalid. Fix it.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_CONTENT_MODIFIER"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_missing_credential"] = _dbg(
    "The iFlow references a missing credential. Find and correct the security material reference.",
    [{"intent": "QUERY_MPL"}, {"intent": "OPEN_SECURITY_MATERIAL"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_wrong_credential"] = _dbg(
    "The iFlow has the wrong credential reference. Identify and correct it.",
    [{"intent": "QUERY_MPL"}, {"intent": "OPEN_SECURITY_MATERIAL"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_queue_missing"] = _dbg(
    "The JMS queue referenced by the iFlow does not exist. Create or correct the queue reference.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_JMS"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_bad_endpoint"] = _dbg(
    "The receiver endpoint URL is malformed. Fix it and redeploy.",
    [{"intent": "QUERY_MPL"}, {"intent": "CONFIGURE_HTTP"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_certificate_expired"] = _dbg(
    "The TLS certificate used by the HTTPS sender has expired. Update the security material.",
    [{"intent": "QUERY_MPL"}, {"intent": "OPEN_SECURITY_MATERIAL"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_deployment_failure"] = _dbg(
    "The deployment failed. Investigate the error and redeploy.",
    [{"intent": "QUERY_MPL"}, {"intent": "DEPLOY_IFLOW"}],
    {"type": "iflow_deployed"},
)

TASK_TEMPLATES["debug_payload_parse_error"] = _dbg(
    "The integration is failing to parse the incoming XML payload. Fix the message mapping.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_MESSAGE_MAPPING"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_broken_payload"] = _dbg(
    "A malformed payload is causing the integration to fail. Add validation.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_CONTENT_MODIFIER"}],
    {"type": "mpl_success"},
)

TASK_TEMPLATES["debug_missing_sender"] = _dbg(
    "The iFlow has no sender channel configured. Add an HTTPS sender.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_SENDER", "adapter": "HTTPS"}],
    {"type": "sender_adapter", "adapter": "HTTPS"},
)

TASK_TEMPLATES["debug_missing_receiver"] = _dbg(
    "The iFlow has no receiver channel configured. Add an HTTP receiver.",
    [{"intent": "QUERY_MPL"}, {"intent": "ADD_RECEIVER", "adapter": "HTTP"}],
    {"type": "receiver_adapter", "adapter": "HTTP"},
)

TASK_TEMPLATES["debug_deploy_then_fix"] = _dbg(
    "The iFlow deployment failed with a configuration error. Fix the error and redeploy.",
    [{"intent": "QUERY_MPL"}, {"intent": "DEPLOY_IFLOW"}],
    {"type": "iflow_deployed"},
)

TASK_TEMPLATES["debug_retry_message"] = _dbg(
    "A message in the MPL is in error status. Retry the message.",
    [{"intent": "QUERY_MPL"}, {"intent": "RETRY_MESSAGE"}],
    {"type": "mpl_success"},
)

# ── Level 5: Long-horizon Architecture (20 tasks) ──────────────────────────────

TASK_TEMPLATES["arch_https_s4_odata_full"] = _arch(
    "Build an HTTPS to S/4HANA OData V4 integration named {iflow_name} with exception "
    "handling, deploy it in DEV, test it and confirm the MPL is successful.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_S4_{rand6}", "iflow_name": "HTTPS_S4_OData_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_eventmesh_s4"] = _arch(
    "Build an asynchronous Blue Yonder to S/4 integration using Event Mesh with JMS "
    "retry for recoverable errors and error logging.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "Event Mesh"},
        {"intent": "CONFIGURE_JMS"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_EM_{rand6}", "iflow_name": "EM_S4_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_sftp_mapping_deploy"] = _arch(
    "Build an SFTP to S/4 integration with message mapping, deploy it and verify with a test message.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "CONFIGURE_SFTP"},
        {"intent": "ADD_MESSAGE_MAPPING"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_SFTP_{rand6}", "iflow_name": "SFTP_S4_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_api_proxy"] = _arch(
    "Create an API proxy for the deployed endpoint with API-key verification and quota protection.",
    [
        {"intent": "CREATE_API_PROVIDER"},
        {"intent": "CREATE_API_PROXY"},
        {"intent": "ADD_API_POLICY"},
        {"intent": "DEPLOY_API_PROXY"},
    ],
    {"type": "api_proxy_deployed"},
    variables={"package_name": "ARCH_APIM_{rand6}", "iflow_name": "Proxy_{rand4}"},
)

TASK_TEMPLATES["arch_full_recovery"] = _arch(
    "Create an HTTPS to HTTP integration, deploy it, detect a 401 error, fix the "
    "credential configuration, redeploy and verify MPL success.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
        {"intent": "OPEN_SECURITY_MATERIAL"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_REC_{rand6}", "iflow_name": "HTTPS_HTTP_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_https_s4_oauth"] = _arch(
    "Build an HTTPS to S/4 OData integration with OAuth2 client credentials, "
    "payload transformation and exception handling.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "CONFIGURE_OAUTH"},
        {"intent": "ADD_CONTENT_MODIFIER"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_OAUTH_{rand6}", "iflow_name": "OAuth_OData_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_jms_retry"] = _arch(
    "Build an HTTPS to JMS integration with retry configuration for recoverable errors.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "JMS"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_JMS_{rand6}", "iflow_name": "HTTPS_JMS_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_splitter_gather_mapping"] = _arch(
    "Build a splitter → message mapping → gather integration for batch processing.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_GENERAL_SPLITTER"},
        {"intent": "ADD_MESSAGE_MAPPING"},
        {"intent": "ADD_GATHER"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_BATCH_{rand6}", "iflow_name": "BatchSplit_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_router_branches"] = _arch(
    "Build an integration with a Router that branches messages to HTTP and JMS receivers.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_ROUTER"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
        {"intent": "ADD_RECEIVER", "adapter": "JMS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_RT_{rand6}", "iflow_name": "Router_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_request_reply_pattern"] = _arch(
    "Build a Request Reply pattern for synchronous calling an external OData service.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_REQUEST_REPLY"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_RR_{rand6}", "iflow_name": "ReqReply_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_async_retry_servicenow"] = _arch(
    "Build an asynchronous integration with Event Mesh, JMS retry for recoverable "
    "errors, and error logging for non-recoverable failures.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "Event Mesh"},
        {"intent": "CONFIGURE_JMS"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "ADD_GROOVY_SCRIPT"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_ASYNC_{rand6}", "iflow_name": "AsyncRetry_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_full_lifecycle"] = _arch(
    "Create a package, build an HTTPS→OData iFlow with exception handling, deploy, "
    "test via MPL, diagnose any error, fix, redeploy and verify.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
        {"intent": "RUN_TEST"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_LF_{rand6}", "iflow_name": "Lifecycle_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_scheduled_polling"] = _arch(
    "Build a scheduled polling integration that reads from SFTP, transforms with "
    "XSLT mapping, and sends to an HTTP endpoint.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "CONFIGURE_SFTP"},
        {"intent": "ADD_XSLT"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_POLL_{rand6}", "iflow_name": "PollSFTP_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_groovy_transform"] = _arch(
    "Build an HTTPS to OData integration where a Groovy Script transforms the payload "
    "before sending, with error handling and retry.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_GROOVY_SCRIPT"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_GRV_{rand6}", "iflow_name": "GroovyXform_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_eventmesh_multicast"] = _arch(
    "Build an Event Mesh integration that multicasts messages to three different receivers.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "Event Mesh"},
        {"intent": "ADD_MULTICAST"},
        {"intent": "ADD_RECEIVER", "adapter": "HTTP"},
        {"intent": "ADD_RECEIVER", "adapter": "JMS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_MC_{rand6}", "iflow_name": "MultiCast_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_api_proxy_with_policies"] = _arch(
    "Create an API proxy for an OData service with API-key verification, quota "
    "limiting, and spike arrest policies.",
    [
        {"intent": "CREATE_API_PROVIDER"},
        {"intent": "CREATE_API_PROXY"},
        {"intent": "ADD_API_POLICY"},
        {"intent": "DEPLOY_API_PROXY"},
    ],
    {"type": "api_proxy_deployed"},
    variables={"package_name": "ARCH_APIM_{rand6}", "iflow_name": "Proxy_{rand4}"},
)

TASK_TEMPLATES["arch_process_direct_chain"] = _arch(
    "Build a chain of two iFlows connected by ProcessDirect channels in the same package.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_PROCESS_DIRECT"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_PD_{rand6}", "iflow_name": "PDChain_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_s4_employee_replication"] = _arch(
    "Build a SuccessFactors to S/4 employee replication integration with scheduled "
    "polling, mapping, error handling and monitoring.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_MESSAGE_MAPPING"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_SF_{rand6}", "iflow_name": "Sf2S4_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_end_to_end_test"] = _arch(
    "Build an HTTPS to OData integration end-to-end: create package, iFlow, configure "
    "adapters, add error handling, deploy, send test message, read MPL and verify success.",
    [
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "ADD_RECEIVER", "adapter": "OData V4"},
        {"intent": "ADD_EXCEPTION_SUBPROCESS"},
        {"intent": "DEPLOY_IFLOW"},
        {"intent": "RUN_TEST"},
        {"intent": "QUERY_MPL"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_E2E_{rand6}", "iflow_name": "E2E_Test_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)

TASK_TEMPLATES["arch_security_and_deploy"] = _arch(
    "Create security material (user credentials), configure it in an HTTPS sender, "
    "create the integration iFlow and deploy it.",
    [
        {"intent": "CREATE_SECURITY_MATERIAL"},
        {"intent": "CREATE_PACKAGE"},
        {"intent": "CREATE_IFLOW"},
        {"intent": "ADD_SENDER", "adapter": "HTTPS"},
        {"intent": "DEPLOY_IFLOW"},
    ],
    {"type": "full_integration_verified"},
    variables={"package_name": "ARCH_SEC_{rand6}", "iflow_name": "Secure_{rand4}"},
    cleanup={"type": "delete_package", "package_id": "{package_name}"},
)


# ─── Generator ────────────────────────────────────────────────────────────────

def generate_task(template_name: str, seed: int | None = None) -> TaskDefinition:
    """Generate a single task from a template."""
    if template_name not in TASK_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")
    rng = random.Random(seed)
    template = TASK_TEMPLATES[template_name]
    substitutions = {
        f"rand{n}": "".join(rng.choices(string.ascii_uppercase + string.digits, k=n))
        for n in (4, 5, 6, 8)
    }

    def expand(value: Any) -> Any:
        if isinstance(value, str):
            for key, replacement in substitutions.items():
                value = value.replace("{" + key + "}", replacement)
            return value
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        return value

    variables = {k: expand(str(v)) for k, v in template.get("variables", {}).items()}
    substitutions.update(variables)
    instruction = template["instruction"]
    for k, v in variables.items():
        instruction = instruction.replace(f"{{{k}}}", str(v))
    task_id = f"SB-{template_name}-{substitutions['rand4'].lower()}"
    return TaskDefinition(
        task_id=task_id,
        instruction=instruction,
        module=template.get("module"),
        difficulty=template.get("difficulty", 1),
        setup=expand(template.get("setup")),
        verify=expand(template.get("verify")),
        cleanup=expand(template.get("cleanup")),
        tags=[template.get("category", ""), template_name],
    )


def generate_benchmark_suite(
    count_per_level: dict[int, int] | None = None,
    *, seed: int = 0,
) -> list[TaskDefinition]:
    """Generate a full benchmark suite across all levels."""
    count_per_level = count_per_level or {1: 15, 2: 20, 3: 20, 4: 20, 5: 20}
    tasks: list[TaskDefinition] = []
    templates_by_level: dict[int, list[str]] = {lvl: [] for lvl in count_per_level}
    for tpl_name, tpl in TASK_TEMPLATES.items():
        lvl = tpl.get("difficulty", 1)
        if lvl in templates_by_level:
            templates_by_level[lvl].append(tpl_name)
    for level, count in count_per_level.items():
        templates = templates_by_level.get(level, [])
        if not templates:
            continue
        for i in range(count):
            tpl = templates[i % len(templates)]
            task = generate_task(tpl, seed=seed + level * 10000 + i)
            task.task_id = f"SB-L{level}-{tpl}-{i:03d}"
            tasks.append(task)
    return tasks


def count_templates() -> dict[int, int]:
    """Return template counts by difficulty level."""
    counts: dict[int, int] = {}
    for tpl in TASK_TEMPLATES.values():
        lvl = tpl.get("difficulty", 1)
        counts[lvl] = counts.get(lvl, 0) + 1
    return counts


def get_total_templates() -> int:
    return len(TASK_TEMPLATES)
