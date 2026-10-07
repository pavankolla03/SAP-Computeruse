"""Unit tests for SAP verifiers."""

from __future__ import annotations

import pytest

from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.services.verifier import (
    run_verifier,
    verify_package_exists,
    verify_iflow_exists,
    verify_iflow_deployed,
    verify_sender_adapter,
    verify_receiver_adapter,
    verify_mpl_success,
    verify_security_material_exists,
    verify_message_status,
    verify_api_proxy_deployed,
    verify_http_response,
    verify_external_parameter,
    verify_iflow_saved,
    verify_components_present,
    verify_package_deleted,
)


@pytest.fixture
def env():
    e = SAPMockEnvironment()
    e.create_package("PKG", "Package")
    e.create_iflow("PKG", "TestFlow")
    e.add_sender("PKG", "TESTFLOW", "HTTPS", {"address": "https://example.com"})
    e.add_receiver("PKG", "TESTFLOW", "HTTP", {"path": "/api"})
    # Add a security material
    e.security_materials["sec_001"] = {"name": "TestCred", "type": "OAuth2ClientCredentials"}
    # Add an MPL entry
    e._add_mpl_entry("PKG:TESTFLOW", "COMPLETED")
    # Add a deployed proxy
    e.api_proxies["MyProxy"] = {"name": "MyProxy", "status": "DEPLOYED", "environment": "dev"}
    # Add components
    e.add_component("PKG", "TESTFLOW", "Router", {"routes": [{"condition": "true"}]})
    # Mark iflow as saved
    e.iFlows["PKG:TESTFLOW"]["saved_at"] = 1234567890.0
    # Add external parameter
    e.iFlows["PKG:TESTFLOW"]["external_parameters"] = [
        {"name": "myParam", "type": "String", "value": "hello"}
    ]
    return e


# ── Existing verifiers ───────────────────────────────────────────────────────

