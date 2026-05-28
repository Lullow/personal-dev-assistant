from __future__ import annotations

from personal_dev_assistant.config import AppConfig, ContextConfig
from personal_dev_assistant.context import compact_output, compact_tool_observation


def test_short_output_is_preserved():
    result = compact_output("short output", max_chars=50)

    assert result.text == "short output"
    assert result.truncated is False
    assert result.original_char_count == len("short output")
    assert result.compacted_char_count == len("short output")


def test_long_output_is_compacted():
    result = compact_output("a" * 100, max_chars=60)

    assert result.truncated is True
    assert result.original_char_count == 100
    assert result.compacted_char_count <= 60


def test_truncation_marker_is_included():
    result = compact_output("a" * 100, max_chars=70)

    assert "[truncated" in result.text
    assert "characters" in result.text


def test_beginning_and_ending_content_are_preserved():
    raw_output = "BEGIN-" + ("middle-" * 20) + "END"

    result = compact_output(raw_output, max_chars=80)

    assert result.text.startswith("BEGIN-")
    assert result.text.endswith("END")
    assert result.truncated is True


def test_configured_max_observation_chars_is_respected():
    config = AppConfig(context=ContextConfig(max_observation_chars=75))

    result = compact_output("0123456789" * 20, config=config)

    assert result.compacted_char_count <= 75
    assert len(result.text) <= 75


def test_compact_tool_observation_returns_tool_result_style_observation():
    config = AppConfig(context=ContextConfig(max_observation_chars=80))

    result = compact_tool_observation(
        "pytest",
        "START-" + ("test output " * 30) + "END",
        config=config,
        output_key="stdout",
    )

    assert result.ok is True
    assert result.truncated is True
    assert result.output["stdout"].startswith("START-")
    assert result.output["stdout"].endswith("END")
    assert result.output["original_char_count"] > result.output["compacted_char_count"]
