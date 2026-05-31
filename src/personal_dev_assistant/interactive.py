"""Deterministic interactive terminal assistant mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.demo.runner import (
    BUGGY_RETURN,
    CALCULATOR_PATH,
    DEMO_PROJECT_DIR,
    EDIT_REASON,
    FIXED_RETURN,
    TEST_PATH,
)
from personal_dev_assistant.models import TokenUsage
from personal_dev_assistant.tools import bash, list_project_files, partial_edit, read_file

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

WELCOME_TITLE = "Personal Dev Assistant"
WELCOME_NOTE = (
    "Deterministic interactive mode — not a free-form LLM session. "
    "No API key required."
)
READY_MESSAGE = "Ready when you are."

HELP_TEXT = """
Commands:
  help              Show this help
  exit, quit        Leave interactive mode
  list              List project files safely
  read <path>       Read a project file with safety checks
  review            Review demo_project or the last file you read
  test              Run pytest on demo_project through the safe bash tool
  fix               Run the scripted multi-agent fix workflow on demo_project
  tokens            Show token budget status for this session
""".strip()


@dataclass(frozen=True)
class ParsedCommand:
    """One parsed interactive command."""

    name: str
    arg: str | None = None


@dataclass
class InteractiveAssistant:
    """Small deterministic terminal assistant for presentation use."""

    app_config: AppConfig
    project_root: Path
    budget_monitor: TokenBudgetMonitor
    input_fn: InputFn
    output_fn: OutputFn
    last_read_path: str | None = None

    def print_welcome(self) -> None:
        self._emit(WELCOME_TITLE)
        self._emit(WELCOME_NOTE)
        self._emit(READY_MESSAGE)

    def run_loop(self) -> int:
        """Run the interactive command loop."""

        self.print_welcome()
        while True:
            try:
                line = self.input_fn("> ")
            except EOFError:
                self._emit("")
                self._emit("Goodbye.")
                return 0

            command = parse_command(line)
            if command is None:
                continue
            if not self.handle(command):
                self._emit("Goodbye.")
                return 0

    def handle(self, command: ParsedCommand) -> bool:
        """Handle one command. Returns False when the session should exit."""

        name = command.name
        if name in {"exit", "quit"}:
            return False
        if name == "help":
            self._emit(HELP_TEXT)
            return True
        if name == "list":
            self._handle_list()
            return True
        if name == "read":
            self._handle_read(command.arg)
            return True
        if name == "review":
            self._handle_review()
            return True
        if name == "test":
            self._handle_test()
            return True
        if name == "fix":
            self._handle_fix()
            return True
        if name == "tokens":
            self._handle_tokens()
            return True

        self._emit(f"Unknown command: {command.name}. Type 'help' for available commands.")
        return True

    def _handle_list(self) -> None:
        result = list_project_files(project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} LIST {result.summary}")
        if result.ok:
            files = result.output.get("files", [])
            preview = ", ".join(files[:8])
            if len(files) > 8:
                preview = f"{preview}, ..."
            self._emit(f"   Files: {preview or 'none'}")

    def _handle_read(self, path: str | None) -> None:
        if not path:
            self._emit("[FAIL] READ Missing path. Usage: read <path>")
            return

        result = read_file(path, project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} READ {result.summary}")
        if not result.ok:
            return

        self.last_read_path = str(result.output.get("path", path))
        content = str(result.output.get("content", ""))
        self._emit("   --- file preview ---")
        for line in content.splitlines()[:12]:
            self._emit(f"   {line}")
        if len(content.splitlines()) > 12:
            self._emit("   ...")

    def _handle_review(self) -> None:
        self._record_agent_tokens("review", input_tokens=80, output_tokens=40)
        self._emit("[STEP] REVIEW")

        if self.last_read_path:
            result = read_file(
                self.last_read_path,
                project_root=self.project_root,
                config=self.app_config,
            )
            if not result.ok:
                self._emit(f"[FAIL] REVIEW {result.summary}")
                return
            content = str(result.output.get("content", ""))
            self._emit(f"   Last read file: {self.last_read_path}")
            self._emit(f"   Summary: {_review_summary(content)}")
            return

        calculator = read_file(
            CALCULATOR_PATH,
            project_root=self.project_root,
            config=self.app_config,
        )
        if not calculator.ok:
            self._emit("[FAIL] REVIEW Could not read demo_project files for review.")
            return

        self._emit("   Review target: demo_project/")
        self._emit("   Test expectation: add(2, 3) should equal 5")
        self._emit(f"   Finding: {_review_summary(str(calculator.output.get('content', '')))}")

    def _handle_test(self) -> None:
        command = f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}"
        result = bash(command, project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} TEST {result.summary}")

    def _handle_fix(self) -> None:
        self._emit("[MAIN AGENT] Task received: Fix the failing test in demo_project/")
        self._record_agent_tokens("main_agent", input_tokens=120, output_tokens=60)

        self._emit("[PLANNER] Plan:")
        self._emit("   1. Inspect demo_project files")
        self._emit("   2. Run tests to confirm failure")
        self._emit("   3. Apply one minimal exact-match edit")
        self._emit("   4. Refresh bytecode and re-run tests")
        self._record_agent_tokens("planner", input_tokens=90, output_tokens=45)

        calculator = read_file(
            CALCULATOR_PATH,
            project_root=self.project_root,
            config=self.app_config,
        )
        if not calculator.ok:
            self._emit("[FAIL] EXPLORER Could not inspect demo_project files.")
            return

        content = str(calculator.output.get("content", ""))
        self._emit("[EXPLORER] Findings:")
        self._emit("   - Test file expects add(2, 3) == 5")
        self._emit(f"   - {_explorer_finding(content)}")
        self._record_agent_tokens("explorer", input_tokens=100, output_tokens=50)

        before = bash(
            f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}",
            project_root=self.project_root,
            config=self.app_config,
        )
        self._emit(f"{_marker(before.ok)} BASH before fix: {before.summary}")

        if BUGGY_RETURN not in content:
            if FIXED_RETURN in content and before.ok:
                self._emit("[CODER] No edit needed — calculator already fixed.")
                self._emit("[REVIEWER] Risk: low — nothing to change.")
                self._emit("[OK] FIX Workflow complete.")
                return
            self._emit("[FAIL] CODER Could not find the expected buggy line to replace.")
            return

        self._emit("[CODER] Proposed one-line fix:")
        self._emit(f"   - {BUGGY_RETURN}")
        self._emit(f"   + {FIXED_RETURN}")
        self._record_agent_tokens("coder", input_tokens=70, output_tokens=35)

        self._emit("[REVIEWER] Risk: low — approve exact-match edit in demo_project/calculator.py")
        self._record_agent_tokens("reviewer", input_tokens=60, output_tokens=30)

        edit = partial_edit(
            CALCULATOR_PATH,
            BUGGY_RETURN,
            FIXED_RETURN,
            EDIT_REASON,
            project_root=self.project_root,
            config=self.app_config,
        )
        self._emit(f"{_marker(edit.ok)} PARTIAL_EDIT {edit.summary}")
        if not edit.ok:
            return

        refresh = bash(
            f"python -m compileall -f {CALCULATOR_PATH}",
            project_root=self.project_root,
            config=self.app_config,
        )
        self._emit(f"{_marker(refresh.ok)} BYTECODE {refresh.summary}")
        if not refresh.ok:
            return

        after = bash(
            f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}",
            project_root=self.project_root,
            config=self.app_config,
        )
        self._emit(f"{_marker(after.ok)} BASH after fix: {after.summary}")
        if after.ok:
            self._emit("[OK] FIX Workflow complete — tests pass.")
        else:
            self._emit("[FAIL] FIX Workflow finished but tests still fail.")

    def _handle_tokens(self) -> None:
        status = self.budget_monitor.status()
        self._emit("[STEP] TOKEN BUDGET")
        self._emit(f"   Total tokens used: {status.total_tokens_used}")
        self._emit(f"   Input tokens used: {status.input_tokens_used}")
        self._emit(f"   Output tokens used: {status.output_tokens_used}")
        self._emit(f"   Remaining budget: {status.remaining_tokens}")
        self._emit(f"   Percentage used: {status.percentage_used:.1%}")
        self._emit(f"   Estimated cost (USD): ${status.estimated_cost_usd:.6f}")
        if status.warning_reached:
            self._emit("   Warning threshold reached.")
        if status.message:
            self._emit(f"   {status.message}")

    def _record_agent_tokens(self, _step: str, *, input_tokens: int, output_tokens: int) -> None:
        self.budget_monitor.add_usage(
            TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        )

    def _emit(self, text: str) -> None:
        self.output_fn(text)


def parse_command(line: str) -> ParsedCommand | None:
    """Parse one interactive command line."""

    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None
    return ParsedCommand(name=name, arg=arg)


def run_interactive(
    *,
    project_root: str | Path = ".",
    app_config: AppConfig,
    input_fn: InputFn | None = None,
    output_fn: OutputFn | None = None,
) -> int:
    """Start the interactive assistant loop."""

    assistant = InteractiveAssistant(
        app_config=app_config,
        project_root=Path(project_root).resolve(),
        budget_monitor=TokenBudgetMonitor(app_config),
        input_fn=input_fn or input,
        output_fn=output_fn or print,
    )
    return assistant.run_loop()


def _marker(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"


def _review_summary(content: str) -> str:
    if BUGGY_RETURN in content:
        return "calculator.add() appears to subtract instead of add."
    if FIXED_RETURN in content:
        return "calculator.add() appears to return the sum correctly."
    return "calculator.add() implementation needs manual inspection."


def _explorer_finding(content: str) -> str:
    if BUGGY_RETURN in content:
        return "calculator.add() currently returns a - b instead of a + b"
    if FIXED_RETURN in content:
        return "calculator.add() already uses addition"
    return "calculator.add() does not match the expected demo bug pattern"
