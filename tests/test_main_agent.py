from __future__ import annotations

from personal_dev_assistant.agents import MainAgent
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, ContextConfig, EnvironmentConfig, RuntimeConfig, TokenBudgetConfig
from personal_dev_assistant.llm.client import ChatClient
from personal_dev_assistant.models import TokenUsage


class ScriptedChatClient(ChatClient):
    """Mock chat client that returns a scripted sequence of responses."""

    def __init__(
        self,
        *,
        model: str,
        budget_monitor: TokenBudgetMonitor,
        responses: list[str],
    ) -> None:
        super().__init__(model=model, budget_monitor=budget_monitor)
        self._responses = list(responses)
        self._call_index = 0

    def _complete(self, messages: list[dict[str, str]]):
        if self._call_index >= len(self._responses):
            text = "ACTION: finish\nFINAL: No more scripted responses."
        else:
            text = self._responses[self._call_index]
        self._call_index += 1

        from personal_dev_assistant.llm.client import LLMResponse, _estimate_tokens, _messages_text

        return LLMResponse(
            text=text,
            usage=TokenUsage(
                input_tokens=_estimate_tokens(_messages_text(messages)),
                output_tokens=_estimate_tokens(text),
            ),
            model=self._model,
            mock=True,
        )


def _make_agent(
    tmp_path,
    responses: list[str],
    *,
    max_steps: int = 10,
    budget_monitor: TokenBudgetMonitor | None = None,
    max_observation_chars: int = 4000,
    max_subagent_summary_chars: int = 1500,
) -> MainAgent:
    app_config = AppConfig(
        context=ContextConfig(
            max_observation_chars=max_observation_chars,
            max_subagent_summary_chars=max_subagent_summary_chars,
        )
    )
    runtime = RuntimeConfig(app=app_config, environment=EnvironmentConfig())
    monitor = budget_monitor or TokenBudgetMonitor(app_config)
    client = ScriptedChatClient(
        model=app_config.model,
        budget_monitor=monitor,
        responses=responses,
    )
    return MainAgent(
        runtime_config=runtime,
        chat_client=client,
        project_root=tmp_path,
        budget_monitor=monitor,
        max_steps=max_steps,
    )


def test_agent_can_finish_directly(tmp_path):
    agent = _make_agent(
        tmp_path,
        ["ACTION: finish\nFINAL: Task complete."],
    )

    result = agent.run("Inspect the project.")

    assert result.stopped_reason == "finish"
    assert result.final_response == "Task complete."
    assert result.steps == 1


def test_agent_can_call_read_file(tmp_path):
    file_path = tmp_path / "demo_project" / "calculator.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    agent = _make_agent(
        tmp_path,
        [
            "ACTION: read_file\nPATH: demo_project/calculator.py",
            "ACTION: finish\nFINAL: Read the calculator file.",
        ],
    )

    result = agent.run("Read calculator.py")

    assert result.stopped_reason == "finish"
    assert any("read_file" in observation for observation in result.observations)
    assert any("calculator.py" in observation for observation in result.observations)


def test_agent_can_call_list_project_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    agent = _make_agent(
        tmp_path,
        [
            "ACTION: list_project_files",
            "ACTION: finish\nFINAL: Listed project files.",
        ],
    )

    result = agent.run("List files")

    assert result.stopped_reason == "finish"
    assert any("list_project_files" in observation for observation in result.observations)
    assert any("src/app.py" in observation for observation in result.observations)


def test_agent_can_call_safe_bash(tmp_path):
    agent = _make_agent(
        tmp_path,
        [
            "ACTION: bash\nCOMMAND: pwd",
            "ACTION: finish\nFINAL: Ran pwd.",
        ],
    )

    result = agent.run("Show working directory")

    assert result.stopped_reason == "finish"
    assert any("bash" in observation for observation in result.observations)
    assert any(str(tmp_path.resolve()) in observation for observation in result.observations)


def test_agent_returns_blocked_bash_result_for_dangerous_command(tmp_path):
    agent = _make_agent(
        tmp_path,
        [
            "ACTION: bash\nCOMMAND: rm -rf demo_project",
            "ACTION: finish\nFINAL: Blocked dangerous command.",
        ],
    )

    result = agent.run("Try dangerous command")

    assert result.stopped_reason == "finish"
    assert any("blocked" in observation.lower() for observation in result.observations)


