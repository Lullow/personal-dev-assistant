from __future__ import annotations

import pytest
from io import StringIO
from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.demo.runner import BUGGY_RETURN, CALCULATOR_PATH, FIXED_RETURN
from personal_dev_assistant.interactive import (
    HELP_TEXT,
    READY_MESSAGE,
    InteractiveAssistant,
    ParsedCommand,
    WELCOME_NOTE,
    WELCOME_TITLE,
    parse_command,
    run_interactive,
)

BUGGY_CALCULATOR = "def add(a, b):\n    return a - b\n"
TEST_FILE = """from calculator import add


def test_add_returns_sum():
    assert add(2, 3) == 5
"""


def _write_demo_project(root: Path, *, calculator_source: str) -> None:
    demo_dir = root / "demo_project"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "calculator.py").write_text(calculator_source, encoding="utf-8")
    (demo_dir / "test_calculator.py").write_text(TEST_FILE, encoding="utf-8")


def _assistant(tmp_path: Path, *, output: StringIO | None = None) -> InteractiveAssistant:
    from personal_dev_assistant.budget import TokenBudgetMonitor

    buffer = output or StringIO()
    lines: list[str] = []

    def capture(text: str) -> None:
        lines.append(text)
        buffer.write(text + "\n")

    return InteractiveAssistant(
        app_config=AppConfig(),
        project_root=tmp_path,
        budget_monitor=TokenBudgetMonitor(AppConfig()),
        input_fn=lambda _prompt: "",
        output_fn=capture,
    )


def test_parse_command_help_and_exit():
    assert parse_command("help") == ParsedCommand(name="help")
    assert parse_command("  quit  ") == ParsedCommand(name="quit")
    assert parse_command("exit") == ParsedCommand(name="exit")


def test_parse_command_read_with_path():
    parsed = parse_command("read demo_project/calculator.py")
    assert parsed == ParsedCommand(name="read", arg="demo_project/calculator.py")


def test_parse_command_empty_line_returns_none():
    assert parse_command("") is None
    assert parse_command("   ") is None


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("list files", ParsedCommand(name="list")),
        ("show files", ParsedCommand(name="list")),
        ("show project files", ParsedCommand(name="list")),
        ("review it", ParsedCommand(name="review")),
        ("review file", ParsedCommand(name="review")),
        ("check it", ParsedCommand(name="review")),
        ("test it", ParsedCommand(name="test")),
        ("run tests", ParsedCommand(name="test")),
        ("run pytest", ParsedCommand(name="test")),
        ("fix bug", ParsedCommand(name="fix")),
        ("fix the bug", ParsedCommand(name="fix")),
        ("repair it", ParsedCommand(name="fix")),
        ("show tokens", ParsedCommand(name="tokens")),
        ("show token usage", ParsedCommand(name="tokens")),
        ("token usage", ParsedCommand(name="tokens")),
        ("budget", ParsedCommand(name="tokens")),
        ("cost", ParsedCommand(name="tokens")),
    ],
)
def test_parse_command_natural_phrases(line, expected):
    assert parse_command(line) == expected


@pytest.mark.parametrize(
    ("line", "path"),
    [
        ("open demo_project/calculator.py", "demo_project/calculator.py"),
        ("show demo_project/calculator.py", "demo_project/calculator.py"),
        ("cat demo_project/calculator.py", "demo_project/calculator.py"),
        ("inspect demo_project/calculator.py", "demo_project/calculator.py"),
        ("  Open   demo_project/calculator.py  ", "demo_project/calculator.py"),
    ],
)
def test_parse_command_natural_read_aliases(line, path):
    assert parse_command(line) == ParsedCommand(name="read", arg=path)


def test_parse_command_show_files_maps_to_list_not_read():
    assert parse_command("show files") == ParsedCommand(name="list")
    assert parse_command("show project files") == ParsedCommand(name="list")


