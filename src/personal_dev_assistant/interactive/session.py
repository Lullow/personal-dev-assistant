"""Session state for Interactive Assistant v.2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PendingEdit:
    """A validated proposed edit awaiting explicit user approval."""

    path: str
    old_text: str
    new_text: str
    reason: str
    mini_diff: str
    risk_level: str | None = None
    reviewer_summary: str | None = None


@dataclass(frozen=True)
class ActionRecord:
    """One compact session action for context tracking."""

    command: str
    summary: str


@dataclass
class InteractiveSession:
    """Stateful interactive chat session."""

    current_file_path: str | None = None
    current_file_content: str | None = None
    last_review_summary: str | None = None
    pending_edit: PendingEdit | None = None
    last_test_result: str | None = None
    last_test_passed: bool | None = None
    context_summary: str = ""
    action_history: list[ActionRecord] = field(default_factory=list)

    def record_action(self, command: str, summary: str) -> None:
        self.action_history.append(ActionRecord(command=command, summary=summary))

    @property
    def history_char_count(self) -> int:
        return sum(len(record.command) + len(record.summary) for record in self.action_history)

    def compact_preview(self, content: str | None, *, max_lines: int = 12) -> str:
        if not content:
            return "(empty)"
        lines = content.splitlines()
        preview_lines = lines[:max_lines]
        preview = "\n".join(preview_lines)
        if len(lines) > max_lines:
            preview = f"{preview}\n..."
        return preview

    def pending_edit_summary(self) -> str | None:
        if self.pending_edit is None:
            return None
        edit = self.pending_edit
        return f"pending edit for {edit.path}: {edit.old_text!r} -> {edit.new_text!r}"
