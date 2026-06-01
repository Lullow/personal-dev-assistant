"""Interactive Assistant v.2 terminal loop."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.context.compaction import compact_output
from personal_dev_assistant.demo.runner import BUGGY_RETURN, CALCULATOR_PATH, DEMO_PROJECT_DIR, FIXED_RETURN
from personal_dev_assistant.interactive.parsing import (
    HELP_TEXT,
    READY_MESSAGE,
    WELCOME_NOTE,
    WELCOME_TITLE,
    ParsedCommand,
    parse_command,
)
from personal_dev_assistant.interactive.review import review_current_file, suggest_fix_for_content
from personal_dev_assistant.interactive.session import InteractiveSession, PendingEdit
from personal_dev_assistant.models import TokenUsage
from personal_dev_assistant.tools import bash, list_project_files, partial_edit, propose_edit, read_file

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

DEFAULT_COMPACTION_THRESHOLD = 1_500
MAX_ACTION_HISTORY_AFTER_COMPACT = 5


class InteractiveAssistant:
    """Stateful deterministic terminal assistant for presentation use."""

    def __init__(
        self,
        *,
        app_config: AppConfig,
        project_root: Path,
        budget_monitor: TokenBudgetMonitor,
        input_fn: InputFn,
        output_fn: OutputFn,
        session: InteractiveSession | None = None,
        compaction_threshold: int = DEFAULT_COMPACTION_THRESHOLD,
    ) -> None:
        self.app_config = app_config
        self.project_root = project_root
        self.budget_monitor = budget_monitor
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.session = session or InteractiveSession()
        self.compaction_threshold = compaction_threshold

    @property
    def last_read_path(self) -> str | None:
        return self.session.current_file_path

    @last_read_path.setter
    def last_read_path(self, value: str | None) -> None:
        self.session.current_file_path = value

    def print_welcome(self) -> None:
        self._emit(WELCOME_TITLE)
        self._emit(WELCOME_NOTE)
        self._emit(f"Type help to see available commands.")
        self._emit(READY_MESSAGE)

    def run_loop(self) -> int:
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
            self.finalize_command()

    def handle(self, command: ParsedCommand) -> bool:
        name = command.name
        if name in {"exit", "quit"}:
            return False
        if name == "help":
            self._handle_help()
            return True
        if name == "list":
            self._handle_list()
            return True
        if name == "read":
            self._handle_open(command.arg)
            return True
        if name == "current":
            self._handle_show_current_file()
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
        if name == "apply":
            self._handle_apply()
            return True
        if name == "reject":
            self._handle_reject()
            return True
        if name == "tokens":
            self._handle_tokens()
            return True
        if name == "compact":
            self._handle_compact_context(manual=True)
            return True

        self._emit(f"Unknown command: {command.name}. Type 'help' for available commands.")
        return True

    def finalize_command(self) -> None:
        """Run post-command maintenance such as automatic context compaction."""

        self._maybe_auto_compact()

    def _handle_help(self) -> None:
        self._emit(HELP_TEXT)
        self.session.record_action("help", "Displayed command help.")

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
        self.session.record_action("list", result.summary)

    def _handle_open(self, path: str | None) -> None:
        if not path:
            self._emit("[FAIL] OPEN Missing path. Usage: open <path>")
            return

        result = read_file(path, project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} OPEN {result.summary}")
        if not result.ok:
            self.session.record_action("open", result.summary)
            return

        relative_path = str(result.output.get("path", path))
        content = str(result.output.get("content", ""))
        self.session.current_file_path = relative_path
        self.session.current_file_content = content
        self._emit(f"   Current file: {relative_path}")
        self._emit("   --- file preview ---")
        for preview_line in self.session.compact_preview(content).splitlines():
            self._emit(f"   {preview_line}")
        self.session.record_action("open", f"Opened {relative_path} ({len(content)} chars).")

    def _handle_show_current_file(self) -> None:
        if not self.session.current_file_path:
            self._emit("[STEP] CURRENT FILE")
            self._emit("   No file open. Use: open <path>")
            self.session.record_action("current", "No current file.")
            return

        path = self.session.current_file_path
        content = self.session.current_file_content or ""
        if content == "" and path:
            result = read_file(path, project_root=self.project_root, config=self.app_config)
            if result.ok:
                content = str(result.output.get("content", ""))
                self.session.current_file_content = content

        self._emit("[STEP] CURRENT FILE")
        self._emit(f"   Path: {path}")
        self._emit("   --- content preview ---")
        for preview_line in self.session.compact_preview(content).splitlines():
            self._emit(f"   {preview_line}")
        self.session.record_action("current", f"Showed {path}.")

    def _handle_review(self) -> None:
        self._record_agent_tokens("review", input_tokens=80, output_tokens=40)
        self._emit("[MAIN ASSISTANT] Delegating review to deterministic subagents...")

        path, content = self._current_file_or_demo()
        if path is None or content is None:
            self._emit("[FAIL] REVIEW No file available to review.")
            self.session.record_action("review", "No file available.")
            return

        combined = review_current_file(path=path, content=content)
        self.session.last_review_summary = combined.summary

        self._emit("[CODE REVIEWER]")
        self._emit(f"   {combined.code_reviewer.summary}")
        self._emit(f"   Finding: {combined.code_reviewer.finding}")
        self._record_agent_tokens("code_reviewer", input_tokens=50, output_tokens=25)

        self._emit("[TEST AGENT]")
        self._emit(f"   {combined.test_agent.summary}")
        self._emit(f"   Finding: {combined.test_agent.finding}")
        self._record_agent_tokens("test_agent", input_tokens=50, output_tokens=25)

        self._emit("[FIX PLANNER]")
        self._emit(f"   {combined.fix_planner.summary}")
        self._emit(f"   Recommendation: {combined.fix_planner.recommendation}")
        self._record_agent_tokens("fix_planner", input_tokens=50, output_tokens=25)

        self._emit("[MAIN ASSISTANT] Review summary:")
        if BUGGY_RETURN in content:
            self._emit("   add() subtracts instead of adding.")
            self._emit(f"   Suggested fix: change `{BUGGY_RETURN}` to `{FIXED_RETURN}`.")
        else:
            self._emit(f"   {combined.code_reviewer.summary}")
        self.session.record_action("review", f"Reviewed {path}.")

    def _handle_test(self) -> None:
        command = f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}"
        result = bash(command, project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} TEST {result.summary}")
        stdout = str(result.output.get("stdout", "")).strip()
        if stdout:
            preview = compact_output(stdout, config=self.app_config).text
            for line in preview.splitlines()[:8]:
                self._emit(f"   {line}")
        self.session.last_test_result = result.summary
        self.session.record_action("test", result.summary)

    def _handle_fix(self) -> None:
        self._record_agent_tokens("fix", input_tokens=90, output_tokens=45)
        path, content = self._current_file_or_demo(require_current=True)
        if path is None or content is None:
            self._emit("[FAIL] FIX Open a file first with: open <path>")
            self.session.record_action("fix", "No current file.")
            return

        suggestion = suggest_fix_for_content(content)
        if suggestion is None:
            self._emit("[FAIL] FIX No automatic fix available for the current file.")
            self.session.record_action("fix", f"No fix suggestion for {path}.")
            return

        old_text, new_text, reason = suggestion
        proposal = propose_edit(
            path,
            old_text,
            new_text,
            reason,
            project_root=self.project_root,
            config=self.app_config,
            apply=False,
        )
        marker = _marker(proposal.ok)
        self._emit(f"{marker} PROPOSED EDIT {proposal.summary}")
        if not proposal.ok:
            self.session.record_action("fix", proposal.summary)
            return

        mini_diff = str(proposal.output.get("mini_diff", _mini_diff(old_text, new_text)))
        self._emit("   --- mini diff ---")
        for line in mini_diff.splitlines():
            self._emit(f"   {line}")
        self._emit("   Pending edit created. Use `apply` to change the file or `reject` to discard.")

        self.session.pending_edit = PendingEdit(
            path=str(proposal.output.get("path", path)),
            old_text=old_text,
            new_text=new_text,
            reason=reason,
            mini_diff=mini_diff,
            risk_level=str(proposal.output.get("risk_level", "")) or None,
            reviewer_summary=str(proposal.output.get("reviewer_summary", "")) or None,
        )
        self.session.record_action("fix", f"Pending edit for {path}.")

    def _handle_apply(self) -> None:
        pending = self.session.pending_edit
        if pending is None:
            self._emit("[FAIL] APPLY No pending edit. Use `fix` first.")
            self.session.record_action("apply", "No pending edit.")
            return

        edit = partial_edit(
            pending.path,
            pending.old_text,
            pending.new_text,
            pending.reason,
            project_root=self.project_root,
            config=self.app_config,
        )
        marker = _marker(edit.ok)
        self._emit(f"{marker} APPLY {edit.summary}")
        if not edit.ok:
            self.session.record_action("apply", edit.summary)
            return

        if pending.path == self.session.current_file_path:
            refreshed = read_file(
                pending.path,
                project_root=self.project_root,
                config=self.app_config,
            )
            if refreshed.ok:
                self.session.current_file_content = str(refreshed.output.get("content", ""))

        self.session.pending_edit = None
        self.session.record_action("apply", f"Applied edit to {pending.path}.")

    def _handle_reject(self) -> None:
        if self.session.pending_edit is None:
            self._emit("[STEP] REJECT No pending edit to clear.")
            self.session.record_action("reject", "No pending edit.")
            return

        path = self.session.pending_edit.path
        self.session.pending_edit = None
        self._emit(f"[OK] REJECT Cleared pending edit for {path}. No files were changed.")
        self.session.record_action("reject", f"Cleared pending edit for {path}.")

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
        self._emit("   Note: chat mode uses deterministic local estimates unless a live LLM is wired in.")
        self.session.record_action("tokens", f"{status.total_tokens_used} tokens used.")

    def _handle_compact_context(self, *, manual: bool) -> None:
        before_count = len(self.session.action_history)
        before_chars = self.session.history_char_count

        preserved: list[str] = []
        if self.session.current_file_path:
            preserved.append(f"current file: {self.session.current_file_path}")
        pending_summary = self.session.pending_edit_summary()
        if pending_summary:
            preserved.append(pending_summary)
        if self.session.last_review_summary:
            compact_review = compact_output(
                self.session.last_review_summary,
                config=self.app_config,
                max_chars=240,
            ).text.replace("\n", " ")
            preserved.append(f"last review: {compact_review}")
        if self.session.last_test_result:
            preserved.append(f"last test: {self.session.last_test_result}")

        recent = self.session.action_history[-MAX_ACTION_HISTORY_AFTER_COMPACT:]
        summary_parts = preserved + [f"{record.command}: {record.summary}" for record in recent]
        self.session.context_summary = "; ".join(summary_parts)
        self.session.action_history = recent

        trigger = "manual" if manual else "automatic"
        self._emit(f"[OK] COMPACT Context compacted ({trigger}).")
        self._emit(f"   Actions before: {before_count} ({before_chars} chars)")
        self._emit(f"   Actions kept: {len(self.session.action_history)}")
        if self.session.context_summary:
            preview = compact_output(
                self.session.context_summary,
                config=self.app_config,
                max_chars=300,
            ).text
            self._emit(f"   Summary: {preview}")

    def _maybe_auto_compact(self) -> None:
        if self.session.history_char_count >= self.compaction_threshold:
            self._handle_compact_context(manual=False)

    def _current_file_or_demo(
        self,
        *,
        require_current: bool = False,
    ) -> tuple[str | None, str | None]:
        if self.session.current_file_path and self.session.current_file_content is not None:
            return self.session.current_file_path, self.session.current_file_content
        if self.session.current_file_path:
            result = read_file(
                self.session.current_file_path,
                project_root=self.project_root,
                config=self.app_config,
            )
            if result.ok:
                content = str(result.output.get("content", ""))
                self.session.current_file_content = content
                return self.session.current_file_path, content
            return self.session.current_file_path, None
        if require_current:
            return None, None

        calculator = read_file(
            CALCULATOR_PATH,
            project_root=self.project_root,
            config=self.app_config,
        )
        if not calculator.ok:
            return None, None
        return CALCULATOR_PATH, str(calculator.output.get("content", ""))

    def _record_agent_tokens(self, _step: str, *, input_tokens: int, output_tokens: int) -> None:
        self.budget_monitor.add_usage(
            TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        )

    def _emit(self, text: str) -> None:
        self.output_fn(text)


def run_interactive(
    *,
    project_root: str | Path = ".",
    app_config: AppConfig,
    input_fn: InputFn | None = None,
    output_fn: OutputFn | None = None,
) -> int:
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


def _mini_diff(old_line: str, new_line: str) -> str:
    return f"- {old_line}\n+ {new_line}"
