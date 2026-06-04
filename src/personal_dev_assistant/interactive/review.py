"""Deterministic review subagents for interactive chat mode."""

from __future__ import annotations

from dataclasses import dataclass

from personal_dev_assistant.interactive.bug_patterns import (
    find_fixed_bug_pattern,
    find_matching_bug_pattern,
)


@dataclass(frozen=True)
class SubAgentReview:
    """Output from one deterministic review subagent."""

    role: str
    summary: str
    finding: str
    recommendation: str


@dataclass(frozen=True)
class CombinedReview:
    """Combined review from code, test, and fix-planning subagents."""

    target_path: str
    code_reviewer: SubAgentReview
    test_agent: SubAgentReview
    fix_planner: SubAgentReview
    matched_pattern_name: str | None = None

    @property
    def summary(self) -> str:
        lines = [
            f"Review of {self.target_path}",
            f"[CODE REVIEWER] {self.code_reviewer.summary}",
            f"   Finding: {self.code_reviewer.finding}",
            f"[TEST AGENT] {self.test_agent.summary}",
            f"   Finding: {self.test_agent.finding}",
            f"[FIX PLANNER] {self.fix_planner.summary}",
            f"   Recommendation: {self.fix_planner.recommendation}",
        ]
        return "\n".join(lines)


def run_code_reviewer(*, path: str, content: str) -> SubAgentReview:
    pattern = find_matching_bug_pattern(path, content)
    if pattern is not None:
        return SubAgentReview(
            role="code_reviewer",
            summary=pattern.summary,
            finding=(
                f"The code contains `{pattern.old_text}` but should use `{pattern.new_text}`."
            ),
            recommendation=f"Change `{pattern.old_text}` to `{pattern.new_text}`.",
        )

    fixed = find_fixed_bug_pattern(path, content)
    if fixed is not None:
        return SubAgentReview(
            role="code_reviewer",
            summary=f"{fixed.name} appears fixed.",
            finding="The file already contains the expected fix for the known bug pattern.",
            recommendation="No code change needed for the known bug pattern.",
        )

    return SubAgentReview(
        role="code_reviewer",
        summary="Implementation needs manual inspection.",
        finding="Could not match a known deterministic bug pattern in this file.",
        recommendation="Inspect the implementation and compare it with the test expectations.",
    )


def run_test_reasoning_agent(*, path: str, content: str) -> SubAgentReview:
    pattern = find_matching_bug_pattern(path, content)
    if pattern is not None:
        return SubAgentReview(
            role="test_agent",
            summary="Tests likely fail for the known bug pattern.",
            finding=pattern.test_hint,
            recommendation="Run pytest on demo_project to confirm the failure.",
        )

    fixed = find_fixed_bug_pattern(path, content)
    if fixed is not None:
        return SubAgentReview(
            role="test_agent",
            summary="Tests should pass for the known demo case.",
            finding=fixed.test_hint.replace("expects", "should satisfy"),
            recommendation="Run pytest on demo_project to verify.",
        )

    return SubAgentReview(
        role="test_agent",
        summary="Test impact is unclear without a known bug pattern.",
        finding="Could not infer test expectations from the current file alone.",
        recommendation="Read the related test file and run pytest.",
    )


def run_fix_planner(*, path: str, content: str) -> SubAgentReview:
    pattern = find_matching_bug_pattern(path, content)
    if pattern is not None:
        return SubAgentReview(
            role="fix_planner",
            summary="One-line fix available for the known bug.",
            finding=f"Exact replacement: `{pattern.old_text}` -> `{pattern.new_text}`.",
            recommendation=pattern.next_step,
        )

    fixed = find_fixed_bug_pattern(path, content)
    if fixed is not None:
        return SubAgentReview(
            role="fix_planner",
            summary="No fix needed for the known bug pattern.",
            finding="The file already contains the expected fixed implementation.",
            recommendation="Run tests to confirm behavior.",
        )

    return SubAgentReview(
        role="fix_planner",
        summary="No automatic fix planned.",
        finding="Could not derive OLD_TEXT/NEW_TEXT for a safe exact-match edit.",
        recommendation="Review the file manually before proposing an edit.",
    )


def review_current_file(*, path: str, content: str) -> CombinedReview:
    """Run deterministic review subagents and combine their results."""

    pattern = find_matching_bug_pattern(path, content)
    return CombinedReview(
        target_path=path,
        code_reviewer=run_code_reviewer(path=path, content=content),
        test_agent=run_test_reasoning_agent(path=path, content=content),
        fix_planner=run_fix_planner(path=path, content=content),
        matched_pattern_name=pattern.name if pattern is not None else None,
    )


def suggest_fix_for_content(path: str, content: str) -> tuple[str, str, str] | None:
    """Return (old_text, new_text, reason) when a known bug pattern is present."""

    pattern = find_matching_bug_pattern(path, content)
    if pattern is None:
        return None
    return (pattern.old_text, pattern.new_text, pattern.reason)
