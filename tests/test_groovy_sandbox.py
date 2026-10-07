"""Tests for groovy sandbox module."""

from __future__ import annotations

import pytest

from sap_cua.runtime.code.groovy_sandbox import GroovySandbox


@pytest.fixture
def sandbox():
    return GroovySandbox(timeout_seconds=5)


class TestGroovySandbox:
    def test_safe_script_passes(self, sandbox):
        script = """
import com.sap.gateway.ip.core.customdev.util.Message

def Message processData(Message message) {
    def body = message.getBody(String)
    message.setBody(body)
    return message
}
"""
        safe, issues = sandbox.validate_safety(script)
        assert safe is True
        assert issues == []

    def test_system_exit_blocked(self, sandbox):
        script = "System.exit(1)"
        safe, issues = sandbox.validate_safety(script)
        assert safe is False
        assert any("System.exit" in i for i in issues)

    def test_process_builder_blocked(self, sandbox):
        script = "new ProcessBuilder(['ls']).start()"
        safe, issues = sandbox.validate_safety(script)
        assert safe is False

    def test_runtime_blocked(self, sandbox):
        script = "Runtime.getRuntime().exec('ls')"
        safe, issues = sandbox.validate_safety(script)
        assert safe is False

    def test_empty_script_blocked(self, sandbox):
        safe, issues = sandbox.validate_safety("")
        assert safe is False

    def test_execute_safe_returns_output(self, sandbox):
        script = "message.getBody()"
        success, output = sandbox.execute(script)
        assert success is True

    def test_file_write_outside_tmp_blocked(self, sandbox):
        script = 'new File("/etc/passwd").writeText("hacked")'
        safe, issues = sandbox.validate_safety(script)
        assert safe is False
