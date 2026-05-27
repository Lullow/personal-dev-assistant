from __future__ import annotations

import pytest

from personal_dev_assistant.models import AgentResult, TokenUsage, ToolCall, ToolResult


def test_tool_call_creation():
    call = ToolCall(name="read_file", input={"path": "demo_project/calculator.py"})

    assert call.name == "read_file"
    assert call.input["path"] == "demo_project/calculator.py"


def test_tool_result_creation():
    result = ToolResult(
        ok=True,
        summary="Read file successfully.",
        output={"path": "demo_project/calculator.py"},
    )

    assert result.ok is True
    assert result.summary == "Read file successfully."
    assert result.output["path"] == "demo_project/calculator.py"
    assert result.truncated is False


def test_agent_result_creation():
    result = AgentResult(
        role="explorer",
        summary="Found a failing calculator test.",
        findings=["add returns subtraction"],
        risk_level="low",
        recommended_next_step="Prepare a one-line fix.",
    )

    assert result.role == "explorer"
    assert result.findings == ["add returns subtraction"]
    assert result.risk_level == "low"
    assert result.recommended_next_step == "Prepare a one-line fix."


def test_token_usage_derives_total_tokens():
    usage = TokenUsage(input_tokens=10, output_tokens=15)

    assert usage.effective_total_tokens == 25


def test_token_usage_rejects_negative_values():
    with pytest.raises(ValueError, match="negative"):
        TokenUsage(input_tokens=-1)
