"""Sandbox for safely executing generated Groovy code."""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_BLACKLIST_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"System\.exit", re.IGNORECASE), "Calls to System.exit are not allowed"),
    (re.compile(r"ProcessBuilder", re.IGNORECASE), "ProcessBuilder is not allowed"),
    (re.compile(r"Runtime\.getRuntime", re.IGNORECASE), "Runtime.getRuntime is not allowed"),
    (re.compile(r"Class\.forName", re.IGNORECASE), "Dynamic class loading is not allowed"),
    (re.compile(r"new\s+File\(", re.IGNORECASE), "File system writes are restricted to /tmp"),
    (re.compile(r"new\s+FileWriter\(", re.IGNORECASE), "File system writes are restricted to /tmp"),
    (re.compile(r"new\s+FileOutputStream\(", re.IGNORECASE), "File system writes are restricted to /tmp"),
    (re.compile(r"new\s+PrintWriter\(", re.IGNORECASE), "File system writes are restricted to /tmp"),
    (re.compile(r"new\s+URL\(", re.IGNORECASE), "Network calls are not allowed"),
    (re.compile(r"\.openConnection\(", re.IGNORECASE), "Network calls are not allowed"),
    (re.compile(r"Socket\s*\(", re.IGNORECASE), "Network calls are not allowed"),
    (re.compile(r"HttpURLConnection", re.IGNORECASE), "Network calls are not allowed"),
    (re.compile(r"\.execute\(\)", re.IGNORECASE), "Process execution is not allowed"),
    (re.compile(r"GroovyShell|GroovyScriptEngine|ClassLoader", re.IGNORECASE), "Class loading is not allowed"),
    (re.compile(r"\.exec\(", re.IGNORECASE), "Process execution is not allowed"),
]


_WHITELIST_MESSAGE_API: list[re.Pattern[str]] = [
    re.compile(r"message\.getBody"),
    re.compile(r"message\.setBody"),
    re.compile(r"message\.getHeader"),
    re.compile(r"message\.setHeader"),
    re.compile(r"message\.getHeaders"),
    re.compile(r"message\.getProperties"),
    re.compile(r"message\.setProperty"),
]


class GroovySandbox:
    """Validates and executes Groovy scripts with safety guards."""

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout_seconds = timeout_seconds

    def validate_safety(self, script: str) -> tuple[bool, list[str]]:
        """Return (is_safe, list_of_issues)."""
        issues: list[str] = []
        if not script or not script.strip():
            issues.append("Script is empty")
            return False, issues
        for pattern, message in _BLACKLIST_PATTERNS:
            if pattern.search(script):
                issues.append(message)
        # File system writes outside /tmp are not allowed
        file_writes = re.findall(r'new\s+File(?:Writer|OutputStream|PrintWriter)?\s*\(\s*["\']([^"\']+)', script)
        for path in file_writes:
            if not path.startswith("/tmp"):
                issues.append(f"File write outside /tmp: {path}")
        return len(issues) == 0, issues

    def execute(self, script: str) -> tuple[bool, str]:
        """Execute a Groovy script (or python fallback if groovy unavailable)."""
        safe, issues = self.validate_safety(script)
        if not safe:
            return False, "Safety violation: " + "; ".join(issues)

        # Try to find a groovy executable; otherwise run a sandboxed simulation
        groovy = _which("groovy")
        if groovy is None:
            return self._simulate_execution(script)
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".groovy", delete=False, dir="/tmp") as tmp:
                tmp.write(script)
                tmp_path = tmp.name
            try:
                result = subprocess.run(
                    [groovy, tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
                output = result.stdout + (("\n" + result.stderr) if result.stderr else "")
                return result.returncode == 0, output.strip()
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except subprocess.TimeoutExpired:
            return False, "Execution timed out"
        except Exception as exc:
            return False, f"Execution error: {exc}"

    def _simulate_execution(self, script: str) -> tuple[bool, str]:
        """Best-effort fallback when groovy is not available.

        We still enforce the whitelist of Message API calls; if the script
        only touches those, we return a synthetic success output.
        """
        for line in script.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("import "):
                continue
            if stripped.startswith("def "):
                continue
            if any(pat.search(stripped) for pat in _WHITELIST_MESSAGE_API):
                continue
            if stripped.startswith("}") or stripped.startswith("{"):
                continue
            return False, f"Simulator refused line: {stripped}"
        return True, "simulated_execution_ok"


def _which(name: str) -> str | None:
    from shutil import which
    return which(name)
