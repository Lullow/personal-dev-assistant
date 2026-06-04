"""Interactive Assistant v.2 terminal loop."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, RuntimeConfig
from personal_dev_assistant.context.compaction import compact_output
from personal_dev_assistant.demo.runner import CALCULATOR_PATH, DEMO_PROJECT_DIR
from personal_dev_assistant.interactive.bug_patterns import find_matching_bug_pattern
from personal_dev_assistant.interactive.intents import IntentClassifier
from personal_dev_assistant.interactive.parsing import (
    HELP_TEXT,
    READY_MESSAGE,
    WELCOME_HELP_HINT,
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
_BOX_WIDTH = 52
_LINE_SEP = "─" * _BOX_WIDTH


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
        self._emit(WELCOME_HELP_HINT)
        if self.llm_intents_enabled:
            self._emit("LLM intents on (routing only); file changes still need /apply.")
        if READY_MESSAGE:
            self._emit(READY_MESSAGE)

    def input_prompt(self) -> str:
        """Dynamic prompt label for the interactive loop."""

        if not self.session.current_file_path:
            return "pda > "
        file_label = Path(self.session.current_file_path).name
        if self.session.pending_edit is not None:
            return f"{file_label} [pending edit] > "
        return f"{file_label} > "

    def run_loop(self) -> int:
        self.print_welcome()
        while True:
            try:
                line = self.input_fn(self.input_prompt())
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

            self._begin_turn(line.strip())
            if command.name == "unknown":
                if intent_message:
                    self._emit_main(intent_message)
                else:
                    self._emit_main(
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
            self._emit_safety(
                "Edits require explicit `/apply`.",
                "Next: type `/apply` if you want to apply the proposed edit.",
            )
            self._emit_state()
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

        self._emit_main(
            f"Unknown command: {command.name}. Type 'help' for available commands."
        )
        return True

    def finalize_command(self) -> None:
        """Run post-command maintenance such as automatic context compaction."""

        self._maybe_auto_compact()

    def _handle_help(self) -> None:
        self._emit_main("Available commands:")
        for help_line in HELP_TEXT.splitlines():
            self._emit(help_line)
        self.session.record_action("help", "Displayed command help.")

    def _handle_list(self) -> None:
        self._emit_main("Listing project files...")
        result = list_project_files(project_root=self.project_root, config=self.app_config)
        self._emit_tool("LIST_PROJECT_FILES", result.ok, result.summary)
        if result.ok:
            files = result.output.get("files", [])
            preview = ", ".join(files[:8])
            if len(files) > 8:
                preview = f"{preview}, ..."
            self._emit(f"Files: {preview or 'none'}")
        self.session.record_action("list", result.summary)

    def _handle_open(self, path: str | None) -> None:
        if not path:
            self._emit_main("Missing path. Usage: open <path>")
            return

        self._emit_main("Opening file...")
        result = read_file(path, project_root=self.project_root, config=self.app_config)
        if not result.ok:
            self._emit_tool("READ_FILE", result.ok, result.summary)
            self.session.record_action("open", result.summary)
            return

        relative_path = str(result.output.get("path", path))
        content = str(result.output.get("content", ""))
        self.session.current_file_path = relative_path
        self.session.current_file_content = content
        self._emit_tool("READ_FILE", result.ok, f"Read {relative_path}")
        self._emit("")
        self._emit(f"Current file: {relative_path}")
        self._emit("")
        self._emit("Preview:")
        self._emit_numbered_preview(content)
        self._emit_state()
        self.session.record_action("open", f"Opened {relative_path} ({len(content)} chars).")

    def _handle_show_current_file(self) -> None:
        if not self.session.current_file_path:
            self._emit_main("No file open. Use: open <path>")
            self.session.record_action("current", "No current file.")
            return

        path = self.session.current_file_path
        content = self.session.current_file_content or ""
        if content == "" and path:
            result = read_file(path, project_root=self.project_root, config=self.app_config)
            if result.ok:
                content = str(result.output.get("content", ""))
                self.session.current_file_content = content

        self._emit_main(f"Current file: {path}")
        self._emit("")
        self._emit("Preview:")
        self._emit_numbered_preview(content)
        self._emit_state()
        self.session.record_action("current", f"Showed {path}.")

    def _handle_review(self) -> None:
        self._record_agent_tokens("review", input_tokens=80, output_tokens=40)

        path, content = self._current_file_or_demo()
        if path is None or content is None:
            self._emit_main("No file available to review.")
            self.session.record_action("review", "No file available.")
            return

        combined = review_current_file(path=path, content=content)
        pattern = find_matching_bug_pattern(path, content)
        self.session.last_review_summary = combined.summary

        self._emit_main(f"Reviewing {path} with subagents...")
        self._emit("")
        self._emit("Agent notes:")
        self._emit_agent_line("CODE REVIEWER", combined.code_reviewer.summary)
        self._record_agent_tokens("code_reviewer", input_tokens=50, output_tokens=25)
        self._emit_agent_line("TEST AGENT", combined.test_agent.summary)
        self._record_agent_tokens("test_agent", input_tokens=50, output_tokens=25)
        fix_hint = (
            "Create a proposed edit with `fix it`, then apply with `/apply`."
            if pattern is not None
            else combined.fix_planner.recommendation
        )
        self._emit_agent_line("FIX PLANNER", fix_hint)
        self._record_agent_tokens("fix_planner", input_tokens=50, output_tokens=25)

        self._emit("")
        self._emit("Summary:")
        if pattern is not None:
            self._emit(f"- {pattern.summary}")
            self._emit(f"- {pattern.test_hint}")
            self._emit(f"- Suggested fix is {pattern.risk_level} risk")
            self._emit("")
            self._emit("Next: type `fix it`")
        else:
            self._emit(f"- {combined.code_reviewer.summary}")
        self._emit_state()
        self.session.record_action("review", f"Reviewed {path}.")

    def _handle_test(self) -> None:
        command = f"{self.app_config.tools.test_command} {DEMO_PROJECT_DIR}"
        self._emit_main(f"Running tests: {command}")
        result = bash(command, project_root=self.project_root, config=self.app_config)
        self._emit_tool("BASH", result.ok, result.summary)
        stdout = str(result.output.get("stdout", "")).strip()
        pytest_lines = _compact_pytest_output(stdout)
        if pytest_lines:
            self._emit("")
            self._emit("Test result:")
            self._emit(_LINE_SEP)
            for line in pytest_lines:
                self._emit(line)
            self._emit(_LINE_SEP)
        self.session.last_test_result = result.summary
        self.session.last_test_passed = result.ok
        self._emit_state()
        self.session.record_action("test", result.summary)

    def _handle_fix(self) -> None:
        self._record_agent_tokens("fix", input_tokens=90, output_tokens=45)
        path, content = self._current_file_or_demo(require_current=True)
        if path is None or content is None:
            self._emit_main("Open a file first with: open <path>")
            self.session.record_action("fix", "No current file.")
            return

        suggestion = suggest_fix_for_content(path, content)
        if suggestion is None:
            self._emit_main(
                "No known deterministic fix pattern found for this file.",
                "Try manual inspection or experimental run-agent --llm.",
            )
            self.session.record_action("fix", f"No fix suggestion for {path}.")
            return

        old_text, new_text, reason = suggestion
        self._emit_main("Proposing fix...")
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
            self._emit(f"Proposed edit: {path}")
            self._emit(f"Status: {_tool_status(proposal.ok)} {proposal.summary}")
            self.session.record_action("fix", proposal.summary)
            return

        edit_path = str(proposal.output.get("path", path))
        risk_level = str(proposal.output.get("risk_level", "unknown") or "unknown")
        mini_diff = str(proposal.output.get("mini_diff", _mini_diff(old_text, new_text)))
        self._emit("")
        self._emit(f"Proposed edit: {edit_path}")
        self._emit(f"Risk: {risk_level}")
        self._emit("Status: reviewed, not applied")
        self._emit("")
        self._emit("Diff:")
        self._emit_diff_block(mini_diff)
        self._emit("")
        self._emit("Next: type `/apply` to apply, or `reject` to discard.")

        self.session.pending_edit = PendingEdit(
            path=str(proposal.output.get("path", path)),
            old_text=old_text,
            new_text=new_text,
            reason=reason,
            mini_diff=mini_diff,
            risk_level=str(proposal.output.get("risk_level", "")) or None,
            reviewer_summary=str(proposal.output.get("reviewer_summary", "")) or None,
        )
        self._emit_state()
        self.session.record_action("fix", f"Pending edit for {path}.")

    def _handle_apply(self) -> None:
        pending = self.session.pending_edit
        if pending is None:
            self._emit_main("No pending edit. Use `fix` first.")
            self.session.record_action("apply", "No pending edit.")
            return

        self._emit_main("Applying pending edit...")
        edit = partial_edit(
            pending.path,
            pending.old_text,
            pending.new_text,
            pending.reason,
            project_root=self.project_root,
            config=self.app_config,
        )
        if not edit.ok:
            self._emit_tool("PARTIAL_EDIT", edit.ok, edit.summary)
            self.session.record_action("apply", edit.summary)
            return

        self._emit_tool("PARTIAL_EDIT", edit.ok, f"Updated {pending.path}")
        self._emit("")
        self._emit("Applied:")
        self._emit(f"- Replaced `{pending.old_text}`")
        self._emit(f"- With `{pending.new_text}`")
        self._emit("")
        self._emit("Reason:")
        self._emit(pending.reason)

        if pending.path == self.session.current_file_path:
            refreshed = read_file(
                pending.path,
                project_root=self.project_root,
                config=self.app_config,
            )
            if refreshed.ok:
                self.session.current_file_content = str(refreshed.output.get("content", ""))

        self.session.pending_edit = None
        self._emit_state()
        self.session.record_action("apply", f"Applied edit to {pending.path}.")

    def _handle_reject(self) -> None:
        if self.session.pending_edit is None:
            self._emit_main("No pending edit to clear.")
            self.session.record_action("reject", "No pending edit.")
            return

        path = self.session.pending_edit.path
        self.session.pending_edit = None
        self._emit_main(f"Cleared pending edit for {path}. No files were changed.")
        self._emit_state()
        self.session.record_action("reject", f"Cleared pending edit for {path}.")

    def _handle_tokens(self) -> None:
        status = self.budget_monitor.status()
        max_tokens = self.app_config.token_budget.max_tokens
        pct = status.percentage_used * 100
        token_lines = [
            f"Used: {status.total_tokens_used} / {max_tokens} tokens ({pct:.1f}%)",
            f"Input/output: {status.input_tokens_used} / {status.output_tokens_used}",
            f"Estimated cost: ${status.estimated_cost_usd:.6f}",
            "Mode: deterministic local estimate",
        ]
        if status.warning_reached:
            token_lines.append("Warning: budget threshold reached.")
        if status.message:
            token_lines.append(f"Note: {status.message}")
        self._emit_tokens_block(*token_lines)
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
        label = "session history" if manual else f"session history ({trigger})"
        context_lines = [
            f"Compacted {label}.",
            "",
            "Preserved:",
            "- current file",
            "- pending edit state",
            "- last review",
            "- last test result",
            "- token usage",
            "",
            (
                f"History: kept {len(self.session.action_history)} actions "
                f"(was {before_count}, {before_chars} chars); "
                f"tokens used: {token_status.total_tokens_used}"
            ),
        ]
        self._emit_context_block(*context_lines)

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

    def _begin_turn(self, user_line: str) -> None:
        self._emit("")
        for line in _user_box_lines(user_line):
            self._emit(line)

    def _emit_main(self, *lines: str) -> None:
        for line in lines:
            self._emit(f"[MAIN] {line}")

    def _emit_tool(self, tool_name: str, ok: bool, message: str) -> None:
        self._emit(f"[TOOL: {tool_name}] {_tool_status(ok)} {message}")

    def _emit_safety(self, *lines: str) -> None:
        if not lines:
            return
        self._emit(f"[SAFETY] ! {lines[0]}")
        for line in lines[1:]:
            self._emit(line)

    def _emit_tokens_block(self, *lines: str) -> None:
        self._emit("[TOKENS]")
        for line in lines:
            self._emit(line)

    def _emit_context_block(self, *lines: str) -> None:
        self._emit("[CONTEXT]")
        for line in lines:
            self._emit(line)

    def _emit_agent_line(self, role: str, text: str) -> None:
        self._emit(f"[{role}] {text}")

    def _emit_numbered_preview(self, content: str, *, max_lines: int = 12) -> None:
        self._emit(_LINE_SEP)
        for line in _numbered_preview_lines(content, max_lines=max_lines):
            self._emit(line)
        self._emit(_LINE_SEP)

    def _emit_diff_block(self, mini_diff: str) -> None:
        self._emit(_LINE_SEP)
        for line in mini_diff.splitlines():
            indented = line
            if line.startswith("-") or line.startswith("+"):
                indented = f"    {line}"
            self._emit(indented)
        self._emit(_LINE_SEP)

    def _emit_state(self) -> None:
        self._emit("")
        self._emit(_format_state_line(self.session))

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


def _tool_status(ok: bool) -> str:
    return "✓" if ok else "✗"


def _format_state_line(session: InteractiveSession) -> str:
    if session.current_file_path:
        file_label = Path(session.current_file_path).name
    else:
        file_label = "(none)"
    pending = "yes" if session.pending_edit is not None else "no"
    if session.last_test_passed is None:
        tests = "not run"
    elif session.last_test_passed:
        tests = "passed"
    else:
        tests = "failed"
    return f"State: file={file_label} | pending_edit={pending} | tests={tests}"


def _user_box_lines(user_line: str) -> list[str]:
    header = "╭─ User "
    top = header + "─" * (_BOX_WIDTH - len(header))
    bottom = "╰" + "─" * (_BOX_WIDTH - 1)
    return [top, f"│ {user_line}", bottom]


def _numbered_preview_lines(content: str, *, max_lines: int = 12) -> list[str]:
    if not content:
        return ["(empty)"]
    lines = content.splitlines()
    preview = lines[:max_lines]
    width = len(str(len(lines) if lines else 1))
    numbered = [f"{index:>{width}}  {line}" for index, line in enumerate(preview, start=1)]
    if len(lines) > max_lines:
        numbered.append("...")
    return numbered


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
