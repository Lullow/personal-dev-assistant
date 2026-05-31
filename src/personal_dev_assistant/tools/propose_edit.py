"""Validate and optionally apply proposed partial edits."""

from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.tools.partial_edit import partial_edit, validate_partial_edit

APPLY_HINT = (
    "Re-run with --apply-proposed-edits to apply this proposal safely via partial_edit."
)


def propose_edit(
    path: str,
    old_text: str,
    new_text: str,
    reason: str = "",
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
    apply: bool = False,
) -> ToolResult:
    """Validate a proposed edit and optionally apply it through partial_edit."""

    validation = validate_partial_edit(
        path,
        old_text,
        new_text,
        reason,
        project_root=project_root,
        config=config,
    )
    if not validation.ok:
        return validation

    relative_path = str(validation.output.get("path", path))
    mini_diff = _mini_diff(old_text, new_text)
    if not apply:
        summary = (
            f"Proposed edit for `{relative_path}` is valid but was not applied. "
            f"{APPLY_HINT}"
        )
        return ToolResult(
            ok=True,
            summary=summary,
            output={
                "path": relative_path,
                "applied": False,
                "valid": True,
                "changed": False,
                "mini_diff": mini_diff,
                "reason": reason.strip() or None,
                "apply_hint": APPLY_HINT,
            },
        )

    return partial_edit(
        path,
        old_text,
        new_text,
        reason,
        project_root=project_root,
        config=config,
    )


def _mini_diff(old_text: str, new_text: str) -> str:
    old_lines = old_text.splitlines() or [old_text]
    new_lines = new_text.splitlines() or [new_text]
    parts: list[str] = []
    for line in old_lines:
        parts.append(f"- {line}")
    for line in new_lines:
        parts.append(f"+ {line}")
    return "\n".join(parts)
