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
)


@pytest.fixture
def env():
    e = SAPMockEnvironment()
    e.create_package("PKG", "Package")
    e.create_iflow("PKG", "TestFlow")
    e.add_sender("PKG", "TESTFLOW", "HTTPS", {"address": "https://example.com"})
    e.add_receiver("PKG", "TESTFLOW", "HTTP", {"path": "/api"})
    return e


def test_verify_package_exists(env: SAPMockEnvironment):
    result = verify_package_exists(env, "PKG")
    assert result["success"] is True


def test_verify_package_missing(env: SAPMockEnvironment):
    result = verify_package_exists(env, "MISSING")
    assert result["success"] is False


def test_verify_iflow_exists(env: SAPMockEnvironment):
    result = verify_iflow_exists(env, "PKG", "TESTFLOW")
    assert result["success"] is True


def test_verify_iflow_missing(env: SAPMockEnvironment):
    result = verify_iflow_exists(env, "PKG", "MISSING")
    assert result["success"] is False


def test_verify_iflow_deployed(env: SAPMockEnvironment):
    env.deploy_iflow("PKG", "TESTFLOW")
    result = verify_iflow_deployed(env, "PKG", "TESTFLOW")
    assert result["success"] is True


def test_verify_iflow_not_deployed(env: SAPMockEnvironment):
    result = verify_iflow_deployed(env, "PKG", "TESTFLOW")
    assert result["success"] is False


def test_verify_sender_adapter(env: SAPMockEnvironment):
    result = verify_sender_adapter(env, "PKG", "TESTFLOW", "HTTPS")
    assert result["success"] is True


def test_verify_wrong_sender(env: SAPMockEnvironment):
    result = verify_sender_adapter(env, "PKG", "TESTFLOW", "SOAP")
    assert result["success"] is False


def test_verify_receiver_adapter(env: SAPMockEnvironment):
    result = verify_receiver_adapter(env, "PKG", "TESTFLOW", "HTTP")
    assert result["success"] is True


def test_run_verifier_dispatch(env: SAPMockEnvironment):
    result = run_verifier(env, "verify_package_exists", package_id="PKG")
    assert result["success"] is True


def test_run_verifier_unknown():
    result = run_verifier(None, "verify_unknown_thing")
    assert result["success"] is False