class TestExistingVerifiers:
    def test_verify_package_exists(self, env: SAPMockEnvironment):
        result = verify_package_exists(env, "PKG")
        assert result["success"] is True

    def test_verify_package_missing(self, env: SAPMockEnvironment):
        result = verify_package_exists(env, "MISSING")
        assert result["success"] is False

    def test_verify_iflow_exists(self, env: SAPMockEnvironment):
        result = verify_iflow_exists(env, "PKG", "TESTFLOW")
        assert result["success"] is True

    def test_verify_iflow_missing(self, env: SAPMockEnvironment):
        result = verify_iflow_exists(env, "PKG", "MISSING")
        assert result["success"] is False

    def test_verify_iflow_deployed(self, env: SAPMockEnvironment):
        env.deploy_iflow("PKG", "TESTFLOW")
        result = verify_iflow_deployed(env, "PKG", "TESTFLOW")
        assert result["success"] is True

    def test_verify_iflow_not_deployed(self, env: SAPMockEnvironment):
        result = verify_iflow_deployed(env, "PKG", "TESTFLOW")
        assert result["success"] is False

    def test_verify_sender_adapter(self, env: SAPMockEnvironment):
        result = verify_sender_adapter(env, "PKG", "TESTFLOW", "HTTPS")
        assert result["success"] is True

    def test_verify_wrong_sender(self, env: SAPMockEnvironment):
        result = verify_sender_adapter(env, "PKG", "TESTFLOW", "SOAP")
        assert result["success"] is False

    def test_verify_receiver_adapter(self, env: SAPMockEnvironment):
        result = verify_receiver_adapter(env, "PKG", "TESTFLOW", "HTTP")
        assert result["success"] is True

    def test_run_verifier_dispatch(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_package_exists", package_id="PKG")
        assert result["success"] is True

    def test_run_verifier_unknown(self):
        result = run_verifier(None, "verify_unknown_thing")
        assert result["success"] is False


# ── New verifiers ────────────────────────────────────────────────────────────

class TestVerifySecurityMaterialExists:
    def test_material_exists(self, env: SAPMockEnvironment):
        result = verify_security_material_exists(env, "TestCred")
        assert result["success"] is True

    def test_material_exists_by_id(self, env: SAPMockEnvironment):
        result = verify_security_material_exists(env, "sec_001")
        assert result["success"] is True

    def test_material_not_found(self, env: SAPMockEnvironment):
        result = verify_security_material_exists(env, "NonExistent")
        assert result["success"] is False
        assert "not found" in result["reason"]


class TestVerifyMessageStatus:
    def test_message_status_matches(self, env: SAPMockEnvironment):
        entries = env.mpl_entries
        message_id = entries[0]["message_id"]
        result = verify_message_status(env, message_id, "COMPLETED")
        assert result["success"] is True

    def test_message_status_mismatch(self, env: SAPMockEnvironment):
        entries = env.mpl_entries
        message_id = entries[0]["message_id"]
        result = verify_message_status(env, message_id, "FAILED")
        assert result["success"] is False
        assert "status" in result["reason"]

    def test_message_not_found(self, env: SAPMockEnvironment):
        result = verify_message_status(env, "nonexistent-id", "COMPLETED")
        assert result["success"] is False


class TestVerifyApiProxyDeployed:
    def test_proxy_deployed(self, env: SAPMockEnvironment):
        result = verify_api_proxy_deployed(env, "MyProxy")
        assert result["success"] is True

    def test_proxy_not_found(self, env: SAPMockEnvironment):
        result = verify_api_proxy_deployed(env, "NoProxy")
        assert result["success"] is False

    def test_proxy_not_deployed(self, env: SAPMockEnvironment):
        env.api_proxies["PendingProxy"] = {"name": "PendingProxy", "status": "PENDING"}
        result = verify_api_proxy_deployed(env, "PendingProxy")
        assert result["success"] is False


class TestVerifyHttpResponse:
    def test_unobserved_http_response_fails(self, env: SAPMockEnvironment):
        result = verify_http_response(env, "https://example.com/api", 200)
        assert result["success"] is False
        assert result["url"] == "https://example.com/api"

    def test_real_env_returns_pending(self):
        result = verify_http_response(None, "https://example.com/api")
        assert result["success"] is False


class TestVerifyExternalParameter:
    def test_parameter_exists(self, env: SAPMockEnvironment):
        result = verify_external_parameter(env, "PKG:TESTFLOW", "myParam")
        assert result["success"] is True

    def test_parameter_not_found(self, env: SAPMockEnvironment):
        result = verify_external_parameter(env, "PKG:TESTFLOW", "noSuchParam")
        assert result["success"] is False

    def test_invalid_iflow_key(self, env: SAPMockEnvironment):
        result = verify_external_parameter(env, "BAD_KEY", "myParam")
        assert result["success"] is False

    def test_iflow_not_found(self, env: SAPMockEnvironment):
        result = verify_external_parameter(env, "PKG:NOTHING", "myParam")
        assert result["success"] is False


class TestVerifyIFlowSaved:
    def test_iflow_saved(self, env: SAPMockEnvironment):
        result = verify_iflow_saved(env, "PKG", "TESTFLOW")
        assert result["success"] is True

    def test_iflow_not_saved(self, env: SAPMockEnvironment):
        e = SAPMockEnvironment()
        e.create_package("PKG", "P")
        e.create_iflow("PKG", "Fresh")
        result = verify_iflow_saved(e, "PKG", "FRESH")
        assert result["success"] is False


class TestVerifyComponentsPresent:
    def test_components_present(self, env: SAPMockEnvironment):
        result = verify_components_present(env, "PKG", "TESTFLOW", ["Router"])
        assert result["success"] is True

    def test_multiple_components_present(self, env: SAPMockEnvironment):
        env.add_component("PKG", "TESTFLOW", "ContentModifier", {"operations": []})
        result = verify_components_present(env, "PKG", "TESTFLOW", ["Router", "ContentModifier"])
        assert result["success"] is True

    def test_missing_component(self, env: SAPMockEnvironment):
        result = verify_components_present(env, "PKG", "TESTFLOW", ["Router", "Gather"])
        assert result["success"] is False
        assert "gather" in result["missing"] or "Gather" in result["missing"]

    def test_iflow_not_found(self, env: SAPMockEnvironment):
        result = verify_components_present(env, "PKG", "NOPE", ["Router"])
        assert result["success"] is False


class TestVerifyPackageDeleted:
    def test_package_deleted(self, env: SAPMockEnvironment):
        # Delete all iFlows first so the package can be deleted
        env.iFlows.clear()
        env.packages["PKG"]["iFlows"] = []
        env.delete_package("PKG")
        result = verify_package_deleted(env, "PKG")
        assert result["success"] is True

    def test_package_still_exists(self, env: SAPMockEnvironment):
        result = verify_package_deleted(env, "PKG")
        assert result["success"] is False

    def test_package_never_existed(self, env: SAPMockEnvironment):
        result = verify_package_deleted(env, "NEVER")
        assert result["success"] is True


class TestRunVerifierDispatch:
    """Verify run_verifier dispatches to all new verifiers."""

    def test_dispatch_verify_security_material_exists(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_security_material_exists", name="TestCred")
        assert result["success"] is True

    def test_dispatch_verify_message_status(self, env: SAPMockEnvironment):
        msg_id = env.mpl_entries[0]["message_id"]
        result = run_verifier(env, "verify_message_status", message_id=msg_id, expected_status="COMPLETED")
        assert result["success"] is True

    def test_dispatch_verify_api_proxy_deployed(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_api_proxy_deployed", proxy_name="MyProxy")
        assert result["success"] is True

    def test_dispatch_verify_http_response(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_http_response", url="https://test.com", expected_status=200)
        assert result["success"] is False

    def test_dispatch_verify_external_parameter(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_external_parameter", iflow_key="PKG:TESTFLOW", param_name="myParam")
        assert result["success"] is True

    def test_dispatch_verify_iflow_saved(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_iflow_saved", package_id="PKG", iflow_id="TESTFLOW")
        assert result["success"] is True

    def test_dispatch_verify_components_present(self, env: SAPMockEnvironment):
        result = run_verifier(env, "verify_components_present", package_id="PKG", iflow_id="TESTFLOW", components=["Router"])
        assert result["success"] is True

    def test_dispatch_verify_package_deleted(self, env: SAPMockEnvironment):
        # Clear iFlows so package can be deleted
        env.iFlows.clear()
        env.packages["PKG"]["iFlows"] = []
        env.delete_package("PKG")
        result = run_verifier(env, "verify_package_deleted", package_id="PKG")
        assert result["success"] is True

    def test_dispatch_unknown_verifier(self):
        result = run_verifier(None, "verify_does_not_exist")
        assert result["success"] is False
