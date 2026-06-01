"""Experimental LLM-driven agent runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from personal_dev_assistant.agents.main import (
    EXPERIMENTAL_ACTION_PROTOCOL,
    EXPERIMENTAL_ALLOWED_ACTIONS,
    MainAgent,
    MainAgentResult,
)
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import RuntimeConfig
from personal_dev_assistant.llm.client import ChatClient, MissingApiKeyError, create_chat_client

EXPERIMENTAL_BANNER = """
*** EXPERIMENTAL LLM AGENT MODE ***
Optional live LLM path — not the primary demo route.
Requires OPENAI_API_KEY. Uses MainAgent with safe read/list/bash/propose_edit/finish.
Proposed edits are validated and reviewed by default; only low/medium-risk proposals
can be applied with --apply-proposed-edits (via partial_edit). High-risk proposals are never auto-applied.
partial_edit and subagents remain disabled for direct LLM use.
""".strip()


@dataclass(frozen=True)
class ExperimentalRunResult:
    """CLI-friendly wrapper around a main-agent run."""

    agent_result: MainAgentResult
    model: str
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
    return ExperimentalRunResult(agent_result=result, model=runtime_config.app.model)


def format_experimental_output(result: ExperimentalRunResult) -> str:
    """Format experimental run output for the terminal."""

    agent_result = result.agent_result
    lines = [
        EXPERIMENTAL_BANNER,
        "",
        f"Model: {result.model}",
        f"Stopped reason: {agent_result.stopped_reason}",
        f"Steps: {agent_result.steps}",
        "",
        "Final response:",
        agent_result.final_response,
    ]
    if agent_result.observations:
        lines.extend(["", "Observations:"])
        lines.extend(f"- {observation}" for observation in agent_result.observations)
    return "\n".join(lines)
