from __future__ import annotations

import importlib.util
import py_compile
import subprocess
import sys
from pathlib import Path

from personal_dev_assistant.config import AppConfig, SafetyConfig
from personal_dev_assistant.tools import partial_edit


def test_successful_single_replacement(tmp_path):
    file_path = tmp_path / "demo_project" / "calculator.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    result = partial_edit(
        "demo_project/calculator.py",
        "return a - b",
        "return a + b",
        reason="Fix addition bug.",
        project_root=tmp_path,
    )

    assert result.ok is True
    assert result.output["path"] == "demo_project/calculator.py"
    assert result.output["changed"] is True
    assert file_path.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_blocked_env_edit_is_rejected(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    result = partial_edit(
        ".env",
        "secret",
        "changed",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["changed"] is False
    assert "blocked" in result.summary.lower()


def test_blocked_git_venv_and_cache_edits_are_rejected(tmp_path):
    blocked_paths = [
        (".git/config", "[core]\n"),
        (".venv/bin/python", "#!/bin/sh\n"),
        ("src/__pycache__/module.pyc", "binary\n"),
        (".pytest_cache/v/cache/nodeids", "[]\n"),
    ]

    for relative_path, content in blocked_paths:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        result = partial_edit(
            relative_path,
            content.strip(),
            "changed",
            project_root=tmp_path,
        )

        assert result.ok is False
        assert result.output["changed"] is False
        assert "blocked" in result.summary.lower()


def test_outside_project_root_path_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")

    result = partial_edit(
        "../outside.txt",
        "outside",
        "changed",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["changed"] is False
    assert "outside" in result.output["reason"].lower() or "outside" in result.summary.lower()


def test_missing_old_text_is_rejected(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello world\n", encoding="utf-8")

    result = partial_edit(
        "notes.txt",
        "missing text",
        "replacement",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["reason"] == "old_text not found"


def test_duplicate_old_text_is_rejected(tmp_path):
    file_path = tmp_path / "repeat.txt"
    file_path.write_text("bug bug\n", encoding="utf-8")

    result = partial_edit(
        "repeat.txt",
        "bug",
        "fix",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["reason"] == "old_text not unique"
    assert file_path.read_text(encoding="utf-8") == "bug bug\n"


def test_no_op_edit_is_rejected(tmp_path):
    file_path = tmp_path / "same.txt"
    file_path.write_text("unchanged\n", encoding="utf-8")

    result = partial_edit(
        "same.txt",
        "unchanged",
        "unchanged",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["reason"] == "no-op edit"
    assert file_path.read_text(encoding="utf-8") == "unchanged\n"


def test_non_utf8_file_is_rejected(tmp_path):
    file_path = tmp_path / "binary.dat"
    file_path.write_bytes(b"\xff\xfe\x00\x01")

    result = partial_edit(
        "binary.dat",
        "anything",
        "replacement",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["reason"] == "non-utf8 file"


def test_empty_old_text_is_rejected(tmp_path):
    file_path = tmp_path / "empty_old.txt"
    file_path.write_text("content\n", encoding="utf-8")

    result = partial_edit(
        "empty_old.txt",
        "",
        "replacement",
        project_root=tmp_path,
    )

    assert result.ok is False
    assert result.output["reason"] == "empty old_text"


def test_file_edits_disabled_in_config(tmp_path):
    file_path = tmp_path / "locked.txt"
    file_path.write_text("old\n", encoding="utf-8")
    config = AppConfig(safety=SafetyConfig(allow_file_edits=False))

    result = partial_edit(
        "locked.txt",
        "old",
        "new",
        project_root=tmp_path,
        config=config,
    )

    assert result.ok is False
    assert result.output["reason"] == "file edits disabled"
    assert file_path.read_text(encoding="utf-8") == "old\n"


def test_partial_edit_invalidates_stale_bytecode_for_same_size_replacement(tmp_path):
    """Pytest must see updated source immediately after a same-length partial_edit."""

    demo_dir = tmp_path / "demo_project"
    demo_dir.mkdir(parents=True)
    calculator = demo_dir / "calculator.py"
    test_file = demo_dir / "test_calculator.py"
    calculator.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    test_file.write_text(
        "from calculator import add\n\n\n"
        "def test_add_returns_sum():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )

    python = sys.executable
    pytest_args = [python, "-m", "pytest", "demo_project/test_calculator.py", "-q"]

    before = subprocess.run(
        pytest_args,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert before.returncode != 0

    cache_path = importlib.util.cache_from_source(str(calculator.resolve()))
    assert cache_path
    if not Path(cache_path).exists():
        py_compile.compile(str(calculator), doraise=True)
    assert Path(cache_path).exists()

    result = partial_edit(
        "demo_project/calculator.py",
        "return a - b",
        "return a + b",
        reason="Fix addition bug.",
        project_root=tmp_path,
    )
    assert result.ok is True
    assert len(calculator.read_text(encoding="utf-8")) == len(
        "def add(a, b):\n    return a + b\n"
    )
    assert not Path(cache_path).exists()

    after = subprocess.run(
        pytest_args,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert after.returncode == 0, after.stdout + after.stderr
