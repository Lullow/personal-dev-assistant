"""Deterministic review subagents for interactive chat mode."""

from __future__ import annotations

from dataclasses import dataclass

from personal_dev_assistant.demo.runner import BUGGY_RETURN, FIXED_RETURN, TEST_PATH


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
    if BUGGY_RETURN in content:
        return SubAgentReview(
            role="code_reviewer",
            summary="add() subtracts instead of adding.",
            finding=(
                "The add function uses `return a - b` but should return the sum of its arguments."
            ),
            recommendation=f"Change `{BUGGY_RETURN}` to `{FIXED_RETURN}`.",
        )
    if FIXED_RETURN in content:
        return SubAgentReview(
            role="code_reviewer",
            summary="add() appears to return the sum correctly.",
            finding="The add function uses addition as expected.",
            recommendation="No code change needed for the known demo bug pattern.",
        )
    return SubAgentReview(
        role="code_reviewer",
        summary="Implementation needs manual inspection.",
        finding="Could not match the known demo bug or fix pattern in this file.",
        recommendation="Inspect add() and compare it with the test expectations.",
    )


def run_test_reasoning_agent(*, path: str, content: str) -> SubAgentReview:
    if BUGGY_RETURN in content:
        return SubAgentReview(
            role="test_agent",
            summary="Tests likely fail on addition.",
            finding=(
                f"{TEST_PATH} expects add(2, 3) == 5, but subtraction would return -1."
            ),
            recommendation="Run pytest on demo_project to confirm the failure.",
        )
    if FIXED_RETURN in content:
        return SubAgentReview(
            role="test_agent",
            summary="Tests should pass for the known demo case.",
            finding="add(2, 3) should equal 5 with the current implementation.",
            recommendation="Run pytest on demo_project to verify.",
        )
    return SubAgentReview(
        role="test_agent",
        summary="Test impact is unclear without the demo bug pattern.",
        finding="Could not infer test expectations from the current file alone.",
        recommendation="Read the related test file and run pytest.",
    )


def run_fix_planner(*, path: str, content: str) -> SubAgentReview:
    if BUGGY_RETURN in content:
        return SubAgentReview(
            role="fix_planner",
            summary="One-line fix available for the demo bug.",
            finding=f"Exact replacement: `{BUGGY_RETURN}` -> `{FIXED_RETURN}`.",
            recommendation=(
                "Use `fix it` to create a pending proposed edit, then `apply` to change the file."
            ),
        )
    if FIXED_RETURN in content:
        return SubAgentReview(
            role="fix_planner",
            summary="No fix needed for the known demo bug.",
            finding="The file already contains the expected fixed return statement.",
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

    return CombinedReview(
        target_path=path,
        code_reviewer=run_code_reviewer(path=path, content=content),
        test_agent=run_test_reasoning_agent(path=path, content=content),
        fix_planner=run_fix_planner(path=path, content=content),
    )


def suggest_fix_for_content(content: str) -> tuple[str, str, str] | None:
    """Return (old_text, new_text, reason) when the demo bug pattern is present."""

    if BUGGY_RETURN not in content:
        return None
    return (
        BUGGY_RETURN,
        FIXED_RETURN,
        "Fix add() so it returns the sum instead of the difference.",
    )
