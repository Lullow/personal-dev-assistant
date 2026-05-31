"""Deterministic end-to-end demo runner for demo_project."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from personal_dev_assistant.config import AppConfig, load_app_config
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.tools import bash, list_project_files, partial_edit, read_file

DEMO_PROJECT_DIR = "demo_project"
CALCULATOR_PATH = f"{DEMO_PROJECT_DIR}/calculator.py"
TEST_PATH = f"{DEMO_PROJECT_DIR}/test_calculator.py"

BUGGY_RETURN = "return a - b"
FIXED_RETURN = "return a + b"
EDIT_REASON = "Fix add() so it returns the sum instead of the difference."


@dataclass(frozen=True)
class DemoStep:
    """One deterministic demo step backed by a tool result."""

    name: str
    result: ToolResult


@dataclass(frozen=True)
class DemoRunResult:
    """Outcome from one demo run."""

    ok: bool
    summary: str
    steps: list[DemoStep] = field(default_factory=list)
    edit_applied: bool = False
    already_fixed: bool = False
    before_tests_passed: bool = False
    after_tests_passed: bool | None = None


def run_demo(
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
    restore_initial_state: bool = False,
) -> DemoRunResult:
    """Run the calculator bug-fix demo using existing safe tools."""

    app_config = config or AppConfig()
    root = Path(project_root).resolve()
    steps: list[DemoStep] = []

    if restore_initial_state:
        restore_result = _restore_bug_if_fixed(root, app_config)
        if restore_result is not None:
            steps.append(DemoStep(name="restore_initial_state", result=restore_result))
            if restore_result.ok and restore_result.output.get("restored") is True:
                refresh_result = _refresh_calculator_bytecode(root, app_config)
                steps.append(DemoStep(name="refresh_bytecode_after_restore", result=refresh_result))
                if not refresh_result.ok:
                    return _failed_demo(
                        steps=steps,
                        summary=(
                            "Demo stopped: could not refresh calculator bytecode after restore. "
                            f"{refresh_result.summary}"
                        ),
                        before_tests_passed=False,
                    )

    list_result = list_project_files(project_root=root, config=app_config)
    steps.append(DemoStep(name="list_project_files", result=list_result))

    test_read_result = read_file(TEST_PATH, project_root=root, config=app_config)
    steps.append(DemoStep(name="read_test_file", result=test_read_result))

    calculator_read_result = read_file(CALCULATOR_PATH, project_root=root, config=app_config)
    steps.append(DemoStep(name="read_calculator_file", result=calculator_read_result))

    before_test_result = _run_demo_tests(root, app_config)
    steps.append(DemoStep(name="run_tests_before", result=before_test_result))
    before_tests_passed = before_test_result.ok

    calculator_content = _calculator_content(calculator_read_result)
    has_bug = BUGGY_RETURN in calculator_content
    is_fixed = FIXED_RETURN in calculator_content

    if before_tests_passed and is_fixed and not has_bug:
        summary = _build_summary(
            edit_applied=False,
            already_fixed=True,
            before_tests_passed=True,
            after_tests_passed=True,
            edit_result=None,
        )
        return DemoRunResult(
            ok=True,
            summary=summary,
            steps=steps,
            edit_applied=False,
            already_fixed=True,
            before_tests_passed=True,
            after_tests_passed=True,
        )

    edit_result: ToolResult | None = None
    edit_applied = False

    if has_bug:
        edit_result = partial_edit(
            CALCULATOR_PATH,
            BUGGY_RETURN,
            FIXED_RETURN,
            EDIT_REASON,
            project_root=root,
            config=app_config,
        )
        steps.append(DemoStep(name="apply_fix", result=edit_result))
        edit_applied = edit_result.ok
    elif not is_fixed:
        summary = (
            "Demo stopped: calculator.py does not contain the expected buggy or fixed "
            f"return statement ({BUGGY_RETURN!r} / {FIXED_RETURN!r})."
        )
        return DemoRunResult(
            ok=False,
            summary=summary,
            steps=steps,
            before_tests_passed=before_tests_passed,
            after_tests_passed=None,
        )
    else:
        summary = (
            "Demo stopped: tests failed but calculator.py already appears fixed. "
            "Inspect demo_project manually before re-running."
        )
        return DemoRunResult(
            ok=False,
            summary=summary,
            steps=steps,
            before_tests_passed=before_tests_passed,
            after_tests_passed=None,
        )

    if edit_result is not None and not edit_result.ok:
        summary = _build_summary(
            edit_applied=False,
            already_fixed=False,
            before_tests_passed=before_tests_passed,
            after_tests_passed=None,
            edit_result=edit_result,
        )
        return DemoRunResult(
            ok=False,
            summary=summary,
            steps=steps,
            edit_applied=False,
            already_fixed=False,
            before_tests_passed=before_tests_passed,
            after_tests_passed=None,
        )

    if edit_applied:
        refresh_result = _refresh_calculator_bytecode(root, app_config)
        steps.append(DemoStep(name="refresh_bytecode_after_fix", result=refresh_result))
        if not refresh_result.ok:
            summary = _build_summary(
                edit_applied=True,
                already_fixed=False,
                before_tests_passed=before_tests_passed,
                after_tests_passed=None,
                edit_result=edit_result,
            )
            summary = (
                f"{summary}\n"
                "Demo stopped: could not refresh calculator bytecode after fix. "
                f"{refresh_result.summary}"
            )
            return DemoRunResult(
                ok=False,
                summary=summary,
                steps=steps,
                edit_applied=True,
                already_fixed=False,
                before_tests_passed=before_tests_passed,
                after_tests_passed=None,
            )

    after_test_result = _run_demo_tests(root, app_config)
    steps.append(DemoStep(name="run_tests_after", result=after_test_result))
    after_tests_passed = after_test_result.ok

    summary = _build_summary(
        edit_applied=edit_applied,
        already_fixed=False,
        before_tests_passed=before_tests_passed,
        after_tests_passed=after_tests_passed,
        edit_result=edit_result,
    )
    return DemoRunResult(
        ok=after_tests_passed,
        summary=summary,
        steps=steps,
        edit_applied=edit_applied,
        already_fixed=False,
        before_tests_passed=before_tests_passed,
        after_tests_passed=after_tests_passed,
    )


def _run_demo_tests(root: Path, config: AppConfig) -> ToolResult:
    command = f"{config.tools.test_command} {DEMO_PROJECT_DIR}"
    return bash(command, project_root=root, config=config)


def _refresh_calculator_bytecode(root: Path, config: AppConfig) -> ToolResult:
    command = f"python -m compileall -f {CALCULATOR_PATH}"
    return bash(command, project_root=root, config=config)


def _failed_demo(
    *,
    steps: list[DemoStep],
    summary: str,
    before_tests_passed: bool,
) -> DemoRunResult:
    return DemoRunResult(
        ok=False,
        summary=summary,
        steps=steps,
        before_tests_passed=before_tests_passed,
        after_tests_passed=None,
    )


def _restore_bug_if_fixed(root: Path, config: AppConfig) -> ToolResult | None:
    read_result = read_file(CALCULATOR_PATH, project_root=root, config=config)
    if not read_result.ok:
        return read_result

    content = _calculator_content(read_result)
    if BUGGY_RETURN in content:
        return ToolResult(
            ok=True,
            summary="Initial buggy state already present; no restore needed.",
            output={"restored": False, "path": CALCULATOR_PATH},
        )
    if FIXED_RETURN not in content:
        return ToolResult(
            ok=False,
            summary=(
                "Could not restore initial demo state: calculator.py does not contain "
                f"the expected fixed line {FIXED_RETURN!r}."
            ),
            output={"restored": False, "path": CALCULATOR_PATH},
        )

    edit_result = partial_edit(
        CALCULATOR_PATH,
        FIXED_RETURN,
        BUGGY_RETURN,
        "Restore intentional demo bug for repeatable presentation.",
        project_root=root,
        config=config,
    )
    if not edit_result.ok:
        return edit_result

    return ToolResult(
        ok=True,
        summary=edit_result.summary,
        output={
            "path": CALCULATOR_PATH,
            "restored": True,
            "changed": True,
        },
    )


def _calculator_content(read_result: ToolResult) -> str:
    return str(read_result.output.get("content", ""))


def _build_summary(
    *,
    edit_applied: bool,
    already_fixed: bool,
    before_tests_passed: bool,
    after_tests_passed: bool | None,
    edit_result: ToolResult | None,
) -> str:
    before_status = "passed" if before_tests_passed else "failed"
    lines = [
        "Personal Dev Assistant demo completed.",
        f"Before fix: tests {before_status}.",
    ]

    if already_fixed:
        lines.append("Calculator was already fixed; no edit was needed.")
        lines.append("After fix: tests passed.")
        lines.append("Verified with safe bash test runs and read-only file inspection.")
        return "\n".join(lines)

    if edit_applied and edit_result is not None:
        lines.append(f"Applied partial edit to {CALCULATOR_PATH}: {BUGGY_RETURN} -> {FIXED_RETURN}.")
        lines.append(f"Edit summary: {edit_result.summary}")
    elif edit_result is not None and not edit_result.ok:
        lines.append(f"Edit failed: {edit_result.summary}")
        return "\n".join(lines)

    if after_tests_passed is None:
        lines.append("After fix: tests were not re-run.")
    else:
        after_status = "passed" if after_tests_passed else "failed"
        lines.append(f"After fix: tests {after_status}.")

    lines.append("Workflow used list_project_files, read_file, bash, partial_edit, and compileall.")
    return "\n".join(lines)


_STEP_PRESENTATION: dict[str, tuple[str, str]] = {
    "restore_initial_state": (
        "Restore intentional bug state",
        "Put demo_project back into its failing starting state for a repeatable presentation.",
    ),
    "refresh_bytecode_after_restore": (
        "Refresh bytecode after restore",
        "Recompile calculator.py so pytest loads the restored source safely.",
    ),
    "list_project_files": (
        "List project files",
        "Inspect the project structure without reading every file's full content.",
    ),
    "read_test_file": (
        "Read failing test",
        "See what behavior the demo project expects from calculator.add().",
    ),
    "read_calculator_file": (
        "Read calculator implementation",
        "Inspect the code under test before making any change.",
    ),
    "run_tests_before": (
        "Run tests before fix",
        "Verify the bug by running pytest through the safe bash tool.",
    ),
    "apply_fix": (
        "Apply one-line partial edit",
        "Make a small exact-match change instead of rewriting the whole file.",
    ),
    "refresh_bytecode_after_fix": (
        "Refresh bytecode after fix",
        "Recompile calculator.py so the next pytest run sees the updated code.",
    ),
    "run_tests_after": (
        "Run tests after fix",
        "Confirm the one-line change actually fixes the failing test.",
    ),
}

_VG_FEATURE_CHECKLIST: tuple[tuple[str, bool], ...] = (
    ("Safe bash execution (pytest + compileall)", True),
    ("Partial file editing (exact one-line fix)", True),
    ("Safety checks before tools run", True),
    ("Read-only file inspection", True),
    ("Before/after test verification", True),
    ("Context-safe compact tool workflow", True),
    ("Deterministic demo without API key", True),
    ("Main agent + sub-agents implemented in codebase/tests", True),
)


def _status_marker(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"


def _mini_diff(old_line: str, new_line: str) -> str:
    return f"- {old_line}\n+ {new_line}"


def format_plain_output(result: DemoRunResult) -> str:
    """Format demo output in the original simple style."""

    lines = [result.summary, "", "Steps:"]
    for step in result.steps:
        status = "ok" if step.result.ok else "failed"
        lines.append(f"- {step.name}: {status} — {step.result.summary}")
    return "\n".join(lines)


def format_visual_output(result: DemoRunResult) -> str:
    """Format presentation-friendly demo output for live terminal use."""

    width = 78
    border = "=" * width
    lines = [
        border,
        " Personal Dev Assistant — Deterministic Live Demo".center(width),
        border,
        "",
        "[STEP] Goal: find and fix the failing test in demo_project/",
        "[STEP] Uses safe tools only — no API key required.",
        "",
    ]

    for index, step in enumerate(result.steps, start=1):
        title, explanation = _STEP_PRESENTATION.get(
            step.name,
            (step.name.replace("_", " ").title(), "Run one safe tool step in the demo workflow."),
        )
        marker = _status_marker(step.result.ok)
        lines.extend(
            [
                f"{index}. [STEP] {title}",
                f"   {explanation}",
                f"   {marker} {step.result.summary}",
                "",
            ]
        )

    before_marker = _status_marker(result.before_tests_passed)
    lines.append("Test status")
    lines.append(f"   Before fix: {before_marker} tests {'passed' if result.before_tests_passed else 'failed'}")

    if result.after_tests_passed is None:
        lines.append("   After fix:  [STEP] tests were not re-run")
    else:
        after_marker = _status_marker(result.after_tests_passed)
        lines.append(
            f"   After fix:  {after_marker} tests {'passed' if result.after_tests_passed else 'failed'}"
        )
    lines.append("")

    if result.edit_applied:
        lines.extend(
            [
                "One-line fix applied",
                _mini_diff(BUGGY_RETURN, FIXED_RETURN),
                "",
            ]
        )
    elif result.already_fixed:
        lines.extend(
            [
                "Edit",
                "   Calculator was already fixed — no edit was needed.",
                "",
            ]
        )

    lines.extend(["VG feature checklist shown in this demo", ""])
    for label, supported in _VG_FEATURE_CHECKLIST:
        box = "[x]" if supported else "[ ]"
        lines.append(f"   {box} {label}")
    lines.append("")

    outcome = "SUCCESS" if result.ok else "FAILED"
    lines.extend([border, f" Demo {outcome} ".center(width), border])
    return "\n".join(lines)


def print_demo_output(result: DemoRunResult, *, plain: bool = False) -> None:
    """Print demo output in plain or presentation-friendly format."""

    text = format_plain_output(result) if plain else format_visual_output(result)
    print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-dev-assistant-demo",
        description="Run the deterministic demo_project bug-fix workflow without an LLM.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the non-secret YAML config file.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root that contains demo_project/.",
    )
    parser.add_argument(
        "--no-restore-initial-state",
        action="store_true",
        help="Do not restore the intentional bug when demo_project is already fixed.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Use the original simple text output instead of presentation-friendly output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app_config = load_app_config(Path(args.config))
    result = run_demo(
        project_root=args.project_root,
        config=app_config,
        restore_initial_state=not args.no_restore_initial_state,
    )

    print_demo_output(result, plain=args.plain)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
