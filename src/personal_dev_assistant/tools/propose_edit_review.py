"""Deterministic reviewer gate for proposed partial edits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.safety import SafetyDecision, check_path_safety

RiskLevel = Literal["low", "medium", "high"]

# Small focused edits (e.g. demo one-liner fix).
_FOCUSED_MAX_LINES = 3
_FOCUSED_MAX_CHARS = 120

# Edits above these thresholds are broader replacements.
_MEDIUM_MAX_LINES = 8
_MEDIUM_MAX_CHARS = 350
_HIGH_MIN_CHARS = 500
_HIGH_MIN_LINES = 12

_TRUSTED_PATH_PREFIXES = ("demo_project/", "tests/")


@dataclass(frozen=True)
class ProposedEditReview:
    """Reviewer outcome for a proposed edit."""

    risk_level: RiskLevel
    reviewer_summary: str
    recommendation: str
    valid: bool


def review_proposed_edit(
    *,
    path: str,
    old_text: str,
    new_text: str,
    reason: str,
    validation: ToolResult,
) -> ProposedEditReview:
    """Classify proposal risk and produce reviewer metadata."""

    safety = check_path_safety(path)
    rejection = str(validation.output.get("reason", "")).lower() if validation.output else ""

    if not validation.ok:
        risk = _risk_for_failed_validation(safety.decision, rejection)
        summary = _failed_summary(path, validation.summary, risk)
        recommendation = _recommendation_for_risk(risk, valid=False)
        return ProposedEditReview(
            risk_level=risk,
            reviewer_summary=summary,
            recommendation=recommendation,
            valid=False,
        )

    relative_path = str(validation.output.get("path", path))
    risk = _risk_for_valid_edit(relative_path, old_text, new_text, safety.decision)
    summary = _valid_summary(relative_path, old_text, new_text, reason, risk)
    recommendation = _recommendation_for_risk(risk, valid=True)
    return ProposedEditReview(
        risk_level=risk,
        reviewer_summary=summary,
        recommendation=recommendation,
        valid=True,
    )


def _risk_for_failed_validation(
    safety_decision: SafetyDecision,
    rejection: str,
) -> RiskLevel:
    if safety_decision is SafetyDecision.BLOCKED:
        return "high"
    if rejection in {
        "empty old_text",
        "no-op edit",
        "old_text not unique",
        "non-utf8 file",
        "path outside project root",
        "file edits disabled",
        "not a file",
    }:
        return "high"
    if rejection == "old_text not found":
        return "medium"
    return "high"


def _risk_for_valid_edit(
    relative_path: str,
    old_text: str,
    new_text: str,
    safety_decision: SafetyDecision,
) -> RiskLevel:
    if safety_decision is SafetyDecision.BLOCKED:
        return "high"

    normalized = relative_path.replace("\\", "/").lower()
    old_lines = len(old_text.splitlines()) or 1
    new_lines = len(new_text.splitlines()) or 1
    max_lines = max(old_lines, new_lines)
    max_span = max(len(old_text), len(new_text))
    combined = len(old_text) + len(new_text)

    if max_lines >= _HIGH_MIN_LINES or max_span >= _HIGH_MIN_CHARS or combined >= _HIGH_MIN_CHARS * 2:
        return "high"

    if max_lines > _MEDIUM_MAX_LINES or max_span > _MEDIUM_MAX_CHARS:
        return "medium"

    trusted = _is_trusted_source_path(normalized)
    focused = max_lines <= _FOCUSED_MAX_LINES and max_span <= _FOCUSED_MAX_CHARS

    if focused and trusted:
        return "low"

    if focused:
        return "medium"

    if trusted and max_lines <= _MEDIUM_MAX_LINES and max_span <= _MEDIUM_MAX_CHARS:
        return "medium"

    return "high"


def _is_trusted_source_path(normalized_path: str) -> bool:
    if any(normalized_path.startswith(prefix) for prefix in _TRUSTED_PATH_PREFIXES):
        return True

    name = PurePosixPath(normalized_path).name
    if name.endswith("_test.py"):
        return True
    if name.startswith("test_") and name.endswith(".py"):
        stem = name[: -len(".py")]
        if len(stem) > len("test_"):
            return True
    return False


def _failed_summary(path: str, validation_summary: str, risk: RiskLevel) -> str:
    return (
        f"Reviewer ({risk} risk): proposal for `{path}` failed validation. "
        f"{validation_summary}"
    )


def _valid_summary(
    relative_path: str,
    old_text: str,
    new_text: str,
    reason: str,
    risk: RiskLevel,
) -> str:
    old_lines = len(old_text.splitlines()) or 1
    new_lines = len(new_text.splitlines()) or 1
    parts = [
        f"Reviewer ({risk} risk): proposal for `{relative_path}` passed validation.",
        f"Replacement spans {old_lines} old line(s) and {new_lines} new line(s).",
    ]
    if reason.strip():
        parts.append(f"Reason: {reason.strip()}.")
    if risk == "low":
        parts.append("Small focused change in a demo or test path.")
    elif risk == "medium":
        parts.append("Moderate-sized or non-demo path edit — review before applying.")
    else:
        parts.append("Broad or high-impact edit — automatic apply is blocked.")
    return " ".join(parts)


def _recommendation_for_risk(risk: RiskLevel, *, valid: bool) -> str:
    if not valid:
        if risk == "high":
            return "Do not apply. Fix the proposal or choose a safer path and smaller replacement."
        return "Do not apply until validation issues are resolved."

    if risk == "low":
        return (
            "Safe to apply with --apply-proposed-edits when you accept this focused change."
        )
    if risk == "medium":
        return (
            "May apply with --apply-proposed-edits after manual review of the mini diff."
        )
    return (
        "Do not apply automatically. Narrow the edit or split into smaller proposals."
    )
