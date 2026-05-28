"""Read-only filesystem tools."""

from __future__ import annotations

from pathlib import Path

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult
from personal_dev_assistant.safety import SafetyDecision, check_path_safety


def read_file(
    path: str,
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
) -> ToolResult:
    """Read an allowed text file and return a bounded observation."""

    app_config = config or AppConfig()
    safety_result = check_path_safety(path)
    if safety_result.decision is SafetyDecision.BLOCKED:
        return ToolResult(
            ok=False,
            summary=f"Read blocked: {safety_result.reason}",
            output={"path": path, "reason": safety_result.reason},
        )

    root = Path(project_root).resolve()
    target_result = _resolve_project_path(root, path)
    if target_result is None:
        return ToolResult(
            ok=False,
            summary="Read blocked: path is outside the project root.",
            output={"path": path},
        )

    target, relative_path = target_result
    if not target.exists():
        return ToolResult(
            ok=False,
            summary=f"File not found: {relative_path}",
            output={"path": relative_path},
        )
    if not target.is_file():
        return ToolResult(
            ok=False,
            summary=f"Path is not a file: {relative_path}",
            output={"path": relative_path},
        )

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ToolResult(
            ok=False,
            summary=f"Read blocked: file is not valid UTF-8 text: {relative_path}",
            output={"path": relative_path},
        )

    max_chars = app_config.context.max_observation_chars
    truncated = len(content) > max_chars
    visible_content = content[:max_chars] if truncated else content
    summary = (
        f"Read text file `{relative_path}` and truncated output to {max_chars} characters."
        if truncated
        else f"Read text file `{relative_path}`."
    )

    return ToolResult(
        ok=True,
        summary=summary,
        output={"path": relative_path, "content": visible_content},
        truncated=truncated,
    )


def list_project_files(
    *,
    project_root: str | Path = ".",
    config: AppConfig | None = None,
    max_files: int = 200,
) -> ToolResult:
    """Return a compact list of allowed project files without reading contents."""

    app_config = config or AppConfig()
    root = Path(project_root).resolve()
    files: list[str] = []
    skipped_directories: list[str] = []

    for current_root, dirnames, filenames in root.walk():
        current_path = Path(current_root)
        current_relative = _relative_posix(root, current_path)
        if current_relative and check_path_safety(current_relative).decision is SafetyDecision.BLOCKED:
            dirnames[:] = []
            skipped_directories.append(current_relative)
            continue

        allowed_dirnames: list[str] = []
        for dirname in sorted(dirnames):
            child_relative = _relative_posix(root, current_path / dirname)
            if check_path_safety(child_relative).decision is SafetyDecision.BLOCKED:
                skipped_directories.append(child_relative)
                continue
            allowed_dirnames.append(dirname)
        dirnames[:] = allowed_dirnames

        for filename in sorted(filenames):
            file_relative = _relative_posix(root, current_path / filename)
            if check_path_safety(file_relative).decision is SafetyDecision.BLOCKED:
                continue
            files.append(file_relative)
            if len(files) >= max_files:
                return _listing_result(files, skipped_directories, app_config, truncated=True)

    return _listing_result(files, skipped_directories, app_config, truncated=False)


def _listing_result(
    files: list[str],
    skipped_directories: list[str],
    config: AppConfig,
    *,
    truncated: bool,
) -> ToolResult:
    max_chars = config.context.max_observation_chars
    compact_files = _compact_to_char_limit(files, max_chars)
    char_truncated = len(compact_files) < len(files)
    was_truncated = truncated or char_truncated
    summary = (
        f"Listed {len(compact_files)} project files; output was truncated."
        if was_truncated
        else f"Listed {len(compact_files)} project files."
    )

    return ToolResult(
        ok=True,
        summary=summary,
        output={
            "files": compact_files,
            "skipped_directories": sorted(set(skipped_directories)),
        },
        truncated=was_truncated,
    )


def _resolve_project_path(root: Path, path: str) -> tuple[Path, str] | None:
    target = (root / path).resolve()
    try:
        relative_path = target.relative_to(root).as_posix()
    except ValueError:
        return None

    if check_path_safety(relative_path).decision is SafetyDecision.BLOCKED:
        return None

    return target, relative_path


def _relative_posix(root: Path, path: Path) -> str:
    if path == root:
        return ""
    return path.relative_to(root).as_posix()


def _compact_to_char_limit(files: list[str], max_chars: int) -> list[str]:
    compact: list[str] = []
    used_chars = 0

    for file_path in files:
        next_used_chars = used_chars + len(file_path) + 1
        if compact and next_used_chars > max_chars:
            break
        compact.append(file_path)
        used_chars = next_used_chars

    return compact
