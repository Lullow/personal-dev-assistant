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
from personal_dev_assistant.config import AppConfig, ContextConfig, EnvironmentConfig, RuntimeConfig
from personal_dev_assistant.llm.client import MissingApiKeyError
from personal_dev_assistant.models import TokenUsage
from personal_dev_assistant.run_agent import (
    EXPERIMENTAL_BANNER,
    format_experimental_output,
    run_experimental_llm_agent,
)
from personal_dev_assistant.cli import main as cli_main
from tests.conftest import clear_openai_env
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
    app_config: AppConfig | None = None,
) -> MainAgent:
    runtime = _runtime()
    if app_config is not None:
        runtime = RuntimeConfig(app=app_config, environment=runtime.environment)
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


def _read_file_response(path: str) -> str:
    return f"ACTION: read_file\nPATH: {path}"


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
    assert result.step_records
    assert "RAW MODEL RESPONSE" in result.step_records[-1].observation
    assert "PARSE FAILURE" in result.step_records[-1].observation


def test_invalid_action_includes_compact_raw_model_response(tmp_path):
    long_prose = "Sure! Let me help.\n\n" + ("comment line\n" * 400)
    app_config = AppConfig(context=ContextConfig(max_observation_chars=300))
    agent = _experimental_agent(
        tmp_path,
        [long_prose],
        app_config=app_config,
    )

    result = agent.run("Inspect project.")

    assert result.stopped_reason == "invalid_action"
    observation = result.step_records[-1].observation
    assert observation is not None
    assert "RAW MODEL RESPONSE" in observation
    assert "truncated" in observation.lower() or "compact preview" in observation.lower()
    assert len(observation) < len(long_prose)


def test_format_experimental_output_shows_parse_failure_sections(tmp_path):
    long_prose = "Intro text without ACTION.\n" + ("x" * 200)
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[long_prose],
    )
    result = run_experimental_llm_agent(
        "Task",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
    )

    text = format_experimental_output(result)
    assert "[PARSE FAILURE]" in text
    assert "[RAW MODEL RESPONSE]" in text


def test_experimental_action_protocol_strict_format_and_examples():
    protocol = EXPERIMENTAL_ACTION_PROTOCOL

    assert "exactly ONE ACTION block" in protocol
    assert "Do NOT write prose" in protocol or "no prose" in protocol.lower()
    assert "first non-empty line" in protocol.lower() or "MUST start with: ACTION:" in protocol
    assert "ACTION: list_project_files" in protocol
    assert "Prefer starting with: ACTION: list_project_files" in protocol
    assert "ACTION: read_file\nPATH: demo_project/calculator.py" in protocol
    assert "ACTION: bash\nCOMMAND: pytest demo_project" in protocol
    assert "ACTION: propose_edit" in protocol
    assert "Fix add() so it returns the sum." in protocol
    assert "partial_edit" in protocol.lower()
    assert "subagents" in protocol.lower()
    assert "pytest demo_project" in protocol
    assert "Do NOT run full-repo pytest" in protocol or "whole repository" in protocol.lower()
    assert "valid but not applied" in protocol.lower()
    assert "ACTION: finish" in protocol
    assert "NEXT reply must be ACTION: finish" in protocol or "must be ACTION: finish" in protocol
    assert "Do NOT apologize" in protocol or "Do not apologize" in protocol.lower()
    assert "cannot help" in protocol.lower() or "refuse" in protocol.lower()
    assert "Recommended demo_project flow" in protocol
    assert "5. ACTION: finish" in protocol or "ACTION: finish\n   FINAL:" in protocol
    assert "MUST use ACTION: propose_edit before ACTION: finish" in protocol
    assert "propose a fix" in protocol.lower()
    assert "Do NOT claim a fix was proposed" in protocol or "do not claim" in protocol.lower()
    assert "unless ACTION: propose_edit was actually used" in protocol
    assert (
        "NEXT action must be ACTION: propose_edit" in protocol
        or "NEXT action MUST be ACTION: propose_edit" in protocol
    )
    assert "Full example flow for a fix proposal task" in protocol
    assert "submitted a reviewed proposed edit" in protocol
    assert "ACTION: propose_edit\nPATH: demo_project/calculator.py\nOLD_TEXT:\ndef add(a, b):" in protocol
    assert "Do NOT put ACTION and parameters on the same line" in protocol
    assert "Preferred format" in protocol or "action name on the same line" in protocol
    assert "ACTION: bash command: pytest demo_project" in protocol
    assert "FINAL is required" in protocol or "FINAL is required for finish" in protocol
    assert "Never return only ACTION: finish" in protocol
    assert "MUST always include FINAL:" in protocol or "MUST always include FINAL" in protocol
    assert "--apply-proposed-edits if not applied" in protocol or (
        "how to apply with --apply-proposed-edits" in protocol
    )
    assert "Truthfulness rules for propose_edit" in protocol
    assert "Never claim in FINAL" in protocol or "never claim" in protocol.lower()
    assert "do not invent" in protocol.lower() or "do not invent them" in protocol.lower()
    assert "Trace-grounding rules" in protocol
    assert "read_file on the target file" in protocol
    assert "Do NOT claim tests failed" in protocol or "do not claim tests failed" in protocol.lower()
    assert "unless ACTION: bash ran" in protocol or "ACTION: bash ran" in protocol


