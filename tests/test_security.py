"""Unit tests for security redaction."""

from __future__ import annotations

import pytest

from sap_cua.security import redact_secrets, validate_no_production_credentials


def test_redact_password():
    text = "The password is secret123"
    redacted, findings = redact_secrets(text)
    assert "REDACTED_PASSWORD" in redacted
    assert "secret123" not in redacted


def test_redact_api_key():
    text = "api_key: sk-abc123def456"
    redacted, findings = redact_secrets(text)
    assert "REDACTED_API_KEY" in redacted
    assert "sk-abc123def456" not in redacted


def test_redact_bearer_token():
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9..."
    redacted, findings = redact_secrets(text)
    assert "REDACTED_BEARER_TOKEN" in redacted


def test_redact_client_secret():
    text = "client_secret=my_super_secret"
    redacted, findings = redact_secrets(text)
    assert "REDACTED_CLIENT_SECRET" in redacted


def test_redact_email():
    text = "Contact user@example.com for details"
    redacted, findings = redact_secrets(text)
    assert "REDACTED_EMAIL" in redacted


def test_clean_text():
    text = "This is a normal sentence."
    redacted, findings = redact_secrets(text)
    assert redacted == text
    assert len(findings) == 0


def test_no_production_credentials_clean():
    warnings = validate_no_production_credentials({
        "client_id": "test",
        "client_secret": "changeme",
    })
    assert len(warnings) == 0


def test_no_production_credentials_present():
    warnings = validate_no_production_credentials({
        "client_secret": "real-secret-12345",
    })
    assert len(warnings) > 0