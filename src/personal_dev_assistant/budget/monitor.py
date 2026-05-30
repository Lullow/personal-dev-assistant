"""Token budget monitoring for agent sessions."""

from __future__ import annotations

from dataclasses import dataclass

from personal_dev_assistant.config import AppConfig, TokenBudgetConfig
from personal_dev_assistant.models import TokenUsage

# Basic per-model cost estimates (USD per 1M tokens) for demo budgeting.
_DEFAULT_COST_RATES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 0.50, "output": 1.50},
}


@dataclass(frozen=True)
class TokenBudgetStatus:
    """Current token budget state for one session."""

    total_tokens_used: int
    input_tokens_used: int
    output_tokens_used: int
    remaining_tokens: int
    percentage_used: float
    warning_reached: bool
    hard_cap_reached: bool
    estimated_cost_usd: float
    can_continue: bool
    message: str | None = None


class TokenBudgetMonitor:
    """Track approximate token usage, warnings, and hard-cap state."""

    def __init__(
        self,
        config: AppConfig | TokenBudgetConfig | None = None,
        *,
        model: str | None = None,
    ) -> None:
        if isinstance(config, AppConfig):
            self._budget = config.token_budget
            self._model = config.model
        elif isinstance(config, TokenBudgetConfig):
            self._budget = config
            self._model = model or "gpt-4o-mini"
        else:
            self._budget = TokenBudgetConfig()
            self._model = model or "gpt-4o-mini"

        self._input_tokens_used = 0
        self._output_tokens_used = 0
        self._estimated_cost_usd = 0.0

    def add_usage(self, usage: TokenUsage) -> TokenBudgetStatus:
        """Add token usage from one interaction and return updated status."""

        interaction_cost = usage.estimated_cost_usd
        if interaction_cost == 0.0:
            interaction_cost = estimate_cost_usd(
                usage.input_tokens,
                usage.output_tokens,
                model=self._model,
            )

        self._input_tokens_used += usage.input_tokens
        self._output_tokens_used += usage.output_tokens
        self._estimated_cost_usd += interaction_cost

        return self.status()

    def status(self) -> TokenBudgetStatus:
        """Return the current budget status."""

        total_used = self._input_tokens_used + self._output_tokens_used
        max_tokens = self._budget.max_tokens
        percentage_used = total_used / max_tokens if max_tokens > 0 else 0.0
        warning_reached = percentage_used >= self._budget.warning_threshold

        hard_cap_reached = False
        can_continue = True
        message = None

        if self._budget.hard_cap_enabled and total_used > max_tokens:
            hard_cap_reached = True
            can_continue = False
            message = (
                "Token budget hard cap reached. No more LLM or tool-agent steps should run."
            )

        remaining_tokens = max(0, max_tokens - total_used)

        return TokenBudgetStatus(
            total_tokens_used=total_used,
            input_tokens_used=self._input_tokens_used,
            output_tokens_used=self._output_tokens_used,
            remaining_tokens=remaining_tokens,
            percentage_used=percentage_used,
            warning_reached=warning_reached,
            hard_cap_reached=hard_cap_reached,
            estimated_cost_usd=self._estimated_cost_usd,
            can_continue=can_continue,
            message=message,
        )


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    model: str = "gpt-4o-mini",
) -> float:
    """Estimate interaction cost using simple hardcoded per-model rates."""

    rates = _DEFAULT_COST_RATES.get(model, _DEFAULT_COST_RATES["default"])
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost
