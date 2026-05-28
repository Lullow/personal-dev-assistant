from __future__ import annotations

from personal_dev_assistant.config import AppConfig, ContextConfig, ToolsConfig
from personal_dev_assistant.tools import bash


def test_blocked_command_is_not_executed(tmp_path):
    result = bash("rm -rf demo_project", project_root=tmp_path)

    assert result.ok is False
    assert result.output["executed"] is False
    assert result.output["safety_decision"] == "blocked"
    assert "blocked" in result.summary.lower()


def test_outside_project_path_command_is_not_executed(tmp_path):
    result = bash("ls /", project_root=tmp_path)

    assert result.ok is False
    assert result.output["executed"] is False
    assert result.output["safety_decision"] == "blocked"
    assert "escapes project root" in result.output["reason"]


def test_parent_traversal_command_is_not_executed(tmp_path):
    result = bash("pytest ../other_project", project_root=tmp_path)

    assert result.ok is False
    assert result.output["executed"] is False
    assert result.output["safety_decision"] == "blocked"
    assert "escapes project root" in result.output["reason"]


def test_risky_command_is_not_executed_and_requires_confirmation(tmp_path):
    result = bash("pip install requests", project_root=tmp_path)

    assert result.ok is False
    assert result.output["executed"] is False
    assert result.output["requires_confirmation"] is True
    assert result.output["safety_decision"] == "risky_requires_confirmation"


def test_safe_command_executes_successfully(tmp_path):
    result = bash("pwd", project_root=tmp_path)

    assert result.ok is True
    assert result.exit_code == 0
    assert result.output["executed"] is True


def test_stdout_is_captured(tmp_path):
    (tmp_path / "demo_project").mkdir()
    (tmp_path / "demo_project" / "example.txt").write_text("ok\n", encoding="utf-8")

    result = bash("ls demo_project", project_root=tmp_path)

    assert result.ok is True
    assert "example.txt" in result.output["stdout"]
    assert result.output["stderr"] == ""


def test_stderr_and_exit_code_are_captured_for_failing_safe_command(tmp_path):
    result = bash("ls missing-file", project_root=tmp_path)

    assert result.ok is False
    assert result.exit_code != 0
    assert "missing-file" in result.output["stderr"]


def test_timeout_is_handled_safely(tmp_path):
    test_file = tmp_path / "test_sleep.py"
    test_file.write_text(
        "import time\n\n"
        "def test_slow():\n"
        "    time.sleep(2)\n",
        encoding="utf-8",
    )
    config = AppConfig(tools=ToolsConfig(command_timeout_seconds=1))

    result = bash("pytest test_sleep.py", project_root=tmp_path, config=config)

    assert result.ok is False
    assert result.exit_code is None
    assert result.output["timed_out"] is True
    assert "timed out" in result.summary.lower()


def test_long_stdout_is_compacted(tmp_path):
    test_file = tmp_path / "test_print.py"
    test_file.write_text(
        "def test_prints():\n"
        "    print('BEGIN-' + ('x' * 200) + '-END')\n",
        encoding="utf-8",
    )
    config = AppConfig(
        context=ContextConfig(max_observation_chars=80),
        tools=ToolsConfig(command_timeout_seconds=5),
    )

    result = bash("pytest -s test_print.py", project_root=tmp_path, config=config)

    assert result.ok is True
    assert result.truncated is True
    assert "[truncated" in result.output["stdout"]
    assert result.output["stdout"].startswith("=")
    assert result.output["stdout"].endswith("\n")
    assert result.output["stdout_compacted_char_count"] <= 80


def test_long_stderr_is_compacted(tmp_path):
    config = AppConfig(context=ContextConfig(max_observation_chars=80))
    missing_path = "missing-" + ("x" * 200)

    result = bash(f"ls {missing_path}", project_root=tmp_path, config=config)

    assert result.ok is False
    assert result.truncated is True
    assert "[truncated" in result.output["stderr"]
    assert result.output["stderr"].startswith("ls:")
    assert result.output["stderr"].endswith("file or directory\n")
    assert result.output["stderr_compacted_char_count"] <= 80


def test_command_runs_inside_project_root(tmp_path):
    result = bash("pwd", project_root=tmp_path)

    assert result.ok is True
    assert result.output["stdout"].strip() == str(tmp_path.resolve())


def test_python_module_pytest_safe_command_executes(tmp_path):
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = bash("python -m pytest test_ok.py", project_root=tmp_path)

    assert result.output["executed"] is True
    assert result.exit_code == 0


def test_normal_safe_path_arguments_still_execute(tmp_path):
    (tmp_path / "demo_project").mkdir()
    (tmp_path / "demo_project" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )

    ls_result = bash("ls demo_project", project_root=tmp_path)
    pytest_result = bash("pytest demo_project", project_root=tmp_path)
    python_pytest_result = bash("python -m pytest demo_project", project_root=tmp_path)

    assert ls_result.output["executed"] is True
    assert pytest_result.output["executed"] is True
    assert python_pytest_result.output["executed"] is True
