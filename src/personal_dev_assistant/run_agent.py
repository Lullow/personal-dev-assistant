"""Experimental LLM-driven agent runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from personal_dev_assistant.agents.main import (
    EXPERIMENTAL_ACTION_PROTOCOL,
    EXPERIMENTAL_ALLOWED_ACTIONS,
    AgentStepRecord,
    MainAgent,
    MainAgentResult,
)
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.budget.monitor import TokenBudgetStatus
from personal_dev_assistant.config import RuntimeConfig
from personal_dev_assistant.llm.client import ChatClient, MissingApiKeyError, create_chat_client

EXPERIMENTAL_BANNER = """
======================================================================
*** EXPERIMENTAL LLM AGENT MODE ***
Optional live LLM path — NOT the primary demo route.
Use `personal-dev-assistant chat` or the deterministic demo without an API key.
======================================================================
""".strip()

_EXPERIMENTAL_NOTES = """
Requires OPENAI_API_KEY. Uses MainAgent with read/list/bash/propose_edit/finish only.
Proposed edits are validated + reviewer-gated. Apply only with --apply-proposed-edits
(low/medium risk). High-risk proposals are never auto-applied. partial_edit/subagents
remain blocked for direct LLM use.
""".strip()


@dataclass(frozen=True)
class ExperimentalRunResult:
    """CLI-friendly wrapper around a main-agent run."""

    agent_result: MainAgentResult
    model: str
    task: str
    apply_proposed_edits: bool
    budget_status: TokenBudgetStatus
    experimental: bool = True


def run_experimental_llm_agent(
    task: str,
    *,
    runtime_config: RuntimeConfig,
    project_root: str | Path = ".",
    prompts_root: str | Path | None = None,
    chat_client: ChatClient | None = None,
    max_steps: int = 10,
    apply_proposed_edits: bool = False,
) -> ExperimentalRunResult:
    """Run MainAgent in restricted experimental LLM mode."""

    monitor = TokenBudgetMonitor(runtime_config.app)
    client = chat_client
    if client is None:
        if not runtime_config.environment.has_openai_api_key:
            raise MissingApiKeyError(
                "OPENAI_API_KEY is required for experimental LLM mode. "
                "Use the deterministic demo or chat mode without an API key."
            )
        client = create_chat_client(
            runtime_config,
            budget_monitor=monitor,
            mode="openai",
        )

    root = Path(project_root).resolve()
    agent = MainAgent(
        runtime_config=runtime_config,
        chat_client=client,
        project_root=root,
        budget_monitor=monitor,
        max_steps=max_steps,
        prompts_root=prompts_root or root,
        allowed_actions=EXPERIMENTAL_ALLOWED_ACTIONS,
        stop_on_invalid_action=True,
        action_protocol=EXPERIMENTAL_ACTION_PROTOCOL,
        apply_proposed_edits=apply_proposed_edits,
    )
    result = agent.run(task)
    return ExperimentalRunResult(
        agent_result=result,
        model=runtime_config.app.model,
        task=task,
        apply_proposed_edits=apply_proposed_edits,
        budget_status=monitor.status(),
    )


def format_experimental_output(result: ExperimentalRunResult) -> str:
    """Format experimental run output for the terminal."""

    lines: list[str] = [
        EXPERIMENTAL_BANNER,
        "",
        _EXPERIMENTAL_NOTES,
        "",
        f"Task: {result.task}",
        f"Model: {result.model}",
        f"Apply proposed edits: {'yes' if result.apply_proposed_edits else 'no (review only)'}",
        "",
        "=" * 70,
        "AGENT TRACE",
        "=" * 70,
    ]

    agent_result = result.agent_result
    if agent_result.step_records:
        for record in agent_result.step_records:
            lines.extend(_format_step_record(record))
            lines.append("")
    elif agent_result.observations:
        for index, observation in enumerate(agent_result.observations, start=1):
            lines.append(f"--- Step {index} (legacy trace) ---")
            lines.extend(_render_observation_lines("tool", observation))
            lines.append("")
    else:
        lines.append("(no tool steps — model finished immediately)")
        lines.append("")

    lines.extend(
        [
            "=" * 70,
            "RUN SUMMARY",
            "=" * 70,
            f"Stopped reason: {agent_result.stopped_reason}",
            f"LLM steps: {agent_result.steps}",
            "",
            "=" * 70,
            "TOKEN BUDGET",
            "=" * 70,
        ]
    )
    lines.extend(_format_budget_status(result.budget_status))
    lines.extend(
        [
            "",
            "=" * 70,
            "FINAL ANSWER",
            "=" * 70,
            agent_result.final_response,
        ]
    )
    return "\n".join(lines)


def _format_step_record(record: AgentStepRecord) -> list[str]:
    lines = [
        f"--- Step {record.step} ---",
        f"  [LLM DECISION] ACTION: {record.action}",
    ]
    if record.action_detail:
        lines.append(f"                 {record.action_detail}")

    if record.action == "finish":
        return lines

    if record.observation:
        lines.extend(_render_observation_lines(record.action, record.observation))
    return lines


def _render_observation_lines(action: str, observation: str) -> list[str]:
    """Split compact observations into tool / safety / reviewer sections."""

    if action == "propose_edit":
        return _render_propose_edit_observation(observation)

    lowered = observation.lower()
    if action == "bash" and "blocked" in lowered:
        return [f"  [SAFETY] {observation}"]

    if "blocked" in lowered and action != "propose_edit":
        return [f"  [SAFETY] {observation}"]

    return [f"  [TOOL RESULT] {observation}"]


def _render_propose_edit_observation(observation: str) -> list[str]:
    fields = _parse_observation_fields(observation)
    prefix, summary = _split_tool_summary(observation, fields)

    lines: list[str] = []
    if summary:
        lines.append(f"  [TOOL RESULT] {prefix}: {summary}")

    reviewer_parts: list[str] = []
    for key in ("risk_level", "reviewer_summary", "recommendation", "valid", "applied"):
        if key in fields:
            reviewer_parts.append(f"{key}={fields[key]}")
    if "mini_diff" in fields:
        reviewer_parts.append("mini_diff present — see diff below")
        lines.append("  [REVIEWER]")
        for part in reviewer_parts:
            lines.append(f"    {part}")
        for diff_line in fields["mini_diff"].splitlines():
            lines.append(f"    {diff_line}")
    elif reviewer_parts:
        lines.append("  [REVIEWER]")
        for part in reviewer_parts:
            lines.append(f"    {part}")

    if not lines:
        lines.append(f"  [TOOL RESULT] {observation}")
    return lines


def _parse_observation_fields(observation: str) -> dict[str, str]:
    """Parse `key: value` lines from a compact tool observation."""

    fields: dict[str, str] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_key, buffer
        if current_key is not None:
            fields[current_key] = "\n".join(buffer).strip()
        current_key = None
        buffer = []

    for line in observation.splitlines():
        if ":" in line and not line.startswith(" "):
            head, _, tail = line.partition(":")
            key = head.strip()
            if key in {
                "path",
                "stdout",
                "stderr",
                "content",
                "files",
                "mini_diff",
                "apply_hint",
                "risk_level",
                "reviewer_summary",
                "recommendation",
                "valid",
                "applied",
            }:
                flush()
                current_key = key
                buffer = [tail.strip()] if tail.strip() else []
                continue
        if current_key is not None:
            buffer.append(line)
        elif not fields and ":" in line:
            # First line is `tool: summary` — handled separately.
            pass

    flush()
    return fields


def _split_tool_summary(observation: str, fields: dict[str, str]) -> tuple[str, str]:
    first_line = observation.splitlines()[0] if observation else ""
    if ":" in first_line:
        prefix, _, summary = first_line.partition(":")
        return prefix.strip(), summary.strip()
    return "tool", first_line


def _format_budget_status(status: TokenBudgetStatus) -> list[str]:
    lines = [
        f"  Total tokens used: {status.total_tokens_used}",
        f"  Input tokens used: {status.input_tokens_used}",
        f"  Output tokens used: {status.output_tokens_used}",
        f"  Remaining budget: {status.remaining_tokens}",
        f"  Budget used: {status.percentage_used:.1%}",
        f"  Estimated cost (USD): ${status.estimated_cost_usd:.6f}",
    ]
    if status.warning_reached:
        lines.append("  Warning: budget warning threshold reached.")
    if status.hard_cap_reached:
        lines.append("  Warning: hard cap reached.")
    if status.message:
        lines.append(f"  {status.message}")
    return lines
