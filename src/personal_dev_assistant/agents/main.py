"""Main agent loop for Personal Dev Assistant."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from personal_dev_assistant.agents.protocol import AgentAction, parse_agent_action
from personal_dev_assistant.agents.subagents import (
    SubAgentRunner,
    compact_agent_result,
    parse_roles_param,
)
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, RuntimeConfig
from personal_dev_assistant.context import compact_output
from personal_dev_assistant.llm.client import BudgetExceededError, ChatClient
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.tools import bash, list_project_files, partial_edit, propose_edit, read_file

DEFAULT_MAX_STEPS = 10

EXPERIMENTAL_ALLOWED_ACTIONS = frozenset(
    {"read_file", "list_project_files", "bash", "finish", "propose_edit"}
)

_ACTION_PROTOCOL = """
Respond using this exact protocol:

ACTION: read_file
PATH: relative/path

ACTION: list_project_files

ACTION: bash
COMMAND: safe command here

ACTION: partial_edit
PATH: relative/path
OLD_TEXT: exact text
NEW_TEXT: replacement text
REASON: why

ACTION: subagents
ROLES: planner, explorer, coder, reviewer

ACTION: finish
FINAL: concise final response to the user
""".strip()

EXPERIMENTAL_ACTION_PROTOCOL = """
Experimental LLM mode — strict action protocol

CRITICAL FORMAT RULES:
- Reply with exactly ONE ACTION block per turn.
- Do NOT write prose, markdown headings, or explanations before ACTION.
- The first non-empty line of your reply MUST start with: ACTION:
- Use only the allowed actions listed below.
- Do NOT use partial_edit or subagents.

Allowed actions only:
- list_project_files
- read_file
- bash
- propose_edit
- finish

First step for project inspection tasks:
- Prefer starting with: ACTION: list_project_files

Examples (copy the structure exactly):

ACTION: list_project_files

ACTION: read_file
PATH: demo_project/calculator.py

ACTION: bash
COMMAND: pytest demo_project

ACTION: propose_edit
PATH: demo_project/calculator.py
OLD_TEXT:
return a - b
NEW_TEXT:
return a + b
REASON:
Fix add() so it returns the sum.

