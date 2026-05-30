"""Sub-agent runner for planner, explorer, coder, and reviewer roles."""

from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.context import compact_output
from personal_dev_assistant.llm.client import ChatClient
from personal_dev_assistant.models import AgentResult

SUPPORTED_ROLES = frozenset({"planner", "explorer", "coder", "reviewer"})

_ROLE_PROMPT_FILES = {
    "planner": "planner_agent.md",
    "explorer": "explorer_agent.md",
    "coder": "coder_agent.md",
    "reviewer": "reviewer_agent.md",
}

_SUBAGENT_RESPONSE_PROTOCOL = """
Respond using this exact protocol:

ROLE: planner
SUMMARY: short summary for the main agent
FINDING: one important observation
FINDING: another observation if needed
RISK_LEVEL: low
NEXT_STEP: concrete next action
""".strip()


class SubAgentRunner:
    """Run specialized sub-agents sequentially through the shared chat client."""

    def __init__(
        self,
        *,
        chat_client: ChatClient,
        app_config: AppConfig,
        prompts_root: str | Path,
        task: str,
        observations: list[str] | None = None,
    ) -> None:
        self._chat_client = chat_client
        self._app_config = app_config
        self._prompts_root = Path(prompts_root)
        self._task = task
        self._observations = observations or []

    def run_roles(self, roles: list[str]) -> list[AgentResult]:
        """Run requested sub-agent roles sequentially."""

        results: list[AgentResult] = []
        for role in roles:
            normalized = role.strip().lower()
            if normalized not in SUPPORTED_ROLES:
                results.append(_unknown_role_result(normalized))
                continue
            results.append(self.run_role(normalized))
        return results

    def run_role(self, role: str) -> AgentResult:
        """Run one sub-agent role and return a compact structured result."""

        messages = self._build_messages(role)
        llm_response = self._chat_client.complete(messages)
        return parse_subagent_response(llm_response.text, default_role=role)

    def _build_messages(self, role: str) -> list[dict[str, str]]:
        prompt_file = _ROLE_PROMPT_FILES[role]
        system_parts = [
            self._load_prompt(prompt_file),
            _SUBAGENT_RESPONSE_PROTOCOL,
        ]
        user_parts = [f"User task:\n{self._task}"]
        if self._observations:
            user_parts.append("Recent compact observations:")
            user_parts.extend(f"- {observation}" for observation in self._observations)

        return [
            {"role": "system", "content": "\n\n".join(part for part in system_parts if part)},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    def _load_prompt(self, filename: str) -> str:
        path = self._prompts_root / "prompts" / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()


def parse_subagent_response(text: str, *, default_role: str = "unknown") -> AgentResult:
    """Parse a sub-agent response into AgentResult."""

    role = default_role
    summary = ""
    findings: list[str] = []
    risk_level = "low"
    recommended_next_step: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().upper()
        value = value.strip()

        if key == "ROLE":
            role = value.lower()
        elif key == "SUMMARY":
            summary = value
        elif key == "FINDING":
            findings.append(value)
        elif key == "RISK_LEVEL":
            risk_level = value.lower()
        elif key == "NEXT_STEP":
            recommended_next_step = value

    if not summary:
        summary = text.strip() or f"{role} completed without summary."

    return AgentResult(
        role=role,
        summary=summary,
        findings=findings,
        risk_level=risk_level,
        recommended_next_step=recommended_next_step,
    )


def compact_agent_result(result: AgentResult, config: AppConfig) -> str:
    """Compact a sub-agent result before returning it to the main agent."""

    parts = [f"{result.role}: {result.summary}"]
    for finding in result.findings:
        parts.append(f"finding: {finding}")
    if result.recommended_next_step:
        parts.append(f"next_step: {result.recommended_next_step}")
    parts.append(f"risk_level: {result.risk_level}")

    raw_text = "\n".join(parts)
    compacted = compact_output(
        raw_text,
        max_chars=config.context.max_subagent_summary_chars,
    )
    return compacted.text


def parse_roles_param(roles_value: str) -> list[str]:
    """Parse a comma-separated ROLES parameter."""

    return [role.strip() for role in roles_value.split(",") if role.strip()]


def _unknown_role_result(role: str) -> AgentResult:
    return AgentResult(
        role=role or "unknown",
        summary=f"Unknown sub-agent role: {role or 'empty'}",
        findings=[f"Supported roles: {', '.join(sorted(SUPPORTED_ROLES))}"],
        risk_level="high",
        recommended_next_step="Use a supported sub-agent role.",
    )
