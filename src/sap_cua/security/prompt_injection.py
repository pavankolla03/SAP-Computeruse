""" defense — detect, sanitize, and neutralize malicious content."""

from __future__ import annotations

import base64
import re
import string
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InjectionPattern:
    """A single prompt-injection signature."""

    pattern: re.Pattern[str]
    description: str
    severity: str  # low | medium | high | critical


class PromptInjectionDefense:
    """Defense-in-depth against prompt-injection attacks in external content."""

    # Patterns are evaluated in declaration order (most specific first).
    _PATTERNS: list[InjectionPattern] = [
        InjectionPattern(
            pattern=re.compile(
                r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE
            ),
            description="Ignore previous instructions",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"you\s+are\s+(now|going\s+to|about\s+to)\s+", re.IGNORECASE
            ),
            description="Role override — 'you are now'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(r"\bact\s+as\b", re.IGNORECASE),
            description="Role override — 'act as'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(r"pretend\s+you\s+are\b", re.IGNORECASE),
            description="Role override — 'pretend you are'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"reveal\s+your\s+(full\s+)?instructions?", re.IGNORECASE
            ),
            description="Instruction exfiltration — 'reveal your instructions'",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"output\s+your\s+(full\s+)?instructions?", re.IGNORECASE
            ),
            description="Instruction exfiltration — 'output your instructions'",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"disregard\s+(all\s+)?(previous\s+)?safety", re.IGNORECASE
            ),
            description="Safety bypass — 'disregard safety'",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(r"\boverride\s+(the\s+)?policy\b", re.IGNORECASE),
            description="Policy override — 'override policy'",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(r"\boverride\s+(all\s+)?rules?\b", re.IGNORECASE),
            description="Rules override — 'override rules'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(r"\boverride\s+(the\s+)?system\b", re.IGNORECASE),
            description="System override — 'override system'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"\b(jailbreak|break\s+(out\s+of\s+)?(the\s+)?(jail|system|sandbox))\b",
                re.IGNORECASE,
            ),
            description="Jailbreak attempt",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(r"\bDAN\b", re.IGNORECASE),
            description="DAN-style attack",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"do\s+anything\s+now", re.IGNORECASE
            ),
            description="DAN-style — 'do anything now'",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"developer\s+mode", re.IGNORECASE
            ),
            description="Developer mode override",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"debug\s+mode", re.IGNORECASE
            ),
            description="Debug mode override",
            severity="medium",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"sudo\s+mode", re.IGNORECASE
            ),
            description="Sudo/superuser mode override",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"ignore\s+(all\s+)?(of\s+)?the\s+(above|previous)", re.IGNORECASE
            ),
            description="Ignore above/previous",
            severity="critical",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"new\s+instruction[:\s]+", re.IGNORECASE
            ),
            description="New instruction injection",
            severity="high",
        ),
        InjectionPattern(
            pattern=re.compile(
                r"system\s+prompt[:\s]+", re.IGNORECASE
            ),
            description=" injection",
            severity="high",
        ),
    ]

    # Source-type -> sanitization wrapper label
    _SOURCE_LABELS: dict[str, str] = {
        "mpl": "[MPL — untrusted input]",
        "payload": "[Payload — untrusted input]",
        "api_response": "[API response — untrusted input]",
        "log": "[Log — untrusted input]",
    }

    # ------------------------------------------------------------------
    # Core scanning
    # ------------------------------------------------------------------
    def scan(self, text: str) -> list[dict[str, Any]]:
        """Scan *text* for prompt-injection patterns.

        Returns a list of dicts with keys:
            - ``pattern`` (str): regex that matched
            - ``description`` (str): human description of the pattern
            - ``severity`` (str): low/medium/high/critical
            - ``position`` (tuple[int, int]): start/end offsets
            - ``sanitized`` (str): cleaned replacement text
        """
        if not text:
            return []

        findings: list[dict[str, Any]] = []
        for inj in self._PATTERNS:
            for match in inj.pattern.finditer(text):
                findings.append(
                    {
                        "pattern": inj.pattern.pattern,
                        "description": inj.description,
                        "severity": inj.severity,
                        "position": (match.start(), match.end()),
                        "sanitized": "[REDACTED]",
                    }
                )

        # Also check decoded base64 payloads
        for decoded in self._decode_base64_candidates(text):
            for inj in self._PATTERNS:
                if inj.pattern.search(decoded):
                    findings.append(
                        {
                            "pattern": inj.pattern.pattern,
                            "description": inj.description + " (base64-encoded)",
                            "severity": inj.severity,
                            "position": (-1, -1),
                            "sanitized": "[REDACTED]",
                        }
                    )

        # Deduplicate by (description, severity)
        seen: set[tuple[str, str]] = set()
        unique: list[dict[str, Any]] = []
        for f in findings:
            key = (f["description"], f["severity"])
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _decode_base64_candidates(self, text: str) -> list[str]:
        """Extract and decode plausible base64 tokens from *text*."""
        results: list[str] = []
        # Match contiguous groups of base64 chars at least 20 chars long
        b64_re = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
        for token in b64_re.findall(text):
            try:
                decoded = base64.b64decode(token, validate=True).decode(
                    "utf-8", errors="replace"
                )
                if decoded.strip():
                    results.append(decoded)
            except Exception:
                pass
        return results

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------
    def sanitize(self, text: str) -> str:
        """Replace detected injections in *text* with ``[REDACTED]`` and return clean text."""
        if not text:
            return text

        cleaned = text
        for inj in self._PATTERNS:
            cleaned = inj.pattern.sub("[REDACTED]", cleaned)
        # Also sanitize decoded base64 payloads if any are embedded
        b64_re = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
        for token in b64_re.findall(cleaned):
            try:
                decoded = base64.b64decode(token, validate=True).decode(
                    "utf-8", errors="replace"
                )
                sanitized_decoded = decoded
                for inj2 in self._PATTERNS:
                    sanitized_decoded = inj2.pattern.sub("[REDACTED]", sanitized_decoded)
                if sanitized_decoded != decoded:
                    cleaned = cleaned.replace(token, "[REDACTED_BASE64]")
            except Exception:
                pass
        return cleaned

    # ------------------------------------------------------------------
    # Quick check
    # ------------------------------------------------------------------
    def is_suspicious(self, text: str) -> bool:
        """Return ``True`` if *text* contains any prompt-injection pattern."""
        return bool(self.scan(text))

    # ------------------------------------------------------------------
    # External-content wrapper
    # ------------------------------------------------------------------
    def redact_external_content(self, text: str, source_type: str) -> str:
        """Wrap *text* with a safety label and sanitize based on *source_type*.

        Supported *source_type* values: ``mpl``, ``payload``, ``api_response``, ``log``.

        Args:
            text: The raw external content.
            source_type: Category of the external source.

        Returns:
            Sanitized text with a source-type label prepended.
        """
        label = self._SOURCE_LABELS.get(source_type.lower(), "[Untrusted external content]")
        sanitized = self.sanitize(text)
        return f"{label}\n{sanitized}"