def test_experimental_finish_claiming_propose_edit_without_action_gets_fallback(tmp_path):
    """Smoke-test scenario: model finishes after read_file but claims propose_edit ran."""
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    calculator = demo_dir / "calculator.py"
    calculator.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: list_project_files",
            "ACTION: bash\nCOMMAND: pytest demo_project",
            "ACTION: read_file\nPATH: demo_project/calculator.py",
            (
                "ACTION: finish\n"
                "FINAL: Reviewed proposed edit submitted (risk low); edit not applied here."
            ),
        ],
    )

    result = agent.run(
        "Inspect demo_project, run pytest, and propose a fix for the failing test"
    )

    assert result.stopped_reason == "finish"
    assert "no proposed edit was submitted" in result.final_response
    assert "ended before calling propose_edit" in result.final_response
    assert not any(record.action == "propose_edit" for record in result.step_records)


def test_experimental_finish_after_propose_edit_accepts_proposal_claim(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")
    final_text = (
        "Reviewed proposed edit submitted (risk low); edit not applied here. "
        "Re-run with --apply-proposed-edits to apply."
    )
    agent = _experimental_agent(
        tmp_path,
        [
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            f"ACTION: finish\nFINAL: {final_text}",
        ],
    )

    result = agent.run("Propose a fix.")

    assert result.stopped_reason == "finish"
    assert result.final_response == final_text
    assert any(
        record.action == "propose_edit"
        and record.observation
        and "propose_edit blocked:" not in record.observation.lower()
        for record in result.step_records
    )


def test_experimental_finish_claiming_test_failure_without_bash_gets_fallback(tmp_path):
    """Smoke-test scenario: propose_edit without pytest, FINAL claims tests failed."""
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    calculator = demo_dir / "calculator.py"
    calculator.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: list_project_files",
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            (
                "ACTION: finish\n"
                "FINAL: Tests fail because add() subtracts. "
                "Reviewed proposed edit submitted (not applied)."
            ),
        ],
    )

    result = agent.run(
        "Inspect demo_project, run pytest, and propose a fix for the failing test"
    )

    assert result.stopped_reason == "finish"
    assert "no test command was run" in result.final_response
    assert "trace does not support" in result.final_response.lower()


def test_experimental_finish_after_bash_accepts_test_summary(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    (demo_dir / "calculator.py").write_text("return a - b\n", encoding="utf-8")

    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: bash\nCOMMAND: pytest demo_project",
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            (
                "ACTION: finish\n"
                "FINAL: Tests fail because add() subtracts. "
                "Reviewed proposed edit submitted (not applied)."
            ),
        ],
    )

    result = agent.run("Run pytest and propose a fix.")

    assert result.stopped_reason == "finish"
    assert "Tests fail because add() subtracts." in result.final_response