def test_parse_command_show_tokens_maps_to_tokens_not_read():
    assert parse_command("show tokens") == ParsedCommand(name="tokens")
    assert parse_command("show token usage") == ParsedCommand(name="tokens")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("can you review it", ParsedCommand(name="review")),
        ("could you review it", ParsedCommand(name="review")),
        ("please run tests", ParsedCommand(name="test")),
        ("Please Can You review it", ParsedCommand(name="review")),
    ],
)
def test_parse_command_polite_prefixes(line, expected):
    assert parse_command(line) == expected


def test_parse_command_unknown_command_still_parsed():
    assert parse_command("foobar") == ParsedCommand(name="foobar")


def test_handle_unknown_command_suggests_help(tmp_path):
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)
    assert assistant.handle(ParsedCommand(name="foobar")) is True
    assert "Unknown command" in output.getvalue()
    assert "help" in output.getvalue()


def test_handle_natural_read_open_path(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    assistant = _assistant(tmp_path)

    parsed = parse_command("open demo_project/calculator.py")
    assert assistant.handle(parsed) is True
    assert assistant.last_read_path == CALCULATOR_PATH


def test_handle_natural_list_phrase(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assert assistant.handle(parse_command("show files")) is True
    assert "[OK] LIST" in output.getvalue()


def test_help_text_mentions_natural_commands():
    assert "Natural phrases also work" in HELP_TEXT
    assert "open <path>" in HELP_TEXT
    assert "run tests" in HELP_TEXT


def test_welcome_messages():
    output = StringIO()
    assistant = _assistant(Path("/tmp"), output=output)
    assistant.print_welcome()
    text = output.getvalue()

    assert WELCOME_TITLE in text
    assert WELCOME_NOTE in text
    assert READY_MESSAGE in text


def test_handle_help_prints_commands():
    output = StringIO()
    assistant = _assistant(Path("/tmp"), output=output)
    assert assistant.handle(ParsedCommand(name="help")) is True
    assert "read <path>" in output.getvalue()


def test_handle_exit_returns_false():
    assistant = _assistant(Path("/tmp"))
    assert assistant.handle(ParsedCommand(name="exit")) is False
    assert assistant.handle(ParsedCommand(name="quit")) is False


def test_handle_read_sets_last_read_path(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    assistant = _assistant(tmp_path)

    assert assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH)) is True
    assert assistant.last_read_path == CALCULATOR_PATH


def test_handle_list_uses_safe_tool(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assert assistant.handle(ParsedCommand(name="list")) is True
    assert "[OK] LIST" in output.getvalue()


def test_handle_test_runs_pytest(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="test"))
    text = output.getvalue()
    assert "TEST" in text


def test_handle_fix_runs_agent_style_flow_and_applies_edit(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assert assistant.handle(ParsedCommand(name="fix")) is True
    text = output.getvalue()

    assert "[MAIN AGENT]" in text
    assert "[PLANNER]" in text
    assert "[EXPLORER]" in text
    assert "[CODER]" in text
    assert "[REVIEWER]" in text
    assert "[OK] PARTIAL_EDIT" in text
    assert "[OK] FIX Workflow complete" in text

    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert FIXED_RETURN in calculator_text
    assert BUGGY_RETURN not in calculator_text


def test_handle_tokens_shows_budget_status(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="fix"))
    assistant.handle(ParsedCommand(name="tokens"))
    text = output.getvalue()

    assert "TOKEN BUDGET" in text
    assert "Total tokens used:" in text
    assert "Remaining budget:" in text


def test_run_interactive_exits_on_quit(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    inputs = iter(["help", "quit"])

    exit_code = run_interactive(
        project_root=tmp_path,
        app_config=AppConfig(),
        input_fn=lambda _prompt: next(inputs),
        output_fn=lambda _text: None,
    )

    assert exit_code == 0


def test_run_interactive_exits_on_eof(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    exit_code = run_interactive(
        project_root=tmp_path,
        app_config=AppConfig(),
        input_fn=raise_eof,
        output_fn=lambda _text: None,
    )

    assert exit_code == 0
