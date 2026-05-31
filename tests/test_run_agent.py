from __future__ import annotations

from pathlib import Path

import pytest

from personal_dev_assistant.agents import MainAgent
from personal_dev_assistant.agents.main import (
    EXPERIMENTAL_ACTION_PROTOCOL,
    EXPERIMENTAL_ALLOWED_ACTIONS,
)
from personal_dev_assistant.agents.protocol import parse_agent_action
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


def _experimental_agent(
    tmp_path,
    responses: list[str],
    *,
    apply_proposed_edits: bool = False,
) -> MainAgent:
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
        apply_proposed_edits=apply_proposed_edits,
    )


def _propose_edit_response(
    path: str,
    old_text: str,
    new_text: str,
    *,
    reason: str = "Fix bug",
) -> str:
    return (
        "ACTION: propose_edit\n"
        f"PATH: {path}\n"
        "OLD_TEXT:\n"
        f"{old_text}\n"
        "NEW_TEXT:\n"
        f"{new_text}\n"
        "REASON:\n"
        f"{reason}"
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


def test_parse_propose_edit_multiline_format():
    text = (
        "ACTION: propose_edit\n"
        "PATH: demo.py\n"
        "OLD_TEXT:\n"
        "return a - b\n"
        "NEW_TEXT:\n"
        "return a + b\n"
        "REASON:\n"
        "Fix add"
    )
    action = parse_agent_action(text)

    assert action.name == "propose_edit"
    assert action.params["path"] == "demo.py"
    assert action.params["old_text"] == "return a - b"
    assert action.params["new_text"] == "return a + b"
    assert action.params["reason"] == "Fix add"


def test_experimental_propose_edit_valid_but_not_applied_by_default(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _propose_edit_response("demo.py", "return a - b", "return a + b"),
            "ACTION: finish\nFINAL: Proposed fix.",
        ],
    )

    result = agent.run("Propose a fix.")

    assert result.stopped_reason == "finish"
    assert target.read_text(encoding="utf-8") == "return a - b\n"
    assert any("not applied" in observation.lower() for observation in result.observations)
    assert any("mini_diff" in observation or "- return a - b" in observation for observation in result.observations)


def test_experimental_propose_edit_applied_with_apply_flag(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _propose_edit_response("demo.py", "return a - b", "return a + b"),
            "ACTION: finish\nFINAL: Applied fix.",
        ],
        apply_proposed_edits=True,
    )

    result = agent.run("Apply a fix.")

    assert result.stopped_reason == "finish"
    assert target.read_text(encoding="utf-8") == "return a + b\n"
    assert any("propose_edit" in observation for observation in result.observations)


def test_experimental_propose_edit_blocked_path_is_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=1\n", encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _propose_edit_response(".env", "SECRET=1", "SECRET=0"),
            "ACTION: finish\nFINAL: Blocked.",
        ],
    )

    result = agent.run("Propose bad path.")

    assert result.stopped_reason == "finish"
    assert env_file.read_text(encoding="utf-8") == "SECRET=1\n"
    assert any("blocked" in observation.lower() for observation in result.observations)


def test_experimental_invalid_propose_edit_format_stops_safely(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        ["ACTION: propose_edit\nPATH: demo.py\nREASON:\nMissing old/new text"],
    )

    result = agent.run("Bad proposal.")

    assert result.stopped_reason == "invalid_propose_edit"
    assert "missing required field" in result.final_response.lower()


def test_run_experimental_llm_agent_passes_apply_flag(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            _propose_edit_response("demo.py", "return a - b", "return a + b"),
            "ACTION: finish\nFINAL: Done.",
        ],
    )

    result = run_experimental_llm_agent(
        "Apply proposal.",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
        apply_proposed_edits=True,
    )

    assert target.read_text(encoding="utf-8") == "return a + b\n"
    assert result.agent_result.stopped_reason == "finish"
