"""Main agent loop for Personal Dev Assistant."""

from __future__ import annotations

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
from personal_dev_assistant.tools import bash, list_project_files, partial_edit, read_file

DEFAULT_MAX_STEPS = 10

EXPERIMENTAL_ALLOWED_ACTIONS = frozenset(
    {"read_file", "list_project_files", "bash", "finish"}
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
Respond using this exact protocol.

Experimental LLM mode allows ONLY these actions:
- read_file
- list_project_files
- bash
- finish

Do NOT use partial_edit or subagents in experimental mode.

ACTION: read_file
PATH: relative/path

ACTION: list_project_files

ACTION: bash
COMMAND: safe command here

ACTION: finish
FINAL: concise final response to the user
""".strip()


@dataclass(frozen=True)
class MainAgentResult:
    """Result from one main-agent run."""

    final_response: str
    steps: int
    stopped_reason: str
    observations: list[str] = field(default_factory=list)


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

    def run(self, task: str) -> MainAgentResult:
        """Run the main loop until finish, max steps, or budget refusal."""

        observations: list[str] = []
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
                )

            action = parse_agent_action(llm_response.text)
            if action.name == "finish":
                return MainAgentResult(
                    final_response=action.final_response or llm_response.text.strip(),
                    steps=steps,
                    stopped_reason="finish",
                    observations=observations,
                )

            if action.name == "unknown":
                if self._stop_on_invalid_action:
                    return MainAgentResult(
                        final_response=(
                            "Stopped safely: could not parse a valid ACTION from the model response."
                        ),
                        steps=steps,
                        stopped_reason="invalid_action",
                        observations=observations,
                    )
                observation = _compact_observation(
                    "agent",
                    f"Could not parse action from model response: {llm_response.text}",
                    config=self._app_config,
                )
                observations.append(observation)
                messages = self._build_messages(task, observations)
                continue

            if self._allowed_actions is not None and action.name not in self._allowed_actions:
                return MainAgentResult(
                    final_response=(
                        f"Stopped safely: action `{action.name}` is not allowed in this mode."
                    ),
                    steps=steps,
                    stopped_reason="blocked_action",
                    observations=observations,
                )

            if action.name == "subagents":
                observation = self._run_subagents(action, task, observations)
                observations.append(observation)
                messages = self._build_messages(task, observations)
                continue

            tool_result = self._execute_action(action)
            observation = _compact_tool_observation(action.name, tool_result, self._app_config)
            observations.append(observation)
            messages = self._build_messages(task, observations)

        return MainAgentResult(
            final_response=f"Stopped after reaching max_steps={self._max_steps}.",
            steps=steps,
            stopped_reason="max_steps",
            observations=observations,
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


def _compact_tool_observation(
    tool_name: str,
    result: ToolResult,
    config: AppConfig,
) -> str:
    parts = [f"{tool_name}: {result.summary}"]

    for key in ("path", "stdout", "stderr", "content", "files"):
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
