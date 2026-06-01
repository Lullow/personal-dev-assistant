from __future__ import annotations

import json
import urllib.request

import pytest

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import (
    AppConfig,
    DEFAULT_OPENAI_BASE_URL,
    EnvironmentConfig,
    RuntimeConfig,
    TokenBudgetConfig,
    load_runtime_config,
    resolve_openai_base_url,
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


def test_openai_chat_client_default_base_url(isolated_openai_env):
    monitor = TokenBudgetMonitor()
    client = OpenAIChatClient(
        app_config=AppConfig(model="gpt-4o-mini"),
        environment=EnvironmentConfig(openai_api_key="test-key"),
        budget_monitor=monitor,
    )

    assert client.chat_completions_url == f"{DEFAULT_OPENAI_BASE_URL}/chat/completions"


def test_openai_chat_client_uses_openrouter_base_url_from_environment():
    monitor = TokenBudgetMonitor()
    client = OpenAIChatClient(
        app_config=AppConfig(model="openai/gpt-5.1-codex-mini"),
        environment=EnvironmentConfig(
            openai_api_key="test-key",
            openai_base_url="https://openrouter.ai/api/v1",
        ),
        budget_monitor=monitor,
    )

    assert (
        client.chat_completions_url
        == "https://openrouter.ai/api/v1/chat/completions"
    )


def test_create_chat_client_openai_mode_uses_runtime_base_url():
    runtime = load_runtime_config(
        "missing.yaml",
        environ={
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1/",
        },
    )
    monitor = TokenBudgetMonitor(runtime.app)

    client = create_chat_client(runtime, budget_monitor=monitor, mode="openai")

    assert isinstance(client, OpenAIChatClient)
    assert client.chat_completions_url == "https://openrouter.ai/api/v1/chat/completions"


def test_openai_chat_client_posts_to_configured_url(monkeypatch):
    captured: dict[str, str] = {}

    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request, timeout=60):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    monitor = TokenBudgetMonitor()
    client = OpenAIChatClient(
        app_config=AppConfig(),
        environment=EnvironmentConfig(
            openai_api_key="test-key",
            openai_base_url="https://openrouter.ai/api/v1",
        ),
        budget_monitor=monitor,
    )

    response = client.complete([{"role": "user", "content": "Hi"}])

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert response.text == "ok"
    assert response.mock is False
