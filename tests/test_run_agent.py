from __future__ import annotations

from pathlib import Path

import pytest

from personal_dev_assistant.agents import MainAgent
from personal_dev_assistant.agents.main import (
    EXPERIMENTAL_ACTION_PROTOCOL,
    EXPERIMENTAL_ALLOWED_ACTIONS,
)
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, EnvironmentConfig, RuntimeConfig
from personal_dev_assistant.llm.client import MissingApiKeyError
from personal_dev_assistant.models import TokenUsage
from personal_dev_assistant.run_agent import (
    EXPERIMENTAL_BANNER,
    format_experimental_output,
    run_experimental_llm_agent,
)
from personal_dev_assistant.cli import main as cli_main
from tests.test_main_agent import ScriptedChatClient


def _runtime(*, api_key: str | None = None) -> RuntimeConfig:
    return RuntimeConfig(
        app=AppConfig(),
        environment=EnvironmentConfig(openai_api_key=api_key),
    )


def _experimental_agent(tmp_path, responses: list[str]) -> MainAgent:
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=responses,
    )
    return MainAgent(
        runtime_config=runtime,
        chat_client=client,
        project_root=tmp_path,
        budget_monitor=monitor,
        allowed_actions=EXPERIMENTAL_ALLOWED_ACTIONS,
        stop_on_invalid_action=True,
        action_protocol=EXPERIMENTAL_ACTION_PROTOCOL,
    )


def test_experimental_run_requires_api_key_when_no_client_injected():
    runtime = _runtime(api_key=None)

    with pytest.raises(MissingApiKeyError):
        run_experimental_llm_agent("Inspect demo_project", runtime_config=runtime)


def test_experimental_agent_can_list_and_finish(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: list_project_files",
            "ACTION: finish\nFINAL: Listed project files.",
        ],
    )

    result = agent.run("List the project.")

    assert result.stopped_reason == "finish"
    assert result.final_response == "Listed project files."
    assert any("list_project_files" in observation for observation in result.observations)


def test_experimental_agent_blocks_partial_edit(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: partial_edit\nPATH: demo.py\nOLD_TEXT: a\nNEW_TEXT: b\nREASON: test",
        ],
    )

    result = agent.run("Try to edit.")

    assert result.stopped_reason == "blocked_action"
    assert "partial_edit" in result.final_response


def test_experimental_agent_blocks_subagents(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        ["ACTION: subagents\nROLES: planner"],
    )

    result = agent.run("Use subagents.")

    assert result.stopped_reason == "blocked_action"
    assert "subagents" in result.final_response


def test_experimental_agent_stops_on_invalid_action_format(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        ["This is not a valid ACTION response."],
    )

    result = agent.run("Do something.")

    assert result.stopped_reason == "invalid_action"
    assert "could not parse" in result.final_response.lower()


def test_experimental_agent_risky_bash_is_not_executed(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: bash\nCOMMAND: rm -rf demo_project",
            "ACTION: finish\nFINAL: done",
        ],
    )

    result = agent.run("Run risky command.")

    assert result.observations
    assert result.observations[0].startswith("bash:")
    assert "blocked" in result.observations[0].lower()


def test_run_experimental_llm_agent_with_scripted_client(tmp_path):
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=["ACTION: finish\nFINAL: Experimental run complete."],
    )

    result = run_experimental_llm_agent(
        "Finish quickly.",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
    )

    assert result.experimental is True
    assert result.agent_result.stopped_reason == "finish"
    assert result.agent_result.final_response == "Experimental run complete."


def test_format_experimental_output_includes_banner():
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=["ACTION: finish\nFINAL: Done."],
    )
    result = run_experimental_llm_agent(
        "Task",
        runtime_config=runtime,
        project_root=".",
        chat_client=client,
    )

    text = format_experimental_output(result)
    assert EXPERIMENTAL_BANNER.splitlines()[0] in text
    assert "Final response:" in text
    assert "Done." in text


def test_cli_run_agent_requires_llm_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = cli_main(["run-agent", "Inspect demo_project"])
    assert exit_code == 2


def test_cli_run_agent_missing_api_key_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = cli_main(["run-agent", "Inspect demo_project", "--llm"])
    assert exit_code == 2
