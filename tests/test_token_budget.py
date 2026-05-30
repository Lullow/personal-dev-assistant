from __future__ import annotations

import pytest

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, TokenBudgetConfig
from personal_dev_assistant.models import TokenUsage


def test_initial_state():
    monitor = TokenBudgetMonitor(TokenBudgetConfig(max_tokens=1000, warning_threshold=0.8))

    status = monitor.status()

    assert status.total_tokens_used == 0
    assert status.input_tokens_used == 0
    assert status.output_tokens_used == 0
    assert status.remaining_tokens == 1000
    assert status.percentage_used == 0.0
    assert status.warning_reached is False
    assert status.hard_cap_reached is False
    assert status.estimated_cost_usd == 0.0
    assert status.can_continue is True
    assert status.message is None


def test_adding_usage_accumulates_tokens_and_cost():
    monitor = TokenBudgetMonitor(TokenBudgetConfig(max_tokens=1000, warning_threshold=0.8))

    status = monitor.add_usage(TokenUsage(input_tokens=100, output_tokens=50, estimated_cost_usd=0.01))

    assert status.total_tokens_used == 150
    assert status.input_tokens_used == 100
    assert status.output_tokens_used == 50
    assert status.estimated_cost_usd == pytest.approx(0.01)
    assert status.remaining_tokens == 850


def test_warning_threshold_is_reached():
    monitor = TokenBudgetMonitor(TokenBudgetConfig(max_tokens=100, warning_threshold=0.5))

    status = monitor.add_usage(TokenUsage(input_tokens=40, output_tokens=10))

    assert status.total_tokens_used == 50
    assert status.percentage_used == pytest.approx(0.5)
    assert status.warning_reached is True
    assert status.hard_cap_reached is False
    assert status.can_continue is True


def test_hard_cap_reached_blocks_further_steps():
    monitor = TokenBudgetMonitor(
        TokenBudgetConfig(max_tokens=100, warning_threshold=0.5, hard_cap_enabled=True)
    )

    status = monitor.add_usage(TokenUsage(input_tokens=70, output_tokens=40))

    assert status.total_tokens_used == 110
    assert status.hard_cap_reached is True
    assert status.can_continue is False
    assert status.remaining_tokens == 0
    assert status.message is not None
    assert "hard cap" in status.message.lower()


def test_hard_cap_disabled_allows_continuing_past_max():
    monitor = TokenBudgetMonitor(
        TokenBudgetConfig(max_tokens=100, warning_threshold=0.5, hard_cap_enabled=False)
    )

    status = monitor.add_usage(TokenUsage(input_tokens=70, output_tokens=40))

    assert status.total_tokens_used == 110
    assert status.hard_cap_reached is False
    assert status.can_continue is True
    assert status.message is None


def test_estimated_cost_accumulates_when_usage_has_no_cost():
    monitor = TokenBudgetMonitor(AppConfig(model="gpt-4o-mini"))

    first = monitor.add_usage(TokenUsage(input_tokens=1000, output_tokens=500))
    second = monitor.add_usage(TokenUsage(input_tokens=2000, output_tokens=1000))

    assert second.estimated_cost_usd > first.estimated_cost_usd
    assert second.estimated_cost_usd > 0.0


def test_token_usage_rejects_negative_values():
    with pytest.raises(ValueError, match="negative"):
        TokenUsage(input_tokens=-1)
