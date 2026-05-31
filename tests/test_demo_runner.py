from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.demo.runner import (
    BUGGY_RETURN,
    CALCULATOR_PATH,
    FIXED_RETURN,
    format_plain_output,
    format_visual_output,
    main,
    run_demo,
)
from personal_dev_assistant.tools import bash

REPO_ROOT = Path(__file__).resolve().parents[1]

BUGGY_CALCULATOR = "def add(a, b):\n    return a - b\n"
FIXED_CALCULATOR = "def add(a, b):\n    return a + b\n"
TEST_FILE = """from calculator import add


def test_add_returns_sum():
    assert add(2, 3) == 5
"""


def _write_demo_project(root: Path, *, calculator_source: str) -> None:
    demo_dir = root / "demo_project"
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "calculator.py").write_text(calculator_source, encoding="utf-8")
    (demo_dir / "test_calculator.py").write_text(TEST_FILE, encoding="utf-8")


def test_demo_detects_failing_test(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())

    assert result.before_tests_passed is False
    before_step = next(step for step in result.steps if step.name == "run_tests_before")
    assert before_step.result.ok is False
    assert before_step.result.exit_code != 0


def test_demo_applies_intended_one_line_fix(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())

    assert result.edit_applied is True
    edit_step = next(step for step in result.steps if step.name == "apply_fix")
    assert edit_step.result.ok is True
    assert edit_step.result.output["changed"] is True

    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert FIXED_RETURN in calculator_text
    assert BUGGY_RETURN not in calculator_text


def test_demo_verifies_tests_pass_after_fix(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())

    assert result.ok is True
    assert result.after_tests_passed is True
    after_step = next(step for step in result.steps if step.name == "run_tests_after")
    assert after_step.result.ok is True
    assert after_step.result.exit_code == 0


def test_demo_summary_includes_before_and_after_test_results(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())

    assert "Before fix: tests failed." in result.summary
    assert "After fix: tests passed." in result.summary
    assert BUGGY_RETURN in result.summary
    assert FIXED_RETURN in result.summary


def test_demo_uses_safe_tool_flow(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())

    step_names = [step.name for step in result.steps]
    assert step_names[:4] == [
        "list_project_files",
        "read_test_file",
        "read_calculator_file",
        "run_tests_before",
    ]
    assert "apply_fix" in step_names
    assert "refresh_bytecode_after_fix" in step_names
    assert "run_tests_after" in step_names

    for step in result.steps:
        if step.name.startswith("run_tests") or step.name.startswith("refresh_bytecode"):
            assert step.result.output.get("executed") is True
            assert "command" in step.result.output
        if step.name == "apply_fix":
            assert step.result.output.get("changed") is True

    blocked = bash("rm -rf demo_project", project_root=tmp_path, config=AppConfig())
    assert blocked.ok is False
    assert blocked.output["executed"] is False


def test_demo_skips_edit_when_already_fixed(tmp_path):
    _write_demo_project(tmp_path, calculator_source=FIXED_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig(), restore_initial_state=False)

    assert result.ok is True
    assert result.already_fixed is True
    assert result.edit_applied is False
    assert "no edit was needed" in result.summary.lower()
    assert not any(step.name == "apply_fix" for step in result.steps)


def test_demo_can_restore_initial_state_for_repeatable_runs(tmp_path):
    _write_demo_project(tmp_path, calculator_source=FIXED_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig(), restore_initial_state=True)

    assert result.ok is True
    assert result.edit_applied is True
    assert result.before_tests_passed is False
    assert result.after_tests_passed is True
    assert any(step.name == "restore_initial_state" for step in result.steps)

    calculator_text = (tmp_path / CALCULATOR_PATH).read_text(encoding="utf-8")
    assert FIXED_RETURN in calculator_text
    assert BUGGY_RETURN not in calculator_text


def test_visual_output_includes_markers_diff_and_checklist(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())
    visual = format_visual_output(result)

    assert "1. [STEP]" in visual
    assert "[STEP] Goal:" in visual
    assert "[FAIL]" in visual
    assert "[OK]" in visual
    assert "Before fix: [FAIL]" in visual
    assert "After fix:  [OK]" in visual
    assert f"- {BUGGY_RETURN}" in visual
    assert f"+ {FIXED_RETURN}" in visual
    assert "VG feature checklist" in visual
    assert "[x] Safe bash execution" in visual
    assert "Demo SUCCESS" in visual


def test_plain_output_matches_original_style(tmp_path):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    result = run_demo(project_root=tmp_path, config=AppConfig())
    plain = format_plain_output(result)

    assert "Before fix: tests failed." in plain
    assert "After fix: tests passed." in plain
    assert "Steps:" in plain
    assert "- list_project_files: ok" in plain
    assert "[STEP]" not in plain


def test_main_uses_visual_output_by_default(tmp_path, capsys):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    exit_code = main(
        [
            "--project-root",
            str(tmp_path),
            "--config",
            str(REPO_ROOT / "config.yaml"),
        ]
    )
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Personal Dev Assistant — Deterministic Live Demo" in captured
    assert "[STEP]" in captured
    assert "VG feature checklist" in captured


def test_main_supports_plain_flag(tmp_path, capsys):
    _write_demo_project(tmp_path, calculator_source=BUGGY_CALCULATOR)

    exit_code = main(
        [
            "--project-root",
            str(tmp_path),
            "--config",
            str(REPO_ROOT / "config.yaml"),
            "--plain",
        ]
    )
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "Steps:" in captured
    assert "VG feature checklist" not in captured
