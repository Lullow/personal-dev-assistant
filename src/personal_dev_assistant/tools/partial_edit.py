"""Partial file edit tool."""

from __future__ import annotations

import importlib
import importlib.util
import os
from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.safety import SafetyDecision, check_path_safety
from personal_dev_assistant.tools.filesystem import _resolve_project_path


def validate_partial_edit(
    path: str,
    old_text: str,
    new_text: str,
    reason: str = "",
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
) -> ToolResult:
    """Validate a partial edit proposal without modifying files."""

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

    summary = f"Edit proposal for `{relative_path}` is valid."
    if reason.strip():
        summary = f"{summary} Reason: {reason.strip()}"

    return ToolResult(
        ok=True,
        summary=summary,
        output={
            "path": relative_path,
            "changed": False,
            "valid": True,
            "reason": reason.strip() or None,
        },
    )


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
    validation = validate_partial_edit(
        path,
        old_text,
        new_text,
        reason,
        project_root=project_root,
        config=app_config,
    )
    if not validation.ok:
        return validation

    relative_path = str(validation.output.get("path", path))
    root = Path(project_root).resolve()
    target = (root / relative_path).resolve()
    content = target.read_text(encoding="utf-8")
    updated_content = content.replace(old_text, new_text, 1)
    target.write_text(updated_content, encoding="utf-8")
    _invalidate_python_bytecode_after_write(target)

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


def _invalidate_python_bytecode_after_write(target: Path) -> None:
    """Remove stale bytecode so imports immediately see the updated source."""

    if target.suffix != ".py":
        return

    importlib.invalidate_caches()

    try:
        os.utime(target, None)
    except OSError:
        pass

    try:
        cache_path = importlib.util.cache_from_source(str(target.resolve()))
    except (TypeError, ValueError):
        return

    if not cache_path:
        return

    try:
        Path(cache_path).unlink(missing_ok=True)
    except OSError:
        pass


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
