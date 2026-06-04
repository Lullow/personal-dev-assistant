from __future__ import annotations

from personal_dev_assistant.demo.runner import BUGGY_RETURN, FIXED_RETURN
from personal_dev_assistant.interactive.bug_patterns import (
    CALCULATOR_ADD_SUBTRACT,
    CALCULATOR_PATH,
    STATS_UTILS_AVERAGE,
    STATS_UTILS_PATH,
    STRING_UTILS_NORMALIZE,
    STRING_UTILS_PATH,
    find_matching_bug_pattern,
)
from personal_dev_assistant.interactive.review import review_current_file, suggest_fix_for_content

BUGGY_CALCULATOR = "def add(a, b):\n    return a - b\n"
BUGGY_STRING_UTILS = "def normalize_name(name):\n    return name.lower()\n"
BUGGY_STATS_UTILS = "def average(numbers):\n    return sum(numbers) // len(numbers)\n"


def test_calculator_pattern_matches_buggy_content():
    pattern = find_matching_bug_pattern(CALCULATOR_PATH, BUGGY_CALCULATOR)
    assert pattern is CALCULATOR_ADD_SUBTRACT
    assert pattern.summary == "add() subtracts instead of adding."


def test_string_utils_pattern_matches_buggy_content():
    pattern = find_matching_bug_pattern(STRING_UTILS_PATH, BUGGY_STRING_UTILS)
    assert pattern is STRING_UTILS_NORMALIZE
    assert "lowercase" in pattern.summary.lower()


def test_stats_utils_pattern_matches_buggy_content():
    pattern = find_matching_bug_pattern(STATS_UTILS_PATH, BUGGY_STATS_UTILS)
    assert pattern is STATS_UTILS_AVERAGE
    assert "integer division" in pattern.summary.lower()


def test_unknown_file_has_no_pattern_match():
    content = "def helper():\n    return 42\n"
    assert find_matching_bug_pattern("demo_project/other.py", content) is None
    assert suggest_fix_for_content("demo_project/other.py", content) is None


def test_string_utils_pattern_requires_demo_challenges_path():
    assert find_matching_bug_pattern("demo_project/string_utils.py", BUGGY_STRING_UTILS) is None


def test_review_current_file_uses_pattern_for_string_utils():
    combined = review_current_file(path=STRING_UTILS_PATH, content=BUGGY_STRING_UTILS)
    assert combined.matched_pattern_name == "string_utils_normalize"
    assert "lowercase" in combined.code_reviewer.summary.lower()
    assert "title-cased" in combined.test_agent.finding.lower()


def test_suggest_fix_for_calculator_returns_expected_replacement():
    suggestion = suggest_fix_for_content(CALCULATOR_PATH, BUGGY_CALCULATOR)
    assert suggestion == (BUGGY_RETURN, FIXED_RETURN, CALCULATOR_ADD_SUBTRACT.reason)
