"""Validate and optionally apply proposed partial edits."""

from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.tools.partial_edit import partial_edit, validate_partial_edit
from personal_dev_assistant.tools.propose_edit_review import review_proposed_edit

APPLY_HINT = (
    "Re-run with --apply-proposed-edits to apply low/medium-risk proposals via partial_edit."
)

_HIGH_RISK_APPLY_BLOCKED = (
    "Apply blocked: reviewer classified this proposal as high risk. "
    "Narrow the edit or use a safer path even with --apply-proposed-edits."
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
    """Validate a proposed edit, run reviewer gate, and optionally apply via partial_edit."""

    validation = validate_partial_edit(
        path,
        old_text,
        new_text,
        reason,
        project_root=project_root,
        config=config,
    )
    review = review_proposed_edit(
        path=path,
        old_text=old_text,
        new_text=new_text,
        reason=reason,
        validation=validation,
    )
    mini_diff = _mini_diff(old_text, new_text)
    relative_path = str(validation.output.get("path", path)) if validation.output else path

    base_output = {
        "path": relative_path,
        "valid": review.valid,
        "risk_level": review.risk_level,
        "reviewer_summary": review.reviewer_summary,
        "recommendation": review.recommendation,
        "mini_diff": mini_diff,
        "applied": False,
        "changed": False,
        "reason": reason.strip() or None,
    }

    if not validation.ok:
        summary = (
            f"{review.reviewer_summary} Recommendation: {review.recommendation}"
        )
        return ToolResult(
            ok=False,
            summary=summary,
            output={**base_output, "apply_hint": None},
        )

    if not apply:
        summary = (
            f"{review.reviewer_summary} Reviewed and not applied. {APPLY_HINT}"
        )
        return ToolResult(
            ok=True,
            summary=summary,
            output={**base_output, "apply_hint": APPLY_HINT},
        )

    if review.risk_level == "high":
        summary = f"{review.reviewer_summary} {_HIGH_RISK_APPLY_BLOCKED}"
        return ToolResult(
            ok=False,
            summary=summary,
            output={**base_output, "apply_hint": None},
        )

    edit_result = partial_edit(
        path,
        old_text,
        new_text,
        reason,
        project_root=project_root,
        config=config,
    )
    if not edit_result.ok:
        return ToolResult(
            ok=False,
            summary=f"{review.reviewer_summary} {edit_result.summary}",
            output={
                **base_output,
                **edit_result.output,
            },
        )

    applied_path = str(edit_result.output.get("path", relative_path))
    summary = (
        f"{review.reviewer_summary} Applied via partial_edit. {edit_result.summary}"
    )
    return ToolResult(
        ok=True,
        summary=summary,
        output={
            **base_output,
            "path": applied_path,
            "applied": True,
            "changed": True,
            "apply_hint": None,
        },
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
