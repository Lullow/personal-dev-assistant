"""Shared structured data objects used by agents and tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    """A request from an agent to run a named tool."""

    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """A normalized result returned by a tool."""

    ok: bool
    summary: str
    output: dict[str, Any] = field(default_factory=dict)
    exit_code: int | None = None
    truncated: bool = False
    raw_output_ref: str | None = None


@dataclass(frozen=True)
class AgentResult:
    """A compact, structured result from an agent or sub-agent."""

    role: str
    summary: str
    findings: list[str] = field(default_factory=list)
    risk_level: str = "low"
    recommended_next_step: str | None = None


@dataclass(frozen=True)
class TokenUsage:
    """Approximate token usage for one interaction or accumulated session."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int | None = None
    estimated_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("Token counts cannot be negative.")
        if self.total_tokens is not None and self.total_tokens < 0:
            raise ValueError("Total tokens cannot be negative.")
        if self.estimated_cost_usd < 0:
            raise ValueError("Estimated cost cannot be negative.")

    @property
    def effective_total_tokens(self) -> int:
        """Return the explicit total, or derive it from input and output tokens."""

        if self.total_tokens is not None:
            return self.total_tokens
        return self.input_tokens + self.output_tokens
