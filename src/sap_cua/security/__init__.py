"""Secret redaction and security utilities."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN ([A-Z ]*PRIVATE KEY)-----.*?-----END \1-----", re.DOTALL), "REDACTED_PRIVATE_KEY"),
    (re.compile(r"client_secret\s*[:=]\s*.+", re.IGNORECASE), "REDACTED_CLIENT_SECRET"),
    (re.compile(r"password(?:\s+is|\s+was)?\s*[:=]?\s*.+", re.IGNORECASE), "REDACTED_PASSWORD"),
    (re.compile(r"secret\s*[:=]\s*.+", re.IGNORECASE), "REDACTED_SECRET"),
    (re.compile(r"api[_-]?key\s*[:=]\s*.+", re.IGNORECASE), "REDACTED_API_KEY"),
    (re.compile(r"access[_-]?token\s*[:=]\s*.+", re.IGNORECASE), "REDACTED_ACCESS_TOKEN"),
    (re.compile(r"private[_-]?key\s*[:=]\s*.+", re.IGNORECASE), "REDACTED_PRIVATE_KEY"),
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"), "REDACTED_PRIVATE_KEY"),
    (re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "REDACTED_BEARER_TOKEN"),
    (re.compile(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b"), "REDACTED_CARD"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "REDACTED_EMAIL"),
]


def redact_secrets(text: str) -> tuple[str, list[dict[str, Any]]]:
    if not text:
        return text, []
    findings = []
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        matches = list(pattern.finditer(redacted))
        for match in reversed(matches):
            findings.append({"type": replacement, "length": len(match.group(0))})
            redacted = redacted[: match.start()] + replacement + redacted[match.end() :]
    return redacted, findings


_SECRET_KEYS = {
    "password", "passwd", "clientsecret", "secret", "apikey", "accesstoken",
    "refreshtoken", "idtoken", "token", "privatekey", "authorization",
    "proxyauthorization", "cookie", "setcookie", "clientassertion",
}


def sanitize_data(value: Any) -> Any:
    """Return a sanitized JSON-compatible copy without rewriting JSON syntax.

    This handles text and structured fields only. Referenced image pixels require
    a separate image-redaction/review gate before use in training.
    """
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if re.sub(r"[^a-z0-9]", "", str(key).lower()) in _SECRET_KEYS
            else sanitize_data(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_data(item) for item in value]
    if isinstance(value, str):
        # Structured JSON embedded in logs or tool responses needs the same treatment.
        import json
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return json.dumps(sanitize_data(parsed), ensure_ascii=False)
        return redact_secrets(value)[0]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"Unsupported value in sanitized data: {type(value).__name__}")


def scan_file_for_secrets(path: str | Path) -> list[dict[str, Any]]:
    findings = []
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        _, file_findings = redact_secrets(content)
        findings.extend(file_findings)
    except Exception as exc:
        logger.warning("Could not scan %s: %s", path, exc)
    return findings


def validate_no_production_credentials(config: dict[str, Any]) -> list[str]:
    warnings = []
    for key in ("client_secret", "password", "private_key", "access_token"):
        value = config.get(key, "")
        if value and value not in ("", "changeme", os.getenv(f"SAP_{key.upper()}", "")):
            warnings.append(f"Potential production credential in {key}")
    return warnings
