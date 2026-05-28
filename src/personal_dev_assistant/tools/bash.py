"""Safe bash command tool."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.context import compact_output
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.safety import SafetyDecision, classify_command


def bash(
    command: str,
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
) -> ToolResult:
    """Run a safe command inside the project root and return compact output."""

    app_config = config or AppConfig()
    safety_result = classify_command(command)

    if safety_result.decision is SafetyDecision.BLOCKED:
        return ToolResult(
            ok=False,
            summary=f"Command blocked: {safety_result.reason}",
            output={
                "command": command,
                "safety_decision": safety_result.decision.value,
                "reason": safety_result.reason,
                "executed": False,
            },
        )

    if safety_result.decision is SafetyDecision.RISKY_REQUIRES_CONFIRMATION:
        return ToolResult(
            ok=False,
            summary=f"Command requires user confirmation: {safety_result.reason}",
            output={
                "command": command,
                "safety_decision": safety_result.decision.value,
                "reason": safety_result.reason,
                "requires_confirmation": True,
                "executed": False,
            },
        )

    root = Path(project_root).resolve()
    if not root.exists() or not root.is_dir():
        return ToolResult(
            ok=False,
            summary="Command blocked: project root does not exist or is not a directory.",
            output={"command": command, "project_root": str(root), "executed": False},
        )

    try:
        args = shlex.split(command)
    except ValueError as error:
        return ToolResult(
            ok=False,
            summary=f"Command blocked: could not parse command safely: {error}.",
            output={"command": command, "executed": False},
        )

    executable_args = _resolve_safe_executable(args)

    try:
        completed = subprocess.run(
            executable_args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=app_config.tools.command_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = _normalize_timeout_output(error.stdout)
        stderr = _normalize_timeout_output(error.stderr)
        return _command_result(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=None,
            config=app_config,
            ok=False,
            summary=(
                "Command timed out after "
                f"{app_config.tools.command_timeout_seconds} seconds: {command}"
            ),
            timed_out=True,
        )
    except OSError as error:
        return ToolResult(
            ok=False,
            summary=f"Command failed to start: {error}",
            output={"command": command, "executed": False},
        )

    return _command_result(
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        config=app_config,
        ok=completed.returncode == 0,
        summary=f"Command exited with code {completed.returncode}: {command}",
        timed_out=False,
    )


def _command_result(
    *,
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    config: AppConfig,
    ok: bool,
    summary: str,
    timed_out: bool,
) -> ToolResult:
    compact_stdout = compact_output(stdout, config=config)
    compact_stderr = compact_output(stderr, config=config)

    return ToolResult(
        ok=ok,
        summary=summary,
        output={
            "command": command,
            "stdout": compact_stdout.text,
            "stderr": compact_stderr.text,
            "stdout_original_char_count": compact_stdout.original_char_count,
            "stdout_compacted_char_count": compact_stdout.compacted_char_count,
            "stderr_original_char_count": compact_stderr.original_char_count,
            "stderr_compacted_char_count": compact_stderr.compacted_char_count,
            "timed_out": timed_out,
            "executed": True,
        },
        exit_code=exit_code,
        truncated=compact_stdout.truncated or compact_stderr.truncated,
    )


def _normalize_timeout_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def _resolve_safe_executable(args: list[str]) -> list[str]:
    if not args:
        return args
    if args[0] == "python":
        return [sys.executable, *args[1:]]
    if args[0] == "pytest":
        return [sys.executable, "-m", "pytest", *args[1:]]
    return args
