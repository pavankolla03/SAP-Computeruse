import json
import httpx
import pytest
from sap_cua.runtime.sap_api import SAPAPIClient


def client(handler, **kwargs):
    return SAPAPIClient(
        api_base="https://tenant.example/api/v1",
        token_url="https://auth.example/oauth/token",
        client_id="client",
        client_secret="secret",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def test_oauth_per_instance_and_real_paths():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "auth.example":
            assert b"grant_type=client_credentials" == request.content
            return httpx.Response(200, json={"access_token": "test-access", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer test-access"
        return httpx.Response(200, json={"d": {"Id": "DEMO"}})

    with client(handler) as api:
        assert api.get_package("DEMO")["success"]
        assert api.get_iflows("DEMO")["success"]
    assert len(seen) == 3
    assert seen[1].url.path == "/api/v1/IntegrationPackages('DEMO')"
    assert seen[2].url.path.endswith("/IntegrationDesigntimeArtifacts")


def test_unconfigured_client_never_mock_success(monkeypatch):
    for key in ("SAP_API_BASE_URL", "SAP_TOKEN_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError):
        SAPAPIClient()


def test_mutations_denied_before_any_network():
    with client(lambda _: pytest.fail("network called")) as api:
        assert api.create_package("DEMO")["success"] is False


def test_write_timeout_is_never_retried():
    calls = []

    def handler(request):
        if request.url.host == "auth.example":
            return httpx.Response(200, json={"access_token": "test"})
        if request.headers.get('X-CSRF-Token') == 'Fetch':
            return httpx.Response(200,headers={'X-CSRF-Token':'test-csrf'},json={'d':{'results':[]}})
        assert request.headers['X-CSRF-Token']=='test-csrf'
        calls.append(request)
        raise httpx.ReadTimeout("credentials should not escape")

    with client(handler, allow_mutations=True) as api:
        result = api.deploy_iflow("DEMO", "FLOW")
    assert len(calls) == 1 and not result["success"]
    assert "credentials" not in result["error"]
    assert calls[0].url.path.endswith("/DeployIntegrationDesigntimeArtifact")
    assert calls[0].url.params["Id"] == "'FLOW'"


def test_query_options_are_sent_and_redirect_not_followed():
    seen = []

    def handler(request):
        if request.url.host == "auth.example":
            return httpx.Response(200, json={"access_token": "test"})
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://other.example"})

    with client(handler) as api:
        result = api.query_mpl({"$filter": "Status eq 'COMPLETED'"}, limit=3)
    assert not result["success"] and len(seen) == 1
    assert seen[0].url.params["$top"] == "3"
    assert seen[0].url.params["$filter"] == "Status eq 'COMPLETED'"


def test_odata_identifier_injection_blocked():
    with client(lambda _: pytest.fail("network called")) as api:
        with pytest.raises(ValueError):
            api.get_package("x')/Other('")


def test_csrf_cookie_and_token_precede_mutation():
    calls=[]
    def handler(request):
        calls.append(request)
        if request.url.host=='auth.example':return httpx.Response(200,json={'access_token':'test'})
        if request.method=='GET':
            assert request.headers['X-CSRF-Token']=='Fetch'
            return httpx.Response(200,headers={'X-CSRF-Token':'csrf-value','Set-Cookie':'session=fixture; Path=/; Secure'},json={'d':{'results':[]}})
        assert request.headers['X-CSRF-Token']=='csrf-value'
        assert 'session=fixture' in request.headers['Cookie']
        return httpx.Response(201,json={'d':{'Id':'TEST'}})
    with client(handler,allow_mutations=True) as api:assert api.create_package('TEST')['success']
    assert len(calls)==3


def test_missing_csrf_prevents_mutation():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'access_token':'test'} if request.url.host=='auth.example' else {})
    with client(handler,allow_mutations=True) as api:assert not api.create_package('TEST')['success']
    assert all(r.method=='GET' or r.url.host=='auth.example' for r in calls)
