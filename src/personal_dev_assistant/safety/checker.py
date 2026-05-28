"""Safety classification for commands and project paths."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class SafetyDecision(StrEnum):
    """Possible safety classifications."""

    SAFE = "safe"
    RISKY_REQUIRES_CONFIRMATION = "risky_requires_confirmation"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SafetyResult:
    """A structured safety decision with a human-readable reason."""

    decision: SafetyDecision
    reason: str

    @property
    def is_allowed(self) -> bool:
        return self.decision is not SafetyDecision.BLOCKED

    @property
    def requires_confirmation(self) -> bool:
        return self.decision is SafetyDecision.RISKY_REQUIRES_CONFIRMATION


_BLOCKED_PATH_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    "dist",
    "build",
}


def classify_command(command: str) -> SafetyResult:
    """Classify a shell command without executing it."""

    command = command.strip()
    if not command:
        return SafetyResult(SafetyDecision.BLOCKED, "Empty commands are not allowed.")

    shell_control_reason = _shell_control_operator_reason(command)
    if shell_control_reason is not None:
        return SafetyResult(SafetyDecision.BLOCKED, shell_control_reason)

    try:
        tokens = shlex.split(command)
    except ValueError as error:
        return SafetyResult(
            SafetyDecision.BLOCKED,
            f"Command could not be parsed safely: {error}.",
        )

    if not tokens:
        return SafetyResult(SafetyDecision.BLOCKED, "Empty commands are not allowed.")

    blocked_path = _first_blocked_path_token(tokens)
    if blocked_path is not None:
        return SafetyResult(
            SafetyDecision.BLOCKED,
            f"Command targets blocked path `{blocked_path}`.",
        )

    if _contains_shell_to_script_pipe(command):
        return SafetyResult(
            SafetyDecision.BLOCKED,
            "Piping downloaded scripts into a shell is blocked.",
        )

    blocked_reason = _blocked_command_reason(tokens)
    if blocked_reason is not None:
        return SafetyResult(SafetyDecision.BLOCKED, blocked_reason)

    risky_reason = _risky_command_reason(tokens)
    if risky_reason is not None:
        return SafetyResult(
            SafetyDecision.RISKY_REQUIRES_CONFIRMATION,
            risky_reason,
        )

    if _is_safe_command(tokens):
        return SafetyResult(SafetyDecision.SAFE, "Command is in the safe allowlist.")

    return SafetyResult(
        SafetyDecision.RISKY_REQUIRES_CONFIRMATION,
        "Command is not in the safe allowlist and requires confirmation.",
    )


def check_path_safety(path: str) -> SafetyResult:
    """Check whether a project-relative path is allowed by the safety policy."""

    if not path or not path.strip():
        return SafetyResult(SafetyDecision.BLOCKED, "Empty paths are not allowed.")

    normalized = _normalize_path(path)
    parts = PurePosixPath(normalized).parts

    for part in parts:
        if part == ".env.example":
            continue
        if part == ".env" or (part.startswith(".env.") and part != ".env.example"):
            return SafetyResult(
                SafetyDecision.BLOCKED,
                f"Path `{path}` targets blocked environment file `{part}`.",
            )
        if part in _BLOCKED_PATH_PARTS:
            return SafetyResult(
                SafetyDecision.BLOCKED,
                f"Path `{path}` contains blocked path segment `{part}`.",
            )

    return SafetyResult(SafetyDecision.SAFE, "Path is allowed.")


def _blocked_command_reason(tokens: list[str]) -> str | None:
    command = tokens[0]

    if command == "sudo":
        return "`sudo` is blocked."
    if command in {"mkfs", "dd", "mount", "umount"}:
        return f"`{command}` is blocked."
    if command == "rm" and _has_recursive_or_force_flag(tokens):
        return "`rm` with recursive or force flags is blocked."
    if command in {"chmod", "chown"} and _has_recursive_flag(tokens):
        return f"`{command}` with recursive flags is blocked."
    if command == "git":
        return _blocked_git_reason(tokens)

    return None


def _blocked_git_reason(tokens: list[str]) -> str | None:
    if len(tokens) < 2:
        return None

    subcommand = tokens[1]
    if subcommand == "reset" and "--hard" in tokens[2:]:
        return "`git reset --hard` is blocked."
    if subcommand == "clean":
        return "`git clean` is blocked."
    if subcommand == "checkout" and "--" in tokens[2:]:
        return "`git checkout --` is blocked."
    if subcommand == "push" and any(token.startswith("--force") or token == "-f" for token in tokens[2:]):
        return "`git push --force` is blocked."

    return None


def _risky_command_reason(tokens: list[str]) -> str | None:
    command = tokens[0]

    if command == "pip" and _contains_token(tokens[1:], "install"):
        return "`pip install` requires confirmation."
    if command == "python" and tokens[1:4] == ["-m", "pip", "install"]:
        return "`python -m pip install` requires confirmation."
    if command in {"npm", "pnpm", "yarn"} and _contains_token(tokens[1:], "install"):
        return f"`{command} install` requires confirmation."
    if command == "git" and len(tokens) > 1 and tokens[1] in {"commit", "push", "merge", "rebase"}:
        return f"`git {tokens[1]}` requires confirmation."
    if any(token in {">", ">>", "2>", "2>>"} for token in tokens):
        return "Commands that write output to files require confirmation."
    if command in {"cp", "mv", "mkdir", "rmdir"}:
        return f"`{command}` can change files and requires confirmation."
    if command == "python" and _looks_like_python_script_run(tokens):
        return "Running repository scripts requires confirmation."

    return None


def _is_safe_command(tokens: list[str]) -> bool:
    command = tokens[0]

    if command == "pwd" and len(tokens) == 1:
        return True
    if command == "ls":
        return True
    if command == "pytest":
        return True
    if command == "python" and tokens[1:] == ["--version"]:
        return True
    if command == "python" and len(tokens) >= 3 and tokens[1:3] == ["-m", "pytest"]:
        return True
    if command == "python" and len(tokens) >= 3 and tokens[1:3] == ["-m", "compileall"]:
        return True

    return False


def _contains_shell_to_script_pipe(command: str) -> bool:
    normalized = " ".join(command.lower().split())
    return ("curl" in normalized or "wget" in normalized) and (
        "| sh" in normalized
        or "| bash" in normalized
        or "| /bin/sh" in normalized
        or "| /bin/bash" in normalized
    )


def _shell_control_operator_reason(command: str) -> str | None:
    if "`" in command:
        return "Command substitution with backticks is blocked."
    if "$(" in command:
        return "Command substitution with `$(` is blocked."
    if "&&" in command:
        return "Shell chaining with `&&` is blocked."
    if "||" in command:
        return "Shell chaining with `||` is blocked."
    if ";" in command:
        return "Shell command separators with `;` are blocked."
    if "|" in command:
        if _contains_shell_to_script_pipe(command):
            return "Piping downloaded scripts into a shell is blocked."
        return "Shell pipes are blocked by default."
    return None


def _first_blocked_path_token(tokens: list[str]) -> str | None:
    for token in tokens:
        if token in {">", ">>", "2>", "2>>", "|", "&&", "||", ";"}:
            continue
        result = check_path_safety(token)
        if result.decision is SafetyDecision.BLOCKED:
            return token
    return None


def _has_recursive_or_force_flag(tokens: list[str]) -> bool:
    return any(
        token.startswith("-") and ("r" in token.lower() or "f" in token.lower())
        for token in tokens[1:]
    )


def _has_recursive_flag(tokens: list[str]) -> bool:
    return any(
        token == "-R" or (token.startswith("-") and "r" in token.lower())
        for token in tokens[1:]
    )


def _contains_token(tokens: list[str], expected: str) -> bool:
    return any(token == expected for token in tokens)


def _looks_like_python_script_run(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    target = tokens[1]
    return not target.startswith("-") and target.endswith(".py")


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized
