"""Interactive Assistant v.2 terminal loop."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, RuntimeConfig
from personal_dev_assistant.context.compaction import compact_output
from personal_dev_assistant.demo.runner import BUGGY_RETURN, CALCULATOR_PATH, DEMO_PROJECT_DIR, FIXED_RETURN
from personal_dev_assistant.interactive.intents import IntentClassifier
from personal_dev_assistant.interactive.parsing import (
    HELP_TEXT,
    READY_MESSAGE,
    WELCOME_NOTE,
    WELCOME_TITLE,
    ParsedCommand,
    resolve_command,
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
        llm_intents_enabled: bool = False,
        intent_classifier: IntentClassifier | None = None,
    ) -> None:
        self.app_config = app_config
        self.project_root = project_root
        self.budget_monitor = budget_monitor
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.session = session or InteractiveSession()
        self.compaction_threshold = compaction_threshold
        self.llm_intents_enabled = llm_intents_enabled
        self.intent_classifier = intent_classifier

    @property
    def last_read_path(self) -> str | None:
        return self.session.current_file_path

    @last_read_path.setter
    def last_read_path(self, value: str | None) -> None:
        self.session.current_file_path = value

    def print_welcome(self) -> None:
        self._emit(WELCOME_TITLE)
        self._emit(WELCOME_NOTE)
        if self.llm_intents_enabled:
            self._emit("LLM intents on (routing only); file changes still need /apply.")
        if READY_MESSAGE:
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

            command, intent_message = resolve_command(
                line,
                llm_intents_enabled=self.llm_intents_enabled,
                intent_classifier=self.intent_classifier,
            )
            if command is None:
                continue
            if command.name == "unknown":
                if intent_message:
                    self._emit(f"[STEP] {intent_message}")
                else:
                    self._emit(
                        "Unknown command. Type 'help' for available commands."
                    )
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
            self._emit("[STEP] APPLY Applying edits requires explicit /apply.")
            self.session.record_action("apply", "Blocked plain apply; requires /apply.")
            return True
        if name == "apply_confirm":
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

        path, content = self._current_file_or_demo()
        if path is None or content is None:
            self._emit("[FAIL] REVIEW No file available to review.")
            self.session.record_action("review", "No file available.")
            return

        combined = review_current_file(path=path, content=content)
        self.session.last_review_summary = combined.summary

        self._emit(f"[REVIEW] {path}")
        self._emit(f"  code reviewer: {combined.code_reviewer.summary}")
        self._record_agent_tokens("code_reviewer", input_tokens=50, output_tokens=25)
        self._emit(f"  test agent: {combined.test_agent.summary}")
        self._record_agent_tokens("test_agent", input_tokens=50, output_tokens=25)
        self._emit(f"  fix planner: {combined.fix_planner.recommendation}")
        self._record_agent_tokens("fix_planner", input_tokens=50, output_tokens=25)

        if BUGGY_RETURN in content:
            self._emit(f"  bug: add() subtracts instead of adding.")
            self._emit(f"  fix: change `{BUGGY_RETURN}` to `{FIXED_RETURN}`.")
        else:
            self._emit(f"  summary: {combined.code_reviewer.summary}")
        self.session.record_action("review", f"Reviewed {path}.")

    def _handle_test(self) -> None:
        command = f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}"
        result = bash(command, project_root=self.project_root, config=self.app_config)
        marker = _marker(result.ok)
        self._emit(f"{marker} TEST {result.summary}")
        stdout = str(result.output.get("stdout", "")).strip()
        for line in _compact_pytest_output(stdout):
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
        if not proposal.ok:
            marker = _marker(proposal.ok)
            self._emit(f"{marker} PROPOSED EDIT {proposal.summary}")
            self.session.record_action("fix", proposal.summary)
            return

        edit_path = str(proposal.output.get("path", path))
        risk_level = str(proposal.output.get("risk_level", "unknown") or "unknown")
        mini_diff = str(proposal.output.get("mini_diff", _mini_diff(old_text, new_text)))
        self._emit(f"[PROPOSED EDIT] {edit_path}")
        self._emit(f"Risk: {risk_level}")
        self._emit("Status: reviewed, not applied")
        self._emit("Diff:")
        for line in mini_diff.splitlines():
            self._emit(f"  {line}")
        self._emit("Next: /apply to apply, reject to discard.")

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
        if not edit.ok:
            self._emit(f"{marker} APPLY {edit.summary}")
            self.session.record_action("apply", edit.summary)
            return

        self._emit(f"{marker} APPLY Updated {pending.path} via partial_edit.")
        if edit.summary:
            self._emit(f"   {edit.summary}")

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
        max_tokens = self.app_config.token_budget.max_tokens
        pct = status.percentage_used * 100
        self._emit("[TOKENS]")
        self._emit(
            f"Used: {status.total_tokens_used} / {max_tokens} tokens ({pct:.1f}%)"
        )
        self._emit(
            f"Input/output: {status.input_tokens_used} / {status.output_tokens_used}"
        )
        self._emit(f"Estimated cost: ${status.estimated_cost_usd:.6f}")
        if status.warning_reached:
            self._emit("Warning: budget threshold reached.")
        if status.message:
            self._emit(f"Note: {status.message}")
        self._emit("Mode: deterministic local estimate")
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

        token_status = self.budget_monitor.status()
        trigger = "manual" if manual else "automatic"
        self._emit(f"[OK] COMPACT Context compacted ({trigger}).")
        self._emit("Preserved:")
        if self.session.current_file_path:
            self._emit(f"  current file: {self.session.current_file_path}")
        else:
            self._emit("  current file: (none)")
        pending_summary = self.session.pending_edit_summary()
        self._emit(f"  pending edit: {pending_summary or '(none)'}")
        if self.session.last_review_summary:
            review_line = compact_output(
                self.session.last_review_summary.splitlines()[0],
                config=self.app_config,
                max_chars=120,
            ).text
            self._emit(f"  last review: {review_line}")
        else:
            self._emit("  last review: (none)")
        if self.session.last_test_result:
            self._emit(f"  last test: {self.session.last_test_result}")
        else:
            self._emit("  last test: (none)")
        self._emit(f"  tokens used: {token_status.total_tokens_used}")
        self._emit(
            f"History: kept {len(self.session.action_history)} actions "
            f"(was {before_count}, {before_chars} chars)"
        )

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
    llm_intents: bool = False,
    intent_classifier: IntentClassifier | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> int:
    from personal_dev_assistant.config import RuntimeConfig, load_runtime_config
    from personal_dev_assistant.interactive.intents import create_intent_classifier

    budget_monitor = TokenBudgetMonitor(app_config)
    classifier = intent_classifier
    llm_intents_enabled = llm_intents

    if llm_intents_enabled and classifier is None:
        runtime = runtime_config or load_runtime_config()
        classifier = create_intent_classifier(runtime, budget_monitor=budget_monitor)

    assistant = InteractiveAssistant(
        app_config=app_config,
        project_root=Path(project_root).resolve(),
        budget_monitor=budget_monitor,
        input_fn=input_fn or input,
        output_fn=output_fn or print,
        llm_intents_enabled=llm_intents_enabled,
        intent_classifier=classifier,
    )
    return assistant.run_loop()


def _marker(ok: bool) -> str:
    return "[OK]" if ok else "[FAIL]"


def _mini_diff(old_line: str, new_line: str) -> str:
    return f"- {old_line}\n+ {new_line}"


def _compact_pytest_output(stdout: str) -> list[str]:
    """Return a short pytest summary for terminal display."""

    if not stdout.strip():
        return []

    highlights: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if " passed in " in stripped or " failed in " in stripped or " error in " in stripped:
            highlights = [stripped]
        elif stripped.startswith("FAILED ") or stripped.startswith("PASSED "):
            highlights.append(stripped)

    if highlights:
        return highlights[-2:]

    compact = compact_output(stdout, max_chars=400).text
    return [line for line in compact.splitlines() if line.strip()][:3]
