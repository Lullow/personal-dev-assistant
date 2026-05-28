"""Deterministic output compaction for active context."""

from __future__ import annotations

from dataclasses import dataclass

from personal_dev_assistant.config import AppConfig
from personal_dev_assistant.models import ToolResult


TRUNCATION_MARKER_TEMPLATE = "\n... [truncated {omitted_chars} characters] ...\n"


@dataclass(frozen=True)
class CompactOutput:
    """A compacted text observation and its size metadata."""

    text: str
    truncated: bool
    original_char_count: int
    compacted_char_count: int


def compact_output(
    raw_text: str,
    *,
    config: AppConfig | None = None,
    max_chars: int | None = None,
) -> CompactOutput:
    """Compact raw text to fit active context while preserving start and end."""

    limit = max_chars if max_chars is not None else (config or AppConfig()).context.max_observation_chars
    if limit <= 0:
        raise ValueError("max_chars must be positive.")

    original_char_count = len(raw_text)
    if original_char_count <= limit:
        return CompactOutput(
            text=raw_text,
            truncated=False,
            original_char_count=original_char_count,
            compacted_char_count=original_char_count,
        )

    compacted = _compact_with_marker(raw_text, limit)
    return CompactOutput(
        text=compacted,
        truncated=True,
        original_char_count=original_char_count,
        compacted_char_count=len(compacted),
    )


def compact_tool_observation(
    tool_name: str,
    raw_output: str,
    *,
    config: AppConfig | None = None,
    output_key: str = "content",
    ok: bool = True,
) -> ToolResult:
    """Convert raw tool text into a compact ToolResult-style observation."""

    compacted = compact_output(raw_output, config=config)
    summary = (
        f"{tool_name} output compacted from {compacted.original_char_count} "
        f"to {compacted.compacted_char_count} characters."
        if compacted.truncated
        else f"{tool_name} output kept without compaction."
    )

    return ToolResult(
        ok=ok,
        summary=summary,
        output={
            output_key: compacted.text,
            "original_char_count": compacted.original_char_count,
            "compacted_char_count": compacted.compacted_char_count,
        },
        truncated=compacted.truncated,
    )


def _compact_with_marker(raw_text: str, limit: int) -> str:
    marker = TRUNCATION_MARKER_TEMPLATE.format(omitted_chars=_initial_omitted_count(raw_text, limit))
    if len(marker) >= limit:
        return marker[:limit]

    available_text_chars = limit - len(marker)
    head_chars = (available_text_chars + 1) // 2
    tail_chars = available_text_chars // 2
    omitted_chars = len(raw_text) - head_chars - tail_chars
    marker = TRUNCATION_MARKER_TEMPLATE.format(omitted_chars=omitted_chars)

    while len(marker) + head_chars + tail_chars > limit:
        if head_chars >= tail_chars and head_chars > 0:
            head_chars -= 1
        elif tail_chars > 0:
            tail_chars -= 1
        else:
            return marker[:limit]
        omitted_chars = len(raw_text) - head_chars - tail_chars
        marker = TRUNCATION_MARKER_TEMPLATE.format(omitted_chars=omitted_chars)

    tail_text = raw_text[-tail_chars:] if tail_chars else ""
    return raw_text[:head_chars] + marker + tail_text


def _initial_omitted_count(raw_text: str, limit: int) -> int:
    return max(len(raw_text) - limit, 0)
