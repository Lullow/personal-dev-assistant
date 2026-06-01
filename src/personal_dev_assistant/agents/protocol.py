"""Agent protocol parsing for the main agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field

_BLOCK_FIELD_NAMES = frozenset({"old_text", "new_text", "reason"})
_FIELD_HEADER_PREFIXES = (
    "ACTION:",
    "PATH:",
    "COMMAND:",
    "ROLES:",
    "FINAL:",
    "OLD_TEXT:",
    "NEW_TEXT:",
    "REASON:",
)

# Longest names first so "list_project_files" wins over shorter prefixes.
_KNOWN_ACTION_NAMES: tuple[str, ...] = (
    "list_project_files",
    "propose_edit",
    "read_file",
    "partial_edit",
    "subagents",
    "finish",
    "bash",
)

# Inline parameter aliases allowed on the ACTION line for specific actions.
_ACTION_INLINE_PARAM_KEYS: dict[str, tuple[str, ...]] = {
    "bash": ("command",),
    "read_file": ("path",),
    "propose_edit": ("path",),
}


@dataclass(frozen=True)
class AgentAction:
    """Parsed action from a mock or LLM response."""

    name: str
    params: dict[str, str] = field(default_factory=dict)
    final_response: str | None = None


def parse_agent_action(text: str) -> AgentAction:
    """Parse a simple ACTION-based response protocol."""

    lines = text.splitlines()
    action_name: str | None = None
    params: dict[str, str] = {}
    final_response: str | None = None
    final_lines: list[str] = []
    capture_final = False

    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()

        if not line:
            if capture_final:
                final_lines.append("")
            index += 1
            continue

        upper = line.upper()
        if upper.startswith("ACTION:"):
            parsed_name, inline_params, index = _parse_action_line(line, lines, index)
            action_name = parsed_name
            params.update(inline_params)
            capture_final = False
            continue

        if upper.startswith("FINAL:"):
            final_response = line.split(":", 1)[1].strip()
            capture_final = True
            index += 1
            continue

        if capture_final:
            final_lines.append(line)
            index += 1
            continue

        if _is_field_header(line):
            key, inline_value = _split_field(line)
            key_lower = key.lower()
            if key_lower in _BLOCK_FIELD_NAMES and inline_value == "":
                index += 1
                block_lines: list[str] = []
                while index < len(lines):
                    next_raw = lines[index]
                    next_line = next_raw.strip()
                    if next_line and _is_field_header(next_line):
                        break
                    block_lines.append(next_raw.rstrip("\n"))
                    index += 1
                params[key_lower] = "\n".join(block_lines)
                continue

            params[key_lower] = inline_value
            index += 1
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            params[key.strip().lower()] = value.strip()
        index += 1

    if final_lines:
        trailing = "\n".join(final_lines).strip()
        final_response = f"{final_response}\n{trailing}".strip() if final_response else trailing

    if action_name is None:
        return AgentAction(name="unknown", params=params, final_response=final_response)

    if action_name == "finish" and final_response is None:
        final_response = params.get("message") or text.strip()

    return AgentAction(name=action_name, params=params, final_response=final_response)


def _parse_action_line(
    line: str,
    lines: list[str],
    index: int,
) -> tuple[str, dict[str, str], int]:
    """Parse ACTION line, tolerating inline parameters and split-line action names."""

    remainder = line.split(":", 1)[1].strip()
    if not remainder:
        lookahead = _parse_action_from_lookahead(lines, index + 1)
        if lookahead is None:
            return "unknown", {}, index + 1
        return lookahead

    action_name, rest = _split_known_action_name(remainder)
    inline_params = _parse_inline_action_params(action_name, rest)
    return action_name, inline_params, index + 1


def _parse_action_from_lookahead(
    lines: list[str],
    start_index: int,
) -> tuple[str, dict[str, str], int] | None:
    """If ACTION: was empty, use the next non-empty line when it is a known action."""

    index = start_index
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        parsed = _parse_action_from_lookahead_line(line)
        if parsed is None:
            return None
        action_name, inline_params = parsed
        return action_name, inline_params, index + 1
    return None


def _parse_action_from_lookahead_line(line: str) -> tuple[str, dict[str, str]] | None:
    """Parse a lookahead line only when it clearly names a known action."""

    stripped = line.strip()
    if not stripped:
        return None

    lower = stripped.lower()
    for known in _KNOWN_ACTION_NAMES:
        if lower == known:
            return known, {}
        if lower.startswith(f"{known} "):
            rest = stripped[len(known) :].strip()
            inline_params = _parse_inline_action_params(known, rest)
            return known, inline_params

    return None


def _split_known_action_name(remainder: str) -> tuple[str, str]:
    """Return action name and trailing text after a known action prefix."""

    lower = remainder.lower()
    for known in _KNOWN_ACTION_NAMES:
        if lower == known:
            return known, ""
        if lower.startswith(f"{known} "):
            return known, remainder[len(known) :].strip()

    parts = remainder.split(None, 1)
    name = parts[0].lower()
    trailing = parts[1].strip() if len(parts) > 1 else ""
    return name, trailing


def _parse_inline_action_params(action_name: str, rest: str) -> dict[str, str]:
    """Extract inline COMMAND:/PATH: aliases from the ACTION line tail."""

    if not rest:
        return {}

    allowed_keys = _ACTION_INLINE_PARAM_KEYS.get(action_name, ())
    rest_lower = rest.lower()
    for key in allowed_keys:
        prefix = f"{key}:"
        if rest_lower.startswith(prefix):
            return {key: rest[len(prefix) :].strip()}
    return {}


def _is_field_header(line: str) -> bool:
    upper = line.upper()
    return any(upper.startswith(prefix) for prefix in _FIELD_HEADER_PREFIXES)


def _split_field(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()
