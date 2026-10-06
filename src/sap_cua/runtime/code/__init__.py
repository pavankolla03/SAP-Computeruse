"""SAP-CUA code generation module — generates Groovy, XSLT, XPath, OpenAPI, test payloads."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generate SAP integration code artifacts."""

    def generate_groovy(self, description: str, context: dict[str, Any] | None = None) -> str:
        """Generate a Groovy script from a description."""
        context = context or {}
        script = f"""// SAP-CUA Generated Groovy Script
// Description: {description}
// Generated: auto

import com.sap.gateway.ip.core.customdev.util.Message
import java.util.HashMap

def Message processData(Message message) {{
    def body = message.getBody(String)
    def headers = message.getHeaders()
    def properties = message.getProperties()

    // User-defined transformation logic
    // TODO: Implement based on requirement: {description}

    message.setBody(body)
    return message
}}
"""
        return script

    def generate_xslt(self, source_schema: str, target_schema: str,
                      mappings: list[dict[str, Any]] | None = None) -> str:
        """Generate an XSLT stylesheet for message mapping."""
        mappings = mappings or []
        mapping_blocks = "\n    ".join(
            f'<xsl:template match="/{m.get("source_path", "")}">'
            f'<{m.get("target_field", "")}><xsl:value-of select="."/></{m.get("target_field", "")}></xsl:template>'
            for m in mappings
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <!-- SAP-CUA Generated XSLT -->
    <!-- Source: {source_schema} -->
    <!-- Target: {target_schema} -->

    <xsl:output method="xml" indent="yes"/>

    <!-- Mappings -->
    {mapping_blocks}

</xsl:stylesheet>
"""

    def generate_xpath(self, xml_structure: str, target_field: str) -> str:
        """Generate an XPath expression for a target field."""
        return f"//{target_field.replace('.', '/')}"

    def generate_openapi(self, service_name: str, endpoints: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate an OpenAPI specification for an SAP API proxy."""
        paths: dict[str, Any] = {}
        for ep in endpoints:
            path = ep.get("path", f"/{service_name.lower()}")
            methods = ep.get("methods", ["get"])
            for method in methods:
                paths.setdefault(path, {})[method] = {
                    "summary": ep.get("summary", f"{service_name} {method.upper()}"),
                    "responses": {
                        "200": {"description": "Success"},
                        "400": {"description": "Bad Request"},
                        "401": {"description": "Unauthorized"},
                        "500": {"description": "Server Error"},
                    },
                }
        return {
            "openapi": "3.0.3",
            "info": {"title": f"{service_name} API", "version": "1.0.0"},
            "paths": paths,
        }

    def generate_test_payload(self, target_type: str, sample_values: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate a test payload for a given target type."""
        sample_values = sample_values or {}
        if target_type.lower() in ("odata", "odata_v4"):
            return {
                "d": {
                    "SalesOrder": sample_values.get("sales_order", "0000000001"),
                    "Customer": sample_values.get("customer", "CUST_001"),
                    "Amount": sample_values.get("amount", "100.00"),
                    "Currency": sample_values.get("currency", "USD"),
                    "_type": "SAP.SalesOrder",
                }
            }
        if target_type.lower() == "soap":
            return {
                "soap:Envelope": {
                    "soap:Body": {
                        sample_values.get("operation", "CreateRequest"): sample_values,
                    }
                }
            }
        if target_type.lower() == "json":
            return sample_values or {"key": "value"}
        return sample_values or {}

    def lint_groovy(self, script: str) -> list[str]:
        """Basic linting for Groovy scripts."""
        issues: list[str] = []
        if "processData" not in script:
            issues.append("Missing processData function entry point")
        if "message.setBody" not in script and "message.getBody" not in script:
            issues.append("Script does not access message body")
        if script.count("def ") == 0:
            issues.append("No function definitions found")
        return issues

    def lint_xslt(self, xslt: str) -> list[str]:
        """Basic linting for XSLT."""
        issues: list[str] = []
        if "xsl:stylesheet" not in xslt:
            issues.append("Missing xsl:stylesheet root element")
        if "xsl:template" not in xslt:
            issues.append("No xsl:template definitions found")
        return issues
