"""Known deterministic bug patterns for interactive review and fix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

CALCULATOR_PATH = "demo_project/calculator.py"
STRING_UTILS_PATH = "demo_challenges/string_utils.py"
STATS_UTILS_PATH = "demo_challenges/stats_utils.py"


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _path_matches(path: str, expected: str) -> bool:
    return _normalize_path(path) == expected


@dataclass(frozen=True)
class BugPattern:
    """A reusable known bug pattern with review and fix metadata."""

    name: str
    summary: str
    test_hint: str
    old_text: str
    new_text: str
    reason: str
    risk_level: str
    next_step: str
    path_suffix: str | None = None
    match: Callable[[str, str], bool] | None = None

    def applies_to(self, path: str, content: str) -> bool:
        if self.path_suffix is not None and not _path_matches(path, self.path_suffix):
            return False
        if self.match is not None:
            return self.match(path, content)
        return self.old_text in content

    def is_fixed(self, path: str, content: str) -> bool:
        if self.path_suffix is not None and not _path_matches(path, self.path_suffix):
            return False
        return self.new_text in content and self.old_text not in content


CALCULATOR_ADD_SUBTRACT = BugPattern(
    name="calculator_add_subtract",
    summary="add() subtracts instead of adding.",
    test_hint="demo_project/test_calculator.py expects add(2, 3) == 5, but subtraction would return -1.",
    old_text="return a - b",
    new_text="return a + b",
    reason="Fix add() so it returns the sum instead of the difference.",
    risk_level="low",
    next_step="Use `fix it` to create a pending proposed edit, then `/apply` to change the file.",
    path_suffix=CALCULATOR_PATH,
    match=lambda _path, content: "return a - b" in content,
)

STRING_UTILS_NORMALIZE = BugPattern(
    name="string_utils_normalize",
    summary="normalize_name lowercases but does not strip spaces or title-case the name.",
    test_hint="demo_challenges/test_string_utils.py expects whitespace removed and title-cased name.",
    old_text="return name.lower()",
    new_text="return name.strip().title()",
    reason="Fix normalize_name so it strips surrounding spaces and returns title case.",
    risk_level="low",
    next_step="Use `fix it` to create a pending proposed edit, then `/apply` to change the file.",
    path_suffix=STRING_UTILS_PATH,
    match=lambda _path, content: "return name.lower()" in content,
)

STATS_UTILS_AVERAGE = BugPattern(
    name="stats_utils_average",
    summary="average uses integer division instead of true division.",
    test_hint="demo_challenges/test_stats_utils.py expects decimal result for [1, 2].",
    old_text="return sum(numbers) // len(numbers)",
    new_text="return sum(numbers) / len(numbers)",
    reason="Fix average so it returns decimal values when needed.",
    risk_level="low",
    next_step="Use `fix it` to create a pending proposed edit, then `/apply` to change the file.",
    path_suffix=STATS_UTILS_PATH,
    match=lambda _path, content: "return sum(numbers) // len(numbers)" in content,
)

KNOWN_BUG_PATTERNS: tuple[BugPattern, ...] = (
    CALCULATOR_ADD_SUBTRACT,
    STRING_UTILS_NORMALIZE,
    STATS_UTILS_AVERAGE,
)


def find_matching_bug_pattern(path: str, content: str) -> BugPattern | None:
    """Return the first known bug pattern that matches the current file content."""

    for pattern in KNOWN_BUG_PATTERNS:
        if pattern.applies_to(path, content):
            return pattern
    return None


def find_fixed_bug_pattern(path: str, content: str) -> BugPattern | None:
    """Return a known pattern that appears already fixed in the file."""

    for pattern in KNOWN_BUG_PATTERNS:
        if pattern.is_fixed(path, content):
            return pattern
    return None
