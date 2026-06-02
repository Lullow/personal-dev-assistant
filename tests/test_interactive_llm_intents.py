from __future__ import annotations

from io import StringIO

import pytest

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.interactive import (
    IntentClassification,
    ParsedCommand,
    ScriptedIntentClassifier,
    is_strict_deterministic_match,
    parse_command,
    parse_intent_json,
    resolve_command,
)
from personal_dev_assistant.interactive.intents import classification_to_command
from tests.test_interactive import BUGGY_CALCULATOR, _assistant, _write_demo_project


def _classifier_for_phrases() -> ScriptedIntentClassifier:
    return ScriptedIntentClassifier(
        {
            "can you help me fix this bug?": IntentClassification(
                intent="fix",
                arg=None,
                confidence="high",
                reason="User wants to prepare a fix.",
            ),
            "could you check this file for problems?": IntentClassification(
                intent="review",
                arg=None,
                confidence="medium",
                reason="User asked for a file review.",
            ),
            "please run the test again": IntentClassification(
                intent="test",
                arg=None,
                confidence="high",
                reason="User wants to run tests.",
            ),
            "show me what file we are working on": IntentClassification(
                intent="current",
                arg=None,
                confidence="high",
                reason="User wants the active file.",
            ),
        }
    )


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("fix it", "fix"),
        ("review it", "review"),
        ("show current file", "current"),
    ],
)
def test_strict_deterministic_match_recognizes_aliases(line, expected):
    assert is_strict_deterministic_match(line) is True
    command, _message = resolve_command(
        line,
        llm_intents_enabled=True,
        intent_classifier=_classifier_for_phrases(),
    )
    assert command == ParsedCommand(name=expected)


def test_resolve_command_without_llm_intents_uses_deterministic_only():
    command, message = resolve_command(
        "can you help me fix this bug?",
        llm_intents_enabled=False,
        intent_classifier=_classifier_for_phrases(),
    )
    assert command == ParsedCommand(name="help", arg="me fix this bug?")
    assert message is None


@pytest.mark.parametrize(
    ("line", "expected_name"),
    [
        ("can you help me fix this bug?", "fix"),
        ("could you check this file for problems?", "review"),
        ("please run the test again", "test"),
        ("show me what file we are working on", "current"),
    ],
)
def test_resolve_command_with_llm_intents_classifies_ambiguous_phrases(
    line,
    expected_name,
):
    command, message = resolve_command(
        line,
        llm_intents_enabled=True,
        intent_classifier=_classifier_for_phrases(),
    )
    assert command == ParsedCommand(name=expected_name)
    assert message is None


def test_resolve_command_invalid_json_returns_unknown():
    classifier = ScriptedIntentClassifier({})
    command, message = resolve_command(
        "tell me a joke about databases",
        llm_intents_enabled=True,
        intent_classifier=classifier,
    )
    assert command == ParsedCommand(name="unknown")
    assert message is not None


def test_parse_intent_json_rejects_disallowed_intent():
    assert (
        parse_intent_json(
            '{"intent":"bash","arg":null,"confidence":"high","reason":"run"}'
        )
        is None
    )


def test_parse_intent_json_rejects_low_confidence_via_classification_to_command():
    classification = IntentClassification(
        intent="fix",
        arg=None,
        confidence="low",
        reason="uncertain",
    )
    name, _arg, message = classification_to_command(classification)
    assert name == "unknown"
    assert message is not None


def test_parse_intent_json_accepts_valid_payload():
    classification = parse_intent_json(
        '{"intent":"review","arg":null,"confidence":"high","reason":"check file"}'
    )
    assert classification is not None
    name, arg, message = classification_to_command(classification)
    assert name == "review"
    assert arg is None
    assert message is None


def test_assistant_without_llm_intents_unchanged_for_fix_it(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output, llm_intents_enabled=False)

    assistant.handle(ParsedCommand(name="read", arg="demo_project/calculator.py"))
    assert assistant.handle(parse_command("fix it")) is True
    assert assistant.session.pending_edit is not None
    assert "PROPOSED EDIT" in output.getvalue()


def test_assistant_with_llm_intents_routes_ambiguous_fix_phrase(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(
        tmp_path,
        output=output,
        llm_intents_enabled=True,
        intent_classifier=_classifier_for_phrases(),
    )
    assistant.session.current_file_path = "demo_project/calculator.py"
    assistant.session.current_file_content = BUGGY_CALCULATOR

    command, _message = resolve_command(
        "can you help me fix this bug?",
        llm_intents_enabled=True,
        intent_classifier=_classifier_for_phrases(),
    )
    assert command is not None
    assistant.handle(command)

    assert assistant.session.pending_edit is not None
    assert "PROPOSED EDIT" in output.getvalue()


def test_assistant_with_llm_intents_unknown_shows_safe_message(tmp_path):
    output = StringIO()
    assistant = _assistant(
        tmp_path,
        output=output,
        llm_intents_enabled=True,
        intent_classifier=ScriptedIntentClassifier({}),
    )

    command, message = resolve_command(
        "compose a poem about recursion",
        llm_intents_enabled=True,
        intent_classifier=ScriptedIntentClassifier({}),
    )
    assert command.name == "unknown"
    assert message

    if message:
        assistant._emit(f"[STEP] {message}")
    assert "Could not confidently" in message
