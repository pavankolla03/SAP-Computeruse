"""Tests for agent loop and code generation."""

from __future__ import annotations

import json

import pytest

from sap_cua.runtime.code import CodeGenerator
from sap_cua.agent.agent_loop import AgentLoop


# ─── Code Generator Tests ─────────────────────────────────────────────────────

class TestCodeGenerator:
    generator = CodeGenerator()

    def test_generate_groovy_has_entry_point(self):
        script = self.generator.generate_groovy("Transform order data")
        assert "processData" in script
        assert "Message" in script

    def test_generate_xslt_has_root(self):
        xslt = self.generator.generate_xslt("source.xsd", "target.xsd")
        assert "xsl:stylesheet" in xslt
        assert "source.xsd" in xslt

    def test_generate_xpath(self):
        xpath = self.generator.generate_xpath("Order", "Order.CustomerID")
        assert "//" in xpath

    def test_generate_openapi(self):
        spec = self.generator.generate_openapi("SalesOrder", [
            {"path": "/Orders", "methods": ["get"], "summary": "Get orders"},
        ])
        assert spec["openapi"].startswith("3.")
        assert "/Orders" in spec["paths"]

    def test_generate_test_payload_odata(self):
        payload = self.generator.generate_test_payload("odata_v4")
        assert "d" in payload
        assert "SalesOrder" in payload["d"]

    def test_generate_test_payload_soap(self):
        payload = self.generator.generate_test_payload("soap")
        assert "soap:Envelope" in payload

    def test_lint_groovy_missing_entry_point(self):
        issues = self.generator.lint_groovy("// comment only")
        assert len(issues) > 0

    def test_lint_xslt_missing_root(self):
        issues = self.generator.lint_xslt("<div/>")
        assert len(issues) > 0

    def test_generate_xslt_with_mappings(self):
        mappings = [
            {"source_path": "Order/ID", "target_field": "OrderID"},
            {"source_path": "Order/Name", "target_field": "OrderName"},
        ]
        xslt = self.generator.generate_xslt("src", "tgt", mappings)
        assert "OrderID" in xslt
        assert "OrderName" in xslt


# ─── Agent Loop Tests ─────────────────────────────────────────────────────────

class TestAgentLoop:
    def test_agent_loop_creation(self):
        loop = AgentLoop(model="mock", max_steps=5)
        assert loop.max_steps == 5
        assert len(loop.history) == 0

    def test_agent_loop_run_mock(self):
        loop = AgentLoop(model="mock", max_steps=3)
        result = loop.run("Open Cloud Integration")
        assert "success" in result
        assert "steps" in result
        assert "duration_ms" in result
        assert result["steps"] <= 3

    def test_agent_loop_reset(self):
        loop = AgentLoop(model="mock", max_steps=5)
        loop.run("Test task")
        loop.reset()
        assert len(loop.history) == 0

    def test_agent_loop_max_steps(self):
        loop = AgentLoop(model="mock", max_steps=2)
        result = loop.run("Very long task")
        assert result["steps"] <= 2

    def test_agent_loop_history_records_steps(self):
        loop = AgentLoop(model="mock", max_steps=5)
        result = loop.run("Create a package")
        if result.get("actions"):
            assert len(result["actions"]) > 0
