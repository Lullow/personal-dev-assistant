from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.tools.propose_edit import propose_edit
from personal_dev_assistant.tools.propose_edit_review import review_proposed_edit
from personal_dev_assistant.tools.partial_edit import validate_partial_edit


def test_propose_edit_valid_small_edit_low_risk_not_applied_by_default(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo_project/calculator.py",
        "return a - b",
        "return a + b",
        "fix add",
        project_root=tmp_path,
        config=AppConfig(),
        apply=False,
    )

    assert result.ok is True
    assert result.output["applied"] is False
    assert result.output["valid"] is True
    assert result.output["risk_level"] == "low"
    assert "reviewer_summary" in result.output
    assert "recommendation" in result.output
    assert "mini_diff" in result.output
    assert "not applied" in result.summary.lower()
    assert target.read_text(encoding="utf-8") == "return a - b\n"


def test_propose_edit_valid_small_edit_applies_when_apply_true(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo_project/calculator.py",
        "return a - b",
        "return a + b",
        "fix add",
        project_root=tmp_path,
        config=AppConfig(),
        apply=True,
    )

    assert result.ok is True
    assert result.output["applied"] is True
    assert result.output["changed"] is True
    assert result.output["risk_level"] == "low"
    assert target.read_text(encoding="utf-8") == "return a + b\n"


def test_propose_edit_blocked_path_high_risk_rejected(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=1\n", encoding="utf-8")

    result = propose_edit(
        ".env",
        "SECRET=1",
        "SECRET=0",
        project_root=tmp_path,
        config=AppConfig(),
    )

    assert result.ok is False
    assert result.output["risk_level"] == "high"
    assert result.output["valid"] is False
    assert "reviewer_summary" in result.output
    assert "recommendation" in result.output
    assert "blocked" in result.summary.lower() or "blocked" in result.output["reviewer_summary"].lower()


def test_propose_edit_missing_old_text_high_risk_rejected(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo.py",
        "",
        "return a + b",
        project_root=tmp_path,
        config=AppConfig(),
    )

    assert result.ok is False
    assert result.output["risk_level"] == "high"
    assert "old_text cannot be empty" in result.summary.lower()


def test_propose_edit_duplicate_old_text_rejected(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("bug\nbug\n", encoding="utf-8")

    result = propose_edit(
        "demo.py",
        "bug",
        "fixed",
        project_root=tmp_path,
        config=AppConfig(),
    )

    assert result.ok is False
    assert result.output["risk_level"] == "high"
    assert "appears 2 times" in result.summary


def test_propose_edit_no_op_rejected(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("same\n", encoding="utf-8")

    result = propose_edit(
        "demo.py",
        "same",
        "same",
        project_root=tmp_path,
        config=AppConfig(),
    )

    assert result.ok is False
    assert result.output["risk_level"] == "high"
    assert "identical" in result.summary.lower()


def test_propose_edit_large_replacement_medium_or_high_risk(tmp_path):
    target = tmp_path / "module.py"
    old_block = "x" * 400 + "\n" + "y" * 50
    new_block = "a" * 400 + "\n" + "b" * 50
    target.write_text(old_block + "\n", encoding="utf-8")

    validation = validate_partial_edit(
        "module.py",
        old_block,
        new_block,
        project_root=tmp_path,
        config=AppConfig(),
    )
    review = review_proposed_edit(
        path="module.py",
        old_text=old_block,
        new_text=new_block,
        reason="",
        validation=validation,
    )

    assert validation.ok is True
    assert review.risk_level in {"medium", "high"}

    result = propose_edit(
        "module.py",
        old_block,
        new_block,
        project_root=tmp_path,
        config=AppConfig(),
        apply=False,
    )
    assert result.output["risk_level"] in {"medium", "high"}


def test_propose_edit_high_risk_not_applied_even_with_apply_true(tmp_path):
    target = tmp_path / "large.py"
    old_block = "line\n" * 15
    new_block = "fixed\n" * 15
    target.write_text(old_block, encoding="utf-8")

    result = propose_edit(
        "large.py",
        old_block,
        new_block,
        project_root=tmp_path,
        config=AppConfig(),
        apply=True,
    )

    assert result.ok is False
    assert result.output["risk_level"] == "high"
    assert result.output["applied"] is False
    assert "high risk" in result.summary.lower()
    assert target.read_text(encoding="utf-8") == old_block


def test_propose_edit_output_includes_reviewer_metadata(tmp_path):
    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir()
    target = demo_dir / "calculator.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo_project/calculator.py",
        "return a - b",
        "return a + b",
        project_root=tmp_path,
        config=AppConfig(),
    )

    assert "Reviewer" in result.output["reviewer_summary"]
    assert result.output["recommendation"]
    assert "- return a - b" in result.output["mini_diff"]
    assert "+ return a + b" in result.output["mini_diff"]
