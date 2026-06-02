"""Command parsing for Interactive Assistant v.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personal_dev_assistant.interactive.intents import IntentClassifier

HELP_TEXT = """
Interactive Assistant v.2 — deterministic session (no API key required)

Commands:
  help                  Show this help
  exit, quit            Leave interactive mode
  list                  List project files safely
  open <path>           Open/read a file into the current session
  read <path>           Alias for open
  show current file     Show the current file path and preview
  review                Review the current file (or demo_project if none open)
  fix                   Create a pending proposed edit for the current file
  /apply                Apply the pending edit after explicit approval
  apply                 Show safety reminder to use /apply
  reject                Clear the pending edit without changing files
  test                  Run pytest on demo_project through the safe bash tool
  tokens                Show token budget / session usage estimate
  compact context       Compact session history while preserving key state

Natural phrases also work (deterministic parsing, not LLM):
  can you / could you / please ... (polite prefixes are stripped)
  list files, show files, show project files
  open <path>, show <path>, cat <path>, inspect <path>
  review it, review this file, can you review it, check it
  fix it, fix bug, fix the bug, repair it
  run tests, run pytest, test it
  show tokens, show token usage, token usage, budget, cost
  compact context, compact history
""".strip()

WELCOME_TITLE = "Personal Dev Assistant — Interactive v.2"
WELCOME_NOTE = (
    "Stateful terminal coding assistant. Open a file, review it, propose a fix, "
    "then apply only when you say so. Type help for commands."
)
READY_MESSAGE = "Ready when you are."

# Longest prefixes first so "please can you" wins over "please".
_POLITE_PREFIXES: tuple[str, ...] = (
    "please can you",
    "can you",
    "could you",
    "please",
)

# Longest phrases first so "show project files" wins over "show files".
_MULTI_WORD_ALIASES: tuple[tuple[str, str], ...] = (
    ("/apply", "apply_confirm"),
    ("show current file", "current"),
    ("review this file", "review"),
    ("compact context", "compact"),
    ("compact history", "compact"),
    ("show project files", "list"),
    ("show token usage", "tokens"),
    ("list files", "list"),
    ("show files", "list"),
    ("token usage", "tokens"),
    ("show tokens", "tokens"),
    ("run pytest", "test"),
    ("run tests", "test"),
    ("fix the bug", "fix"),
    ("fix bug", "fix"),
    ("fix it", "fix"),
    ("review file", "review"),
    ("review it", "review"),
    ("repair it", "fix"),
    ("check it", "review"),
    ("test it", "test"),
)

_SINGLE_WORD_ALIASES: dict[str, str] = {
    "budget": "tokens",
    "cost": "tokens",
    "apply": "apply",
    "reject": "reject",
}

_READ_PREFIXES: frozenset[str] = frozenset({"read", "open", "show", "cat", "inspect"})

# Paths that must not be treated as file reads when using a read-style verb.
_READ_PATH_BLOCKLIST: frozenset[str] = frozenset(
    {
        "files",
        "project files",
        "tokens",
        "token usage",
        "current file",
        "what file we are working on",
        "me what file we are working on",
    }
)

_STRICT_SINGLE_COMMANDS: frozenset[str] = frozenset(
    {
        "help",
        "exit",
        "quit",
        "list",
        "review",
        "fix",
        "/apply",
        "reject",
        "test",
        "tokens",
        "compact",
        "current",
    }
)

_HANDLER_COMMANDS: frozenset[str] = _STRICT_SINGLE_COMMANDS | {"read"}


@dataclass(frozen=True)
class ParsedCommand:
    """One parsed interactive command."""

    name: str
    arg: str | None = None


def _strip_polite_prefix(text: str) -> str:
    stripped = text.strip()
    lower = stripped.lower()
    for prefix in _POLITE_PREFIXES:
        if lower.startswith(prefix):
            remainder = stripped[len(prefix) :].strip()
            if remainder:
                return remainder
    return stripped


def parse_command(line: str) -> ParsedCommand | None:
    """Parse one interactive command line with deterministic natural-language aliases."""

    stripped = line.strip()
    if not stripped:
        return None

    normalized = _strip_polite_prefix(stripped)
    lower = normalized.lower()

    for phrase, command in _MULTI_WORD_ALIASES:
        if lower == phrase:
            return ParsedCommand(name=command)

    if lower in _SINGLE_WORD_ALIASES:
        return ParsedCommand(name=_SINGLE_WORD_ALIASES[lower])

    parts = normalized.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None

    if verb in _READ_PREFIXES and arg is not None and arg.lower() not in _READ_PATH_BLOCKLIST:
        return ParsedCommand(name="read", arg=arg)

    return ParsedCommand(name=verb, arg=arg)


def is_strict_deterministic_match(line: str) -> bool:
    """True when the line is fully resolved by alias or single-token rules."""

    stripped = line.strip()
    if not stripped:
        return False

    normalized = _strip_polite_prefix(stripped)
    lower = normalized.lower()

    for phrase, _command in _MULTI_WORD_ALIASES:
        if lower == phrase:
            return True

    if lower in _SINGLE_WORD_ALIASES:
        return True

    parts = normalized.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None

    if verb in _READ_PREFIXES and arg is not None and arg.lower() not in _READ_PATH_BLOCKLIST:
        return True

    return len(parts) == 1 and verb in _STRICT_SINGLE_COMMANDS


def resolve_command(
    line: str,
    *,
    llm_intents_enabled: bool = False,
    intent_classifier: IntentClassifier | None = None,
) -> tuple[ParsedCommand | None, str | None]:
    """Parse a command line; optionally fall back to LLM intent classification."""

    command = parse_command(line)
    if command is None:
        return None, None

    if not llm_intents_enabled:
        return command, None

    if is_strict_deterministic_match(line):
        return command, None

    if intent_classifier is None:
        from personal_dev_assistant.interactive.intents import _INTENT_UNKNOWN_USER_MESSAGE

        return ParsedCommand(name="unknown"), _INTENT_UNKNOWN_USER_MESSAGE

    from personal_dev_assistant.interactive.intents import (
        _INTENT_UNKNOWN_USER_MESSAGE,
        classification_to_command,
    )

    classification = intent_classifier.classify(line.strip())
    if classification is None:
        return ParsedCommand(name="unknown"), _INTENT_UNKNOWN_USER_MESSAGE

    intent_name, arg, message = classification_to_command(classification)
    if intent_name == "unknown":
        return ParsedCommand(name="unknown"), message

    return ParsedCommand(name=intent_name, arg=arg), None
