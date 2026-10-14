"""Requirements must not silently become a different integration."""

import pytest

from sap_cua.engineering.benchmark import TASKS
from sap_cua.engineering.planner import SAPPlanner
from sap_cua.rag.schemas import Scope

SCOPE = Scope(customer="local", tenant="dev")


@pytest.mark.parametrize(
    "requirement,sender,receiver",
    [
        ("Create JMS to HTTP integration", "JMS", "HTTP"),
        ("Please create a JMS integration flow to HTTP", "JMS", "HTTP"),
        ("Create a SOAP to REST integration flow", "SOAP", "HTTP"),
        ("Please build an integration flow from SOAP to HTTPS", "SOAP", "HTTP"),
        ("Create HTTPS to SOAP", "HTTPS", "SOAP"),
        ("Create SOAP to SOAP", "SOAP", "SOAP"),
        ("Create SFTP to OData V4", "SFTP", "ODataV4"),
        ("Create Event Mesh to OData V2", "EventMesh", "ODataV2"),
        ("Create HTTPS with JMS retry to HTTP", "HTTPS", "HTTP"),
        ("Create HTTPS HTTP integration", "HTTPS", "HTTP"),
        ("  Create an HTTPS to HTTP integration flow  ", "HTTPS", "HTTP"),
    ],
)
def test_explicit_endpoints_preserve_direction(requirement, sender, receiver):
    plan = SAPPlanner().plan(requirement, SCOPE)
    assert not plan.blockers
    adapters = {
        s.args["direction"]: s.args["adapter"]
        for s in plan.steps
        if s.action == "CONFIGURE_ADAPTER"
    }
    assert adapters == {"sender": sender, "receiver": receiver}


@pytest.mark.parametrize(
    "requirement",
    [
        "Create an integration flow",
        "Create JMS integration",
        "Create HTTPS to SFTP",
        "Create OData V4 to HTTP",
        "Create HTTPS to HTTP and SOAP",
        "Create HTTPS to HTTP or SOAP",
        "Create HTTPS to HTTP without a router",
        "Create HTTPS to HTTP with encryption",
        "Create HTTPS to HTTP with a GET method",
        "Create HTTPS to HTTP every 10 minutes",
        "Create HTTPS to HTTP at https://example.com/api",
        "Create HTTPS to HTTP and send email notifications",
        "Create HTTPS to HTTP with two routers",
        "Create HTTPS Router Router to HTTP",
        "Create HTTPS to HTTP using a custom Groovy script",
        "Create ProcessDirect to HTTP",
        "Create HTTPS to OData V3",
    ],
)
def test_unsupported_or_ambiguous_requirements_have_no_executable_steps(requirement):
    plan = SAPPlanner().plan(requirement, SCOPE)
    assert plan.blockers
    assert plan.pattern == "UNSUPPORTED"
    assert plan.steps == []


def test_component_order_matches_request():
    plan = SAPPlanner().plan("Create HTTPS Router Content Modifier to HTTP", SCOPE)
    assert not plan.blockers
    components = [s for s in plan.steps if s.action == "ADD_COMPONENT"]
    assert [s.args["component"] for s in components] == ["Router", "ContentModifier"]
    assert [s.args["after"] for s in components] == ["Start", "Router"]


@pytest.mark.parametrize("requirement", TASKS)
def test_existing_benchmark_requirements_remain_supported(requirement):
    assert not SAPPlanner().plan(requirement, SCOPE).blockers
