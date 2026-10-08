import hashlib
import io
import zipfile

import pytest

from sap_cua.engineering.budget import Budget
from sap_cua.engineering.templates import IFlowTemplateEngine, blueprint
from sap_cua.rag.evaluation import retrieval_metrics
from sap_cua.runtime.browser.insertion import Box, insertion_point


def archive(name, content):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(name, content)
    return out.getvalue()


def test_template_substitution_is_xml_safe():
    data = archive(
        "src/main/resources/scenarioflows/integrationflow/Flow.iflw",
        "<flow><endpoint>{{RECEIVER_URL}}</endpoint></flow>",
    )
    result = IFlowTemplateEngine().render(
        data,
        {"RECEIVER_URL": "https://example.test/?a=1&b=2"},
        approved_sha256=hashlib.sha256(data).hexdigest(),
    )
    assert result["validated_xml"] and not result["tenant_validated"]
    with zipfile.ZipFile(io.BytesIO(result["artifact"])) as z:
        assert b"&amp;" in z.read(z.namelist()[0])


@pytest.mark.parametrize(
    "name,content",
    [
        ("../unsafe.iflw", "<flow/>"),
        ("Flow.iflw", '<!DOCTYPE f [<!ENTITY x SYSTEM "file:///etc/passwd">]><f>&x;</f>'),
        ("readme.txt", "not an artifact"),
    ],
)
def test_unsafe_templates_fail(name, content):
    data = archive(name, content)
    from defusedxml.common import DefusedXmlException

    with pytest.raises((ValueError, DefusedXmlException)):
        IFlowTemplateEngine().render(data, {}, approved_sha256=hashlib.sha256(data).hexdigest())


def test_blueprint_is_not_falsely_deployable():
    assert not blueprint("HTTPS_TO_ODATA_V4")["deployable"]


def test_budget_reserves_before_execution():
    budget = Budget(1)
    budget.reserve("a", 0.8)
    with pytest.raises(RuntimeError):
        budget.reserve("b", 0.3)
    budget.settle("a", 0.7)
    budget.reserve("b", 0.3)
    budget.release("b")
    assert float(budget.spent) == 0.7


def test_dynamic_drop_uses_current_geometry():
    assert insertion_point(
        Box(0, 0, 1000, 400), Box(100, 100, 100, 50), Box(400, 100, 100, 50)
    ) == (300, 125)
    assert insertion_point(Box(0, 0, 200, 200), Box(150, 50, 40, 30))[0] == 198
    with pytest.raises(ValueError):
        insertion_point(Box(0, 0, 100, 100), Box(200, 0, 10, 10))


def test_rag_metrics_known_values():
    m = retrieval_metrics(["a", "a", "b", "c"], {"b", "c"}, k=3)
    assert m["recall_at_k"] == 1 and m["mrr"] == 0.5 and 0 < m["ndcg"] < 1
