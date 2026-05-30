from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.agents.subagents import (
    SubAgentRunner,
    compact_agent_result,
    parse_subagent_response,
)
from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, ContextConfig
from personal_dev_assistant.llm.client import ChatClient
from personal_dev_assistant.models import AgentResult, TokenUsage

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        text = self._responses[min(self._call_index, len(self._responses) - 1)]
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


def _runner(responses: list[str], *, max_subagent_summary_chars: int = 1500) -> SubAgentRunner:
    app_config = AppConfig(context=ContextConfig(max_subagent_summary_chars=max_subagent_summary_chars))
    monitor = TokenBudgetMonitor(app_config)
    client = ScriptedChatClient(
        model=app_config.model,
        budget_monitor=monitor,
        responses=responses,
    )
    return SubAgentRunner(
        chat_client=client,
        app_config=app_config,
        prompts_root=REPO_ROOT,
        task="Fix the failing demo test.",
    )


def test_subagent_runner_can_run_planner_and_return_agent_result():
    runner = _runner(
        [
            "ROLE: planner\n"
            "SUMMARY: Inspect demo files and run tests.\n"
            "FINDING: Start with demo_project/test_calculator.py\n"
            "RISK_LEVEL: low\n"
            "NEXT_STEP: Ask explorer to inspect files"
        ]
    )

    result = runner.run_role("planner")

    assert isinstance(result, AgentResult)
    assert result.role == "planner"
    assert "Inspect demo files" in result.summary
    assert result.findings == ["Start with demo_project/test_calculator.py"]
    assert result.risk_level == "low"


def test_subagent_runner_can_run_explorer_coder_and_reviewer_roles():
    responses = [
        "ROLE: explorer\nSUMMARY: Found subtraction bug\nFINDING: add returns a - b\nRISK_LEVEL: low\nNEXT_STEP: edit",
        "ROLE: coder\nSUMMARY: Replace subtraction with addition\nFINDING: one-line fix\nRISK_LEVEL: low\nNEXT_STEP: test",
        "ROLE: reviewer\nSUMMARY: Edit looks safe\nFINDING: no risky commands needed\nRISK_LEVEL: low\nNEXT_STEP: finish",
    ]
    runner = _runner(responses)

    results = runner.run_roles(["explorer", "coder", "reviewer"])

    assert [result.role for result in results] == ["explorer", "coder", "reviewer"]
    assert all(result.summary for result in results)


def test_subagent_output_is_compacted_when_too_long():
    long_summary = "SUMMARY-" + ("x" * 300) + "-END"
    parsed = parse_subagent_response(
        f"ROLE: planner\nSUMMARY: {long_summary}\nRISK_LEVEL: low",
        default_role="planner",
    )
    app_config = AppConfig(context=ContextConfig(max_subagent_summary_chars=80))

    compact = compact_agent_result(parsed, app_config)

    assert len(compact) <= 80
    assert "[truncated" in compact


def test_invalid_role_is_rejected_clearly():
    runner = _runner(
        ["ROLE: planner\nSUMMARY: Plan the work\nRISK_LEVEL: low\nNEXT_STEP: explore"]
    )

    results = runner.run_roles(["planner", "unknown-role"])

    assert results[0].role == "planner"
    assert results[1].role == "unknown-role"
    assert "Unknown sub-agent role" in results[1].summary
    assert results[1].risk_level == "high"


def test_parse_subagent_response_collects_multiple_findings():
    result = parse_subagent_response(
        "ROLE: explorer\n"
        "SUMMARY: Found issue\n"
        "FINDING: test expects addition\n"
        "FINDING: calculator subtracts\n"
        "RISK_LEVEL: low\n"
        "NEXT_STEP: prepare edit",
        default_role="explorer",
    )

    assert result.findings == ["test expects addition", "calculator subtracts"]
    assert result.recommended_next_step == "prepare edit"
