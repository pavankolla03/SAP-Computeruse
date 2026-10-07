"""Terminal executor — runs shell commands safely via shlex."""

from __future__ import annotations

import asyncio
import logging
import shlex
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class CommandTimeoutError(TimeoutError):
    """Raised when a command exceeds its timeout."""


class CommandNotAllowedError(PermissionError):
    """Raised when a command is rejected by ``allowed_commands``."""


class TerminalExecutor:
    """Run shell commands in a controlled manner.

    By default commands are parsed with :func:`shlex.split` and executed
    **without** a shell to avoid injection attacks.  Pass ``shell=True``
    only when you really need shell features (e.g. pipes, globs).
    """

    def __init__(
        self,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        allowed_commands: list[str] | None = None,
        default_timeout: float = 60.0,
        shell: bool = False,
    ) -> None:
        self.cwd = cwd
        self.env = env
        self.allowed_commands = allowed_commands
        self.default_timeout = default_timeout
        self.shell = shell

    # ─── Sync execution ────────────────────────────────────────────────────

    def run(
        self,
        command: str,
        timeout: float | None = None,
        check: bool = False,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Run a shell command synchronously.

        Returns
        -------
        dict with keys ``stdout``, ``stderr``, ``returncode``, ``success``.
        """
        args = self._prepare_command(command)
        effective_timeout = timeout if timeout is not None else self.default_timeout
        effective_cwd = cwd or self.cwd

        logger.debug("running %r (timeout=%s)", args, effective_timeout)
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=check,
                cwd=effective_cwd,
                env=self.env,
                shell=self.shell,
            )
            return {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
                "success": completed.returncode == 0,
                "command": command,
            }
        except subprocess.TimeoutExpired as exc:
            logger.error("Command %r timed out after %ss", command, effective_timeout)
            raise CommandTimeoutError(
                f"Command {command!r} timed out after {effective_timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            logger.error("Command not found: %s", exc)
            return {
                "stdout": "",
                "stderr": str(exc),
                "returncode": 127,
                "success": False,
                "command": command,
            }

    # ─── Async execution ───────────────────────────────────────────────────

    async def run_async(
        self,
        command: str,
        timeout: float | None = None,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Run a shell command asynchronously using asyncio.create_subprocess_exec."""
        args = self._prepare_command(command)
        effective_timeout = timeout if timeout is not None else self.default_timeout
        effective_cwd = cwd or self.cwd

        logger.debug("running async %r (timeout=%s)", args, effective_timeout)
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_cwd,
                env=self.env,
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(), timeout=effective_timeout
            )
            return {
                "stdout": (stdout_b or b"").decode(errors="replace"),
                "stderr": (stderr_b or b"").decode(errors="replace"),
                "returncode": process.returncode or 0,
                "success": (process.returncode or 0) == 0,
                "command": command,
            }
        except asyncio.TimeoutError as exc:
            try:
                process.kill()
            except Exception:
                pass
            raise CommandTimeoutError(
                f"Command {command!r} timed out after {effective_timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            return {
                "stdout": "",
                "stderr": str(exc),
                "returncode": 127,
                "success": False,
                "command": command,
            }

    # ─── Internals ────────────────────────────────────────────────────────

    def _prepare_command(self, command: str) -> list[str]:
        """Validate and parse a command string.

        - ``shell=False`` ⇒ always split with :func:`shlex.split` (no injection).
        - ``allowed_commands`` is checked against the program name.
        """
        if self.shell:
            # Even when shell=True, the user has opted in explicitly.
            return [command]

        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"Invalid command string: {command!r}") from exc

        if not tokens:
            raise ValueError(f"Empty command: {command!r}")

        if self.allowed_commands is not None:
            program = tokens[0]
            if program not in self.allowed_commands:
                raise CommandNotAllowedError(
                    f"Command '{program}' is not in the allow-list: "
                    f"{self.allowed_commands}"
                )

        return tokens