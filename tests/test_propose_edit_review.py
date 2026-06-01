from __future__ import annotations

from pathlib import Path

import pytest

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.tools.partial_edit import validate_partial_edit
from personal_dev_assistant.tools.propose_edit_review import (
    _is_trusted_source_path,
    review_proposed_edit,
)


@pytest.mark.parametrize(
    "path",
    [
        "demo_project/calculator.py",
        "tests/test_example.py",
        "test_example.py",
        "example_test.py",
        "pkg/example_test.py",
    ],
)
def test_trusted_source_path_detection(path: str):
    normalized = path.replace("\\", "/").lower()
    assert _is_trusted_source_path(normalized) is True


@pytest.mark.parametrize(
    "path",
    [
        "module.py",
        "src/app.py",
        "test_.py",
        "notest.py",
    ],
)
def test_non_trusted_source_paths(path: str):
    normalized = path.replace("\\", "/").lower()
    assert _is_trusted_source_path(normalized) is False


def _review_small_edit(tmp_path: Path, relative_path: str) -> str:
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("return a - b\n", encoding="utf-8")

    validation = validate_partial_edit(
        relative_path,
        "return a - b",
        "return a + b",
        project_root=tmp_path,
        config=AppConfig(),
    )
    review = review_proposed_edit(
        path=relative_path,
        old_text="return a - b",
        new_text="return a + b",
        reason="fix",
        validation=validation,
    )
    assert validation.ok is True
    return review.risk_level


@pytest.mark.parametrize(
    "relative_path",
    [
        "tests/test_example.py",
        "test_example.py",
        "example_test.py",
    ],
)
def test_trusted_test_files_get_low_risk_for_small_edit(tmp_path, relative_path: str):
    assert _review_small_edit(tmp_path, relative_path) == "low"


def test_non_trusted_module_gets_medium_risk_for_small_focused_edit(tmp_path):
    assert _review_small_edit(tmp_path, "module.py") == "medium"


def test_large_edit_still_high_risk_in_demo_project(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    old_block = "line\n" * 15
    new_block = "fixed\n" * 15
    target.write_text(old_block, encoding="utf-8")

    validation = validate_partial_edit(
        "demo_project/calculator.py",
        old_block,
        new_block,
        project_root=tmp_path,
        config=AppConfig(),
    )
    review = review_proposed_edit(
        path="demo_project/calculator.py",
        old_text=old_block,
        new_text=new_block,
        reason="",
        validation=validation,
    )

    assert validation.ok is True
    assert review.risk_level == "high"
