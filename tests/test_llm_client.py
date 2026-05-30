from __future__ import annotations

import pytest

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import (
    AppConfig,
    EnvironmentConfig,
    RuntimeConfig,
    TokenBudgetConfig,
)
from personal_dev_assistant.llm import (
    BudgetExceededError,
    MissingApiKeyError,
    MockChatClient,
    OpenAIChatClient,
    create_chat_client,
)
from personal_dev_assistant.models import TokenUsage


def test_mock_response_returns_text():
    monitor = TokenBudgetMonitor()
    client = MockChatClient(
        model="gpt-4o-mini",
        budget_monitor=monitor,
        response_text="Hello from mock.",
    )

    response = client.complete([{"role": "user", "content": "Hi"}])

    assert response.text == "Hello from mock."
    assert response.mock is True
    assert response.model == "gpt-4o-mini"


def test_mock_response_returns_token_usage():
    monitor = TokenBudgetMonitor()
    client = MockChatClient(model="gpt-4o-mini", budget_monitor=monitor)

    response = client.complete([{"role": "user", "content": "Explain this code."}])

    assert response.usage.input_tokens > 0
    assert response.usage.output_tokens > 0
    assert response.usage.effective_total_tokens == (
        response.usage.input_tokens + response.usage.output_tokens
    )


def test_budget_monitor_is_updated_after_mock_call():
    monitor = TokenBudgetMonitor(TokenBudgetConfig(max_tokens=10_000))
    client = MockChatClient(model="gpt-4o-mini", budget_monitor=monitor)

    client.complete([{"role": "user", "content": "Task"}])

    status = monitor.status()
    assert status.total_tokens_used > 0
    assert status.estimated_cost_usd > 0.0


def test_hard_cap_prevents_call():
    monitor = TokenBudgetMonitor(
        TokenBudgetConfig(max_tokens=10, warning_threshold=0.5, hard_cap_enabled=True)
    )
    monitor.add_usage(TokenUsage(input_tokens=8, output_tokens=5))
    client = MockChatClient(model="gpt-4o-mini", budget_monitor=monitor)

    with pytest.raises(BudgetExceededError, match="hard cap"):
        client.complete([{"role": "user", "content": "Another step"}])


def test_missing_api_key_is_clear_for_real_client_mode():
    monitor = TokenBudgetMonitor()
    client = OpenAIChatClient(
        app_config=AppConfig(model="gpt-4o-mini"),
        environment=EnvironmentConfig(openai_api_key=None),
        budget_monitor=monitor,
    )

    with pytest.raises(MissingApiKeyError, match="OPENAI_API_KEY"):
        client.complete([{"role": "user", "content": "Hi"}])


def test_create_chat_client_factory_returns_mock_by_default():
    runtime = RuntimeConfig(
        app=AppConfig(model="demo-model"),
        environment=EnvironmentConfig(),
    )
    monitor = TokenBudgetMonitor(runtime.app)

    client = create_chat_client(runtime, budget_monitor=monitor, mode="mock")

    response = client.complete([{"role": "user", "content": "Hello"}])

    assert response.mock is True
    assert response.model == "demo-model"


def test_token_usage_rejects_negative_values():
    with pytest.raises(ValueError, match="negative"):
        TokenUsage(input_tokens=-1)
