from __future__ import annotations

from personal_dev_assistant.config import AppConfig, ContextConfig
from personal_dev_assistant.tools import list_project_files, read_file


def test_read_file_reads_allowed_text_file(tmp_path):
    file_path = tmp_path / "demo_project" / "calculator.py"
    file_path.parent.mkdir()
    file_path.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = read_file("demo_project/calculator.py", project_root=tmp_path)

    assert result.ok is True
    assert result.output["path"] == "demo_project/calculator.py"
    assert "return a + b" in result.output["content"]
    assert result.truncated is False


def test_read_file_rejects_env_file(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    result = read_file(".env", project_root=tmp_path)

    assert result.ok is False
    assert "blocked" in result.summary.lower()


def test_read_file_allows_env_example(tmp_path):
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")

    result = read_file(".env.example", project_root=tmp_path)

    assert result.ok is True
    assert result.output["content"] == "OPENAI_API_KEY=\n"


def test_read_file_rejects_git_venv_and_cache_paths(tmp_path):
    blocked_paths = [
        ".git/config",
        ".venv/bin/python",
        "__pycache__/module.pyc",
        ".pytest_cache/v/cache/nodeids",
        ".mypy_cache/meta.json",
        ".ruff_cache/content",
        ".cache/tool",
    ]

    for blocked_path in blocked_paths:
        result = read_file(blocked_path, project_root=tmp_path)

        assert result.ok is False
        assert "blocked" in result.summary.lower()


def test_read_file_truncates_long_content(tmp_path):
    (tmp_path / "notes.txt").write_text("abcdef", encoding="utf-8")
    config = AppConfig(context=ContextConfig(max_observation_chars=3))

    result = read_file("notes.txt", project_root=tmp_path, config=config)

    assert result.ok is True
    assert result.output["content"] == "abc"
    assert result.truncated is True


def test_list_project_files_skips_blocked_directories(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "demo_project").mkdir()
    (tmp_path / "demo_project" / "calculator.py").write_text("pass\n", encoding="utf-8")

    blocked_files = [
        ".git/config",
        ".venv/bin/python",
        "__pycache__/module.pyc",
        ".pytest_cache/v/cache/nodeids",
        ".mypy_cache/meta.json",
        ".ruff_cache/content",
        ".cache/tool",
        "dist/package.whl",
        "build/output.txt",
    ]
    for blocked_file in blocked_files:
        path = tmp_path / blocked_file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("blocked\n", encoding="utf-8")

    result = list_project_files(project_root=tmp_path)

    assert result.ok is True
    assert "src/app.py" in result.output["files"]
    assert "demo_project/calculator.py" in result.output["files"]
    assert all(".git" not in file_path for file_path in result.output["files"])
    assert all(".venv" not in file_path for file_path in result.output["files"])
    assert all("__pycache__" not in file_path for file_path in result.output["files"])
    assert "dist" in result.output["skipped_directories"]
    assert "build" in result.output["skipped_directories"]


def test_list_project_files_returns_compact_truncated_list(tmp_path):
    for index in range(5):
        (tmp_path / f"file_{index}.txt").write_text("ok\n", encoding="utf-8")

    result = list_project_files(project_root=tmp_path, max_files=2)

    assert result.ok is True
    assert len(result.output["files"]) == 2
    assert result.truncated is True
