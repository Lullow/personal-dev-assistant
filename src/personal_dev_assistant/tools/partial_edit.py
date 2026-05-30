"""Partial file edit tool."""

from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.safety import SafetyDecision, check_path_safety
from personal_dev_assistant.tools.filesystem import _resolve_project_path


def partial_edit(
    path: str,
    old_text: str,
    new_text: str,
    reason: str = "",
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
) -> ToolResult:
    """Apply a small, exact-match text replacement in an allowed project file."""

    app_config = config or AppConfig()

    if not app_config.safety.allow_file_edits:
        return _rejected(
            path=path,
            summary="Edit blocked: file edits are disabled in configuration.",
            reason="file edits disabled",
        )

    if not old_text:
        return _rejected(
            path=path,
            summary="Edit blocked: old_text cannot be empty.",
            reason="empty old_text",
        )

    if old_text == new_text:
        return _rejected(
            path=path,
            summary="Edit blocked: old_text and new_text are identical.",
            reason="no-op edit",
        )

    safety_result = check_path_safety(path)
    if safety_result.decision is SafetyDecision.BLOCKED:
        return _rejected(
            path=path,
            summary=f"Edit blocked: {safety_result.reason}",
            reason=safety_result.reason,
        )

    root = Path(project_root).resolve()
    target_result = _resolve_project_path(root, path)
    if target_result is None:
        return _rejected(
            path=path,
            summary="Edit blocked: path is outside the project root or not allowed.",
            reason="path outside project root",
        )

    target, relative_path = target_result
    if not target.exists():
        return _rejected(
            path=relative_path,
            summary=f"Edit blocked: file not found: {relative_path}",
            reason="file not found",
        )
    if not target.is_file():
        return _rejected(
            path=relative_path,
            summary=f"Edit blocked: path is not a file: {relative_path}",
            reason="not a file",
        )

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return _rejected(
            path=relative_path,
            summary=f"Edit blocked: file is not valid UTF-8 text: {relative_path}",
            reason="non-utf8 file",
        )

    occurrences = content.count(old_text)
    if occurrences == 0:
        return _rejected(
            path=relative_path,
            summary=f"Edit blocked: old_text not found in `{relative_path}`.",
            reason="old_text not found",
        )
    if occurrences > 1:
        return _rejected(
            path=relative_path,
            summary=(
                f"Edit blocked: old_text appears {occurrences} times in `{relative_path}`."
            ),
            reason="old_text not unique",
        )

    updated_content = content.replace(old_text, new_text, 1)
    target.write_text(updated_content, encoding="utf-8")

    summary = f"Updated `{relative_path}` with a single focused replacement."
    if reason.strip():
        summary = f"{summary} Reason: {reason.strip()}"

    return ToolResult(
        ok=True,
        summary=summary,
        output={
            "path": relative_path,
            "changed": True,
            "reason": reason.strip() or None,
        },
    )


def _rejected(*, path: str, summary: str, reason: str) -> ToolResult:
    return ToolResult(
        ok=False,
        summary=summary,
        output={
            "path": path,
            "changed": False,
            "reason": reason,
        },
    )