ACTION: finish
FINAL: concise final response
""".strip()

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}", re.IGNORECASE), "sk-[REDACTED]"),
    (re.compile(r"Bearer\s+\S+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"OPENAI_API_KEY\s*=\s*\S+", re.IGNORECASE), "OPENAI_API_KEY=[REDACTED]"),
)


@dataclass(frozen=True)
class AgentStepRecord:
    """One LLM step in the main agent loop (for trace display)."""

    step: int
    action: str
    action_detail: str
    observation: str | None = None


@dataclass(frozen=True)
class MainAgentResult:
    """Result from one main-agent run."""

    final_response: str
    steps: int
    stopped_reason: str
    observations: list[str] = field(default_factory=list)
    step_records: list[AgentStepRecord] = field(default_factory=list)


class MainAgent:
    """Simple main agent that decides between tool calls and finishing."""

    def __init__(
        self,
        *,
        runtime_config: RuntimeConfig,
        chat_client: ChatClient,
        project_root: str | Path = ".",
        budget_monitor: TokenBudgetMonitor | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        prompts_root: str | Path | None = None,
        allowed_actions: frozenset[str] | None = None,
        stop_on_invalid_action: bool = False,
        action_protocol: str | None = None,
        apply_proposed_edits: bool = False,
    ) -> None:
        self._runtime_config = runtime_config
        self._app_config = runtime_config.app
        self._chat_client = chat_client
        self._project_root = Path(project_root).resolve()
        self._budget_monitor = budget_monitor or TokenBudgetMonitor(runtime_config.app)
        self._max_steps = max_steps
        self._prompts_root = Path(prompts_root or self._project_root)
        self._allowed_actions = allowed_actions
        self._stop_on_invalid_action = stop_on_invalid_action
        self._action_protocol = action_protocol or _ACTION_PROTOCOL
        self._apply_proposed_edits = apply_proposed_edits

    def run(self, task: str) -> MainAgentResult:
        """Run the main loop until finish, max steps, or budget refusal."""

        observations: list[str] = []
        step_records: list[AgentStepRecord] = []
        steps = 0
        messages = self._initial_messages(task)

        while steps < self._max_steps:
            steps += 1
            try:
                llm_response = self._chat_client.complete(messages)
            except BudgetExceededError as error:
                return MainAgentResult(
                    final_response=str(error),
                    steps=steps,
                    stopped_reason="budget_exceeded",
                    observations=observations,
                    step_records=step_records,
                )

            action = parse_agent_action(llm_response.text)
            if action.name == "finish":
                step_records.append(
                    _make_step_record(
                        steps,
                        action,
                        observation=None,
                    )
                )
                return MainAgentResult(
                    final_response=action.final_response or llm_response.text.strip(),
                    steps=steps,
                    stopped_reason="finish",
                    observations=observations,
                    step_records=step_records,
                )

            if action.name == "unknown":
                if self._stop_on_invalid_action:
                    parse_observation = _format_parse_failure_observation(
                        llm_response.text,
                        config=self._app_config,
                    )
                    step_records.append(
                        _make_step_record(
                            steps,
                            action,
                            observation=parse_observation,
                        )
                    )
                    return MainAgentResult(
                        final_response=(
                            "Stopped safely: could not parse a valid ACTION from the model "
                            "response. See PARSE FAILURE and RAW MODEL RESPONSE in the trace."
                        ),
                        steps=steps,
                        stopped_reason="invalid_action",
                        observations=observations,
                        step_records=step_records,
                    )
                observation = _compact_observation(
                    "agent",
                    f"Could not parse action from model response: {llm_response.text}",
                    config=self._app_config,
                )
                observations.append(observation)
                step_records.append(
                    _make_step_record(
                        steps,
                        AgentAction(name="unknown", params={}),
                        observation=observation,
                    )
                )
                messages = self._build_messages(task, observations)
                continue

            if self._allowed_actions is not None and action.name not in self._allowed_actions:
                step_records.append(
                    _make_step_record(
                        steps,
                        action,
                        observation=f"Action `{action.name}` is not allowed in this mode.",
                    )
                )
                return MainAgentResult(
                    final_response=(
                        f"Stopped safely: action `{action.name}` is not allowed in this mode."
                    ),
                    steps=steps,
                    stopped_reason="blocked_action",
                    observations=observations,
                    step_records=step_records,
                )

            if action.name == "subagents":
                observation = self._run_subagents(action, task, observations)
                observations.append(observation)
                step_records.append(_make_step_record(steps, action, observation=observation))
                messages = self._build_messages(task, observations)
                continue

            if action.name == "propose_edit":
                propose_error = _propose_edit_format_error(action)
                if propose_error is not None:
                    if self._stop_on_invalid_action:
                        step_records.append(
                            _make_step_record(steps, action, observation=propose_error)
                        )
                        return MainAgentResult(
                            final_response=propose_error,
                            steps=steps,
                            stopped_reason="invalid_propose_edit",
                            observations=observations,
                            step_records=step_records,
                        )
                    observation = _compact_observation("propose_edit", propose_error, config=self._app_config)
                    observations.append(observation)
                    step_records.append(_make_step_record(steps, action, observation=observation))
                    messages = self._build_messages(task, observations)
                    continue

            tool_result = self._execute_action(action)
            observation = _compact_tool_observation(action.name, tool_result, self._app_config)
            observations.append(observation)
            step_records.append(_make_step_record(steps, action, observation=observation))
            messages = self._build_messages(task, observations)

        return MainAgentResult(
            final_response=f"Stopped after reaching max_steps={self._max_steps}.",
            steps=steps,
            stopped_reason="max_steps",
            observations=observations,
            step_records=step_records,
        )

    def _execute_action(self, action: AgentAction) -> ToolResult:
        if action.name == "read_file":
            return read_file(
                action.params.get("path", ""),
                project_root=self._project_root,
                config=self._app_config,
            )
        if action.name == "list_project_files":
            return list_project_files(
                project_root=self._project_root,
                config=self._app_config,
            )
        if action.name == "bash":
            return bash(
                action.params.get("command", ""),
                project_root=self._project_root,
                config=self._app_config,
            )
        if action.name == "partial_edit":
            return partial_edit(
                action.params.get("path", ""),
                action.params.get("old_text", ""),
                action.params.get("new_text", ""),
                action.params.get("reason", ""),
                project_root=self._project_root,
                config=self._app_config,
            )
        if action.name == "propose_edit":
            return propose_edit(
                action.params.get("path", ""),
                action.params.get("old_text", ""),
                action.params.get("new_text", ""),
                action.params.get("reason", ""),
                project_root=self._project_root,
                config=self._app_config,
                apply=self._apply_proposed_edits,
            )
        return ToolResult(
            ok=False,
            summary=f"Unsupported action: {action.name}",
            output={"action": action.name},
        )

    def _initial_messages(self, task: str) -> list[dict[str, str]]:
        return self._build_messages(task, [])

    def _build_messages(self, task: str, observations: list[str]) -> list[dict[str, str]]:
        system_parts = [
            self._load_prompt("system_prompt.md"),
            self._load_prompt("main_agent.md"),
            self._action_protocol,
        ]
        system_prompt = "\n\n".join(part for part in system_parts if part)

        user_parts = [f"User task:\n{task}"]
        if observations:
            user_parts.append("Recent compact observations:")
            user_parts.extend(f"- {observation}" for observation in observations)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    def _load_prompt(self, filename: str) -> str:
        path = self._prompts_root / "prompts" / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def _run_subagents(
        self,
        action: AgentAction,
        task: str,
        observations: list[str],
    ) -> str:
        roles = parse_roles_param(action.params.get("roles", ""))
        runner = SubAgentRunner(
            chat_client=self._chat_client,
            app_config=self._app_config,
            prompts_root=self._prompts_root,
            task=task,
            observations=observations,
        )
        results = runner.run_roles(roles)
        compact_parts = [compact_agent_result(result, self._app_config) for result in results]
        combined = "\n".join(compact_parts) if compact_parts else "subagents: no roles requested"
        return _compact_observation("subagents", combined, config=self._app_config)


def _make_step_record(
    step: int,
    action: AgentAction,
    *,
    observation: str | None,
) -> AgentStepRecord:
    return AgentStepRecord(
        step=step,
        action=action.name,
        action_detail=_format_action_detail(action),
        observation=observation,
    )


def _format_action_detail(action: AgentAction) -> str:
    if action.name == "read_file":
        return f"PATH: {action.params.get('path', '').strip()}"
    if action.name == "bash":
        return f"COMMAND: {action.params.get('command', '').strip()}"
    if action.name in {"partial_edit", "propose_edit"}:
        path = action.params.get("path", "").strip()
        reason = action.params.get("reason", "").strip()
        detail = f"PATH: {path}"
        if reason:
            detail = f"{detail} | REASON: {reason}"
        return detail
    if action.name == "subagents":
        return f"ROLES: {action.params.get('roles', '').strip()}"
    if action.name == "finish":
        final = action.final_response or ""
        return final[:200] + ("..." if len(final) > 200 else "")
    if action.name == "unknown":
        return "Unparseable model response"
    return action.name


def _propose_edit_format_error(action: AgentAction) -> str | None:
    missing = [
        field
        for field in ("path", "old_text", "new_text")
        if not action.params.get(field, "").strip()
    ]
    if missing:
        return (
            "Invalid propose_edit format: missing required field(s): "
            f"{', '.join(missing)}."
        )
    return None


def _compact_tool_observation(
    tool_name: str,
    result: ToolResult,
    config: AppConfig,
) -> str:
    parts = [f"{tool_name}: {result.summary}"]

    for key in (
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
    ):
        if key not in result.output:
            continue
        value = result.output[key]
        if isinstance(value, list):
            rendered = ", ".join(str(item) for item in value[:20])
        else:
            rendered = str(value)
        parts.append(f"{key}: {rendered}")

    raw_observation = "\n".join(parts)
    return _compact_observation(tool_name, raw_observation, config=config)


def _compact_observation(source: str, text: str, *, config: AppConfig) -> str:
    compacted = compact_output(text, config=config)
    if compacted.truncated:
        return f"{source}: {compacted.text}"
    return text if source == "agent" else compacted.text


def _redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _format_parse_failure_observation(raw_model_text: str, *, config: AppConfig) -> str:
    """Build a compact, redacted preview of an unparseable model response."""

    redacted = _redact_secrets(raw_model_text.strip())
    compacted = compact_output(redacted, config=config)
    lines = [
        "PARSE FAILURE: Could not parse a valid ACTION block from the model response.",
        "The reply must start with ACTION: and contain no prose before it.",
    ]
    if compacted.truncated:
        lines.append(
            f"RAW MODEL RESPONSE (compact preview; "
            f"original {compacted.original_char_count} characters):"
        )
    else:
        lines.append("RAW MODEL RESPONSE:")
    lines.append(compacted.text)
    return "\n".join(lines)