def test_agent_stops_at_max_steps(tmp_path):
    agent = _make_agent(
        tmp_path,
        [
            "ACTION: read_file\nPATH: missing.txt",
            "ACTION: read_file\nPATH: missing.txt",
        ],
        max_steps=2,
    )

    result = agent.run("Keep reading")

    assert result.stopped_reason == "max_steps"
    assert result.steps == 2
    assert "max_steps=2" in result.final_response


def test_agent_stops_if_token_budget_hard_cap_is_reached(tmp_path):
    monitor = TokenBudgetMonitor(
        TokenBudgetConfig(max_tokens=20, warning_threshold=0.5, hard_cap_enabled=True)
    )
    monitor.add_usage(TokenUsage(input_tokens=15, output_tokens=10))
    agent = _make_agent(
        tmp_path,
        ["ACTION: finish\nFINAL: Should not reach this."],
        budget_monitor=monitor,
    )

    result = agent.run("One more step")

    assert result.stopped_reason == "budget_exceeded"
    assert "hard cap" in result.final_response.lower()


def test_tool_observations_are_included_compactly_not_as_unbounded_raw_output(tmp_path):
    long_content = "BEGIN-" + ("x" * 500) + "-END"
    file_path = tmp_path / "long.txt"
    file_path.write_text(long_content, encoding="utf-8")

    agent = _make_agent(
        tmp_path,
        [
            "ACTION: read_file\nPATH: long.txt",
            "ACTION: finish\nFINAL: Done.",
        ],
        max_observation_chars=120,
    )

    result = agent.run("Read long file")

    assert result.observations
    observation = result.observations[0]
    assert len(observation) <= 120 + len("read_file: ")
    assert "[truncated" in observation


def test_main_agent_can_parse_subagents_action_with_multiple_roles(tmp_path):
    agent = _make_agent(
        tmp_path,
        [
            "ACTION: subagents\nROLES: planner, explorer",
            "ROLE: planner\nSUMMARY: Plan the fix\nFINDING: inspect demo files\nRISK_LEVEL: low\nNEXT_STEP: explore",
            "ROLE: explorer\nSUMMARY: Found subtraction bug\nFINDING: add returns a - b\nRISK_LEVEL: low\nNEXT_STEP: edit",
            "ACTION: finish\nFINAL: Sub-agents coordinated.",
        ],
    )

    result = agent.run("Fix the demo test")

    assert result.stopped_reason == "finish"
    assert any("planner" in observation for observation in result.observations)
    assert any("explorer" in observation for observation in result.observations)
    assert any("subtraction bug" in observation for observation in result.observations)


def test_main_agent_adds_compact_subagent_results_to_observations(tmp_path):
    long_summary = "SUMMARY-" + ("x" * 300) + "-END"
    agent = _make_agent(
        tmp_path,
        [
            "ACTION: subagents\nROLES: planner",
            f"ROLE: planner\nSUMMARY: {long_summary}\nRISK_LEVEL: low",
            "ACTION: finish\nFINAL: Done.",
        ],
        max_subagent_summary_chars=80,
    )

    result = agent.run("Long sub-agent summary")

    assert result.observations
    assert "[truncated" in result.observations[0]


def test_token_budget_monitor_is_updated_through_chat_client_during_subagents(tmp_path):
    app_config = AppConfig()
    monitor = TokenBudgetMonitor(app_config)
    client = ScriptedChatClient(
        model=app_config.model,
        budget_monitor=monitor,
        responses=[
            "ACTION: subagents\nROLES: planner",
            "ROLE: planner\nSUMMARY: Short plan\nRISK_LEVEL: low",
            "ACTION: finish\nFINAL: Done.",
        ],
    )
    agent = MainAgent(
        runtime_config=RuntimeConfig(app=app_config, environment=EnvironmentConfig()),
        chat_client=client,
        project_root=tmp_path,
        budget_monitor=monitor,
    )

    agent.run("Track budget")

    assert monitor.status().total_tokens_used > 0
