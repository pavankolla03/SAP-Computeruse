"""Unit tests for the SAP mock environment."""

from __future__ import annotations

import pytest

from sap_cua.sap.mocks import SAPMockEnvironment
from sap_cua.sap.actions import SAPActionType


@pytest.fixture
def env():
    return SAPMockEnvironment(tenant_id="test-tenant")


def test_create_package(env: SAPMockEnvironment):
    result = env.create_package("TEST_PKG", "Test package")
    assert result["success"] is True
    assert result["package_id"] == "TEST_PKG"
    assert env.get_package("TEST_PKG") is not None


def test_create_duplicate_package(env: SAPMockEnvironment):
    env.create_package("DUP", "First")
    result = env.create_package("DUP", "Second")
    assert result["success"] is False


def test_create_iflow(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    result = env.create_iflow("PKG", "TestFlow")
    assert result["success"] is True
    assert result["iflow_id"] == "TESTFLOW"


def test_create_iflow_missing_package(env: SAPMockEnvironment):
    result = env.create_iflow("MISSING", "TestFlow")
    assert result["success"] is False


def test_deploy_iflow(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    env.create_iflow("PKG", "TestFlow")
    result = env.deploy_iflow("PKG", "TESTFLOW")
    assert result["success"] is True
    assert result["status"] == "DEPLOYED"


def test_add_sender(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    env.create_iflow("PKG", "TestFlow")
    result = env.add_sender("PKG", "TESTFLOW", "HTTPS", {"address": "https://example.com"})
    assert result["success"] is True
    assert "sender_id" in result


def test_add_receiver(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    env.create_iflow("PKG", "TestFlow")
    result = env.add_receiver("PKG", "TESTFLOW", "HTTP", {"path": "/api"})
    assert result["success"] is True
    assert "receiver_id" in result


def test_delete_package(env: SAPMockEnvironment):
    env.create_package("EMPTY", "Empty package")
    result = env.delete_package("EMPTY")
    assert result["success"] is True


def test_delete_package_with_iflows(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    env.create_iflow("PKG", "TestFlow")
    result = env.delete_package("PKG")
    assert result["success"] is False


def test_execute_action_create_package(env: SAPMockEnvironment):
    result = env.execute_action(SAPActionType.CREATE_PACKAGE, {"name": "NEW_PKG"})
    assert result["success"] is True
    assert result["package_id"] == "NEW_PKG"


def test_execute_action_deploy_iflow(env: SAPMockEnvironment):
    env.create_package("PKG", "Package")
    env.create_iflow("PKG", "TestFlow")
    result = env.execute_action(SAPActionType.DEPLOY_IFLOW, {"package_id": "PKG", "iflow_id": "TESTFLOW"})
    assert result["success"] is True


def test_execute_action_missing_args(env: SAPMockEnvironment):
    result = env.execute_action(SAPActionType.CREATE_PACKAGE, {})
    assert result["success"] is False