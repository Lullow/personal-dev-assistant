from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.tools.propose_edit import propose_edit


def test_propose_edit_valid_but_not_applied_by_default(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo.py",
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
    assert "not applied" in result.summary.lower()
    assert target.read_text(encoding="utf-8") == "return a - b\n"


def test_propose_edit_applied_only_when_apply_flag_enabled(tmp_path):
    target = tmp_path / "demo.py"
    target.write_text("return a - b\n", encoding="utf-8")

    result = propose_edit(
        "demo.py",
        "return a - b",
        "return a + b",
        "fix add",
        project_root=tmp_path,
        config=AppConfig(),
        apply=True,
    )

    assert result.ok is True
    assert result.output["changed"] is True
    assert target.read_text(encoding="utf-8") == "return a + b\n"


def test_propose_edit_blocked_path_is_rejected(tmp_path):
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
    assert "blocked" in result.summary.lower()


def test_propose_edit_missing_old_text_is_rejected(tmp_path):
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
    assert "old_text cannot be empty" in result.summary.lower()


def test_propose_edit_duplicate_old_text_is_rejected(tmp_path):
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
    assert "appears 2 times" in result.summary


def test_propose_edit_no_op_is_rejected(tmp_path):
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
    assert "identical" in result.summary.lower()
