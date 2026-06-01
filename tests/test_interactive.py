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
    InteractiveSession,
    ParsedCommand,
    WELCOME_NOTE,
    WELCOME_TITLE,
    parse_command,
    review_current_file,
    run_interactive,
)
from personal_dev_assistant.interactive.assistant import DEFAULT_COMPACTION_THRESHOLD

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


def _assistant(
    tmp_path: Path,
    *,
    output: StringIO | None = None,
    session: InteractiveSession | None = None,
    compaction_threshold: int = DEFAULT_COMPACTION_THRESHOLD,
) -> InteractiveAssistant:
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
        session=session,
        compaction_threshold=compaction_threshold,
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
        ("show current file", ParsedCommand(name="current")),
        ("review it", ParsedCommand(name="review")),
        ("review this file", ParsedCommand(name="review")),
        ("review file", ParsedCommand(name="review")),
        ("check it", ParsedCommand(name="review")),
        ("test it", ParsedCommand(name="test")),
        ("run tests", ParsedCommand(name="test")),
        ("run pytest", ParsedCommand(name="test")),
        ("fix it", ParsedCommand(name="fix")),
        ("fix bug", ParsedCommand(name="fix")),
        ("fix the bug", ParsedCommand(name="fix")),
        ("repair it", ParsedCommand(name="fix")),
        ("apply", ParsedCommand(name="apply")),
        ("reject", ParsedCommand(name="reject")),
        ("show tokens", ParsedCommand(name="tokens")),
        ("show token usage", ParsedCommand(name="tokens")),
        ("token usage", ParsedCommand(name="tokens")),
        ("budget", ParsedCommand(name="tokens")),
        ("cost", ParsedCommand(name="tokens")),
        ("compact context", ParsedCommand(name="compact")),
        ("compact history", ParsedCommand(name="compact")),
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


def test_parse_command_show_current_file_not_treated_as_read():
    assert parse_command("show current file") == ParsedCommand(name="current")


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


def test_welcome_messages_mention_help():
    output = StringIO()
    assistant = _assistant(Path("/tmp"), output=output)
    assistant.print_welcome()
    text = output.getvalue()

    assert WELCOME_TITLE in text
    assert WELCOME_NOTE in text
    assert READY_MESSAGE in text
    assert "help" in text.lower()


def test_handle_help_prints_commands():
    output = StringIO()
    assistant = _assistant(Path("/tmp"), output=output)
    assert assistant.handle(ParsedCommand(name="help")) is True
    text = output.getvalue()
    assert "open <path>" in text
    assert "show current file" in text
    assert "apply" in text
    assert "reject" in text
    assert "compact context" in text


def test_help_text_mentions_natural_commands():
    assert "Natural phrases also work" in HELP_TEXT
    assert "open <path>" in HELP_TEXT
    assert "run tests" in HELP_TEXT
    assert "fix it" in HELP_TEXT


def test_handle_exit_returns_false():
    assistant = _assistant(Path("/tmp"))
    assert assistant.handle(ParsedCommand(name="exit")) is False
    assert assistant.handle(ParsedCommand(name="quit")) is False


def test_open_file_stores_current_file_state(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    assistant = _assistant(tmp_path)

    parsed = parse_command("open demo_project/calculator.py")
    assert assistant.handle(parsed) is True
    assert assistant.session.current_file_path == CALCULATOR_PATH
    assert BUGGY_RETURN in (assistant.session.current_file_content or "")
    assert assistant.last_read_path == CALCULATOR_PATH


def test_show_current_file_displays_path_and_content(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(ParsedCommand(name="current"))
    text = output.getvalue()

    assert "CURRENT FILE" in text
    assert CALCULATOR_PATH in text
    assert BUGGY_RETURN in text


def test_review_current_file_reports_add_subtract_bug(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(parse_command("can you review it"))
    text = output.getvalue()

    assert "[CODE REVIEWER]" in text
    assert "[TEST AGENT]" in text
    assert "[FIX PLANNER]" in text
    assert "[MAIN ASSISTANT]" in text
    assert "subtract" in text.lower()
    assert FIXED_RETURN in text
    assert assistant.session.last_review_summary is not None


def test_review_current_file_deterministic_subagents(tmp_path):
    combined = review_current_file(path=CALCULATOR_PATH, content=BUGGY_CALCULATOR)
    assert "subtract" in combined.code_reviewer.summary.lower()
    assert "add(2, 3)" in combined.test_agent.finding
    assert BUGGY_RETURN in combined.fix_planner.finding


def test_fix_creates_pending_edit_without_modifying_file(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(parse_command("fix it"))
    text = output.getvalue()

    assert "PROPOSED EDIT" in text
    assert "mini diff" in text.lower()
    assert "apply" in text.lower()
    assert assistant.session.pending_edit is not None
    assert assistant.session.pending_edit.path == CALCULATOR_PATH
    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert BUGGY_RETURN in calculator_text
    assert FIXED_RETURN not in calculator_text


def test_apply_modifies_file_after_explicit_command(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    assistant = _assistant(tmp_path)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(ParsedCommand(name="fix"))
    assistant.handle(ParsedCommand(name="apply"))

    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert FIXED_RETURN in calculator_text
    assert BUGGY_RETURN not in calculator_text
    assert assistant.session.pending_edit is None


def test_reject_clears_pending_edit_without_modifying_file(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    assistant = _assistant(tmp_path)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(ParsedCommand(name="fix"))
    assistant.handle(ParsedCommand(name="reject"))

    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert BUGGY_RETURN in calculator_text
    assert assistant.session.pending_edit is None


def test_handle_list_uses_safe_tool(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assert assistant.handle(ParsedCommand(name="list")) is True
    assert "[OK] LIST" in output.getvalue()


def test_handle_test_runs_pytest_demo_project(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="test"))
    text = output.getvalue()
    assert "TEST" in text
    assert assistant.session.last_test_result is not None


def test_handle_tokens_shows_budget_status(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assistant.handle(ParsedCommand(name="review"))
    assistant.handle(ParsedCommand(name="tokens"))
    text = output.getvalue()

    assert "TOKEN BUDGET" in text
    assert "Total tokens used:" in text
    assert "Remaining budget:" in text


def test_compact_context_preserves_current_file_and_pending_edit(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    session = InteractiveSession()
    assistant = _assistant(tmp_path, session=session, compaction_threshold=50)

    assistant.handle(ParsedCommand(name="read", arg=CALCULATOR_PATH))
    assistant.handle(ParsedCommand(name="fix"))
    assistant.handle(ParsedCommand(name="compact"))

    assert session.current_file_path == CALCULATOR_PATH
    assert session.pending_edit is not None
    assert "current file:" in session.context_summary
    assert "pending edit" in session.context_summary


def test_auto_compaction_triggers_when_history_grows(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output, compaction_threshold=80)

    for _ in range(6):
        assistant.handle(ParsedCommand(name="list"))
        assistant.finalize_command()

    assert "COMPACT Context compacted (automatic)" in output.getvalue()


def test_handle_natural_list_phrase(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)
    output = StringIO()
    assistant = _assistant(tmp_path, output=output)

    assert assistant.handle(parse_command("show files")) is True
    assert "[OK] LIST" in output.getvalue()


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