def test_experimental_propose_edit_before_read_file_is_blocked(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")

    agent = _experimental_agent(
        tmp_path,
        [
            "ACTION: list_project_files",
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            "ACTION: finish\nFINAL: Done.",
        ],
    )

    result = agent.run("Propose a fix.")

    assert result.stopped_reason == "finish"
    assert target.read_text(encoding="utf-8") == "return a - b\n"
    assert any(
        "not read in this run" in observation.lower()
        for observation in result.observations
    )
    assert not any(
        "risk_level" in observation or "reviewer_summary" in observation
        for observation in result.observations
    )


def test_experimental_propose_edit_after_read_file_works(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")

    agent = _experimental_agent(
        tmp_path,
        [
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            "ACTION: finish\nFINAL: Proposed fix.",
        ],
    )

    result = agent.run("Propose a fix.")

    assert result.stopped_reason == "finish"
    assert any(
        "risk_level" in observation or "reviewer_summary" in observation
        for observation in result.observations
    )


def test_final_claims_test_results_detects_false_claims():
    from personal_dev_assistant.agents.main import _final_claims_test_results

    assert _final_claims_test_results("Tests fail because add() subtracts.")
    assert _final_claims_test_results("Ran pytest and found a failing test.")
    assert not _final_claims_test_results("Listed project files successfully.")
    assert not _final_claims_test_results("No test command was run in this session.")


def test_final_claims_propose_edit_occurred_detects_false_claims():
    from personal_dev_assistant.agents.main import _final_claims_propose_edit_occurred

    assert _final_claims_propose_edit_occurred(
        "Reviewed proposed edit submitted (risk low); edit not applied here."
    )
    assert _final_claims_propose_edit_occurred(
        "Submitted a reviewed proposed edit. Re-run with --apply-proposed-edits."
    )
    assert not _final_claims_propose_edit_occurred("Listed project files successfully.")
    assert not _final_claims_propose_edit_occurred(
        "No proposed edit was submitted in this run."
    )


def test_experimental_finish_without_final_produces_fallback(tmp_path):
    agent = _experimental_agent(tmp_path, ["ACTION: finish"])

    result = agent.run("Finish without summary.")

    assert result.stopped_reason == "finish"
    assert "did not provide a FINAL summary" in result.final_response


def test_experimental_finish_with_final_uses_model_response(tmp_path):
    agent = _experimental_agent(
        tmp_path,
        ["ACTION: finish\nFINAL: Experimental run complete."],
    )

    result = agent.run("Finish with summary.")

    assert result.stopped_reason == "finish"
    assert result.final_response == "Experimental run complete."


def test_parse_failure_observation_redacts_secrets():
    from personal_dev_assistant.agents.main import _format_parse_failure_observation

    observation = _format_parse_failure_observation(
        "Here is my key sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890",
        config=AppConfig(),
    )

    assert "sk-[REDACTED]" in observation
    assert "abcdefghijklmnopqrstuvwxyz" not in observation


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


def test_format_experimental_output_includes_banner_and_trace(tmp_path):
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            "ACTION: list_project_files",
            "ACTION: finish\nFINAL: Done.",
        ],
    )
    result = run_experimental_llm_agent(
        "List and finish.",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
    )

    text = format_experimental_output(result)
    assert EXPERIMENTAL_BANNER.splitlines()[0] in text
    assert "EXPERIMENTAL LLM AGENT MODE" in text
    assert "Apply proposed edits: no" in text
    assert "--- Step 1 ---" in text
    assert "[LLM DECISION]" in text
    assert "list_project_files" in text
    assert "[TOOL RESULT]" in text
    assert "--- Step 2 ---" in text
    assert "Stopped reason: finish" in text
    assert "TOKEN BUDGET" in text
    assert "Total tokens used:" in text
    assert "FINAL ANSWER" in text
    assert "Done." in text


def test_format_experimental_output_labels_propose_edit_reviewer(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    (demo_dir / "calculator.py").write_text("return a - b\n", encoding="utf-8")
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            "ACTION: finish\nFINAL: Proposed.",
        ],
    )
    result = run_experimental_llm_agent(
        "Propose fix.",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
    )

    text = format_experimental_output(result)
    assert "[REVIEWER]" in text
    assert "risk_level=" in text
    assert "reviewer_summary=" in text
    assert "recommendation=" in text


def test_format_experimental_output_shows_apply_flag(tmp_path):
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=["ACTION: finish\nFINAL: ok"],
    )
    result = run_experimental_llm_agent(
        "Task",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
        apply_proposed_edits=True,
    )

    text = format_experimental_output(result)
    assert "Apply proposed edits: yes" in text


def test_format_experimental_output_labels_blocked_bash_as_safety(tmp_path):
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            "ACTION: bash\nCOMMAND: rm -rf demo_project",
            "ACTION: finish\nFINAL: done",
        ],
    )
    result = run_experimental_llm_agent(
        "Risky bash",
        runtime_config=runtime,
        project_root=tmp_path,
        chat_client=client,
    )

    text = format_experimental_output(result)
    assert "[SAFETY]" in text
    assert "blocked" in text.lower()


def test_cli_run_agent_requires_llm_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = cli_main(["run-agent", "Inspect demo_project"])
    assert exit_code == 2


def test_cli_run_agent_missing_api_key_returns_error(tmp_path, monkeypatch):
    clear_openai_env(monkeypatch)
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
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
            "ACTION: finish\nFINAL: Proposed fix.",
        ],
    )

    result = agent.run("Propose a fix.")

    assert result.stopped_reason == "finish"
    assert target.read_text(encoding="utf-8") == "return a - b\n"
    assert any("not applied" in observation.lower() for observation in result.observations)
    assert any(
        "risk_level" in observation or "reviewer_summary" in observation
        for observation in result.observations
    )


def test_experimental_propose_edit_applied_with_apply_flag(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
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


def test_experimental_propose_edit_high_risk_not_applied_with_apply_flag(tmp_path):
    target = tmp_path / "large.py"
    old_block = "line\n" * 15
    new_block = "fixed\n" * 15
    target.write_text(old_block, encoding="utf-8")
    agent = _experimental_agent(
        tmp_path,
        [
            _read_file_response("large.py"),
            _propose_edit_response("large.py", old_block, new_block),
            "ACTION: finish\nFINAL: Blocked by reviewer.",
        ],
        apply_proposed_edits=True,
    )

    result = agent.run("Try large apply.")

    assert result.stopped_reason == "finish"
    assert target.read_text(encoding="utf-8") == old_block
    assert any("high risk" in observation.lower() for observation in result.observations)


def test_run_experimental_llm_agent_passes_apply_flag(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")
    runtime = _runtime()
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            _read_file_response("demo_project/calculator.py"),
            _propose_edit_response(
                "demo_project/calculator.py",
                "return a - b",
                "return a + b",
            ),
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
