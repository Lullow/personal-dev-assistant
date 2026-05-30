"""Agent protocol parsing for the main agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentAction:
    """Parsed action from a mock or LLM response."""

    name: str
    params: dict[str, str] = field(default_factory=dict)
    final_response: str | None = None


def parse_agent_action(text: str) -> AgentAction:
    """Parse a simple ACTION-based response protocol."""

    action_name: str | None = None
    params: dict[str, str] = {}
    final_response: str | None = None
    final_lines: list[str] = []
    capture_final = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if capture_final:
                final_lines.append("")
            continue

        upper = line.upper()
        if upper.startswith("ACTION:"):
            action_name = line.split(":", 1)[1].strip().lower()
            capture_final = False
            continue

        if upper.startswith("FINAL:"):
            final_response = line.split(":", 1)[1].strip()
            capture_final = True
            continue

        if capture_final:
            final_lines.append(line)
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            params[key.strip().lower()] = value.strip()

    if final_lines:
        trailing = "\n".join(final_lines).strip()
        final_response = f"{final_response}\n{trailing}".strip() if final_response else trailing

    if action_name is None:
        return AgentAction(name="unknown", params=params, final_response=final_response)

    if action_name == "finish" and final_response is None:
        final_response = params.get("message") or text.strip()

    return AgentAction(name=action_name, params=params, final_response=final_response)
