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
            action_name = line.split(":", 1)[1].strip().lower()
            capture_final = False
            index += 1
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


def _is_field_header(line: str) -> bool:
    upper = line.upper()
    return any(upper.startswith(prefix) for prefix in _FIELD_HEADER_PREFIXES)


def _split_field(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key.strip(), value.strip()
