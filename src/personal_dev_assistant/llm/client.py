"""OpenAI-compatible chat client with mock and budget integration."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import AppConfig, EnvironmentConfig, RuntimeConfig
from personal_dev_assistant.models import TokenUsage


class BudgetExceededError(Exception):
    """Raised when a call is refused because the token budget hard cap was reached."""


class MissingApiKeyError(Exception):
    """Raised when a real API client is used without an API key."""


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM chat completion."""

    text: str
    usage: TokenUsage
    model: str
    mock: bool


class ChatClient(ABC):
    """Chat completion client integrated with token budget monitoring."""

    def __init__(self, *, model: str, budget_monitor: TokenBudgetMonitor) -> None:
        self._model = model
        self._budget_monitor = budget_monitor

    def complete(self, messages: list[Mapping[str, str]]) -> LLMResponse:
        """Run one chat completion and record token usage in the budget monitor."""

        status = self._budget_monitor.status()
        if not status.can_continue:
            raise BudgetExceededError(
                status.message
                or "Token budget hard cap reached. No more LLM calls should run."
            )

        response = self._complete(messages)
        self._budget_monitor.add_usage(response.usage)
        return response

    @abstractmethod
    def _complete(self, messages: list[Mapping[str, str]]) -> LLMResponse:
        """Provider-specific completion without budget checks."""


class MockChatClient(ChatClient):
    """Deterministic dry-run client for tests and local development."""

    def __init__(
        self,
        *,
        model: str,
        budget_monitor: TokenBudgetMonitor,
        response_text: str = "Mock LLM response.",
    ) -> None:
        super().__init__(model=model, budget_monitor=budget_monitor)
        self._response_text = response_text

    def _complete(self, messages: list[Mapping[str, str]]) -> LLMResponse:
        input_tokens = _estimate_tokens(_messages_text(messages))
        output_tokens = _estimate_tokens(self._response_text)

        return LLMResponse(
            text=self._response_text,
            usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            model=self._model,
            mock=True,
        )


class OpenAIChatClient(ChatClient):
    """Small OpenAI-compatible HTTP chat client."""

    def __init__(
        self,
        *,
        app_config: AppConfig,
        environment: EnvironmentConfig,
        budget_monitor: TokenBudgetMonitor,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        super().__init__(model=app_config.model, budget_monitor=budget_monitor)
        self._api_key = environment.openai_api_key
        self._base_url = base_url.rstrip("/")

    def _complete(self, messages: list[Mapping[str, str]]) -> LLMResponse:
        if not self._api_key:
            raise MissingApiKeyError(
                "OPENAI_API_KEY is required for real LLM calls. "
                "Use MockChatClient or set the environment variable."
            )

        payload = {
            "model": self._model,
            "messages": [dict(message) for message in messages],
        }
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API request failed: {error.code} {details}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"OpenAI API request failed: {error}") from error

        choice = body["choices"][0]["message"]["content"]
        usage_data = body.get("usage", {})
        usage = TokenUsage(
            input_tokens=int(usage_data.get("prompt_tokens", 0)),
            output_tokens=int(usage_data.get("completion_tokens", 0)),
            total_tokens=int(usage_data.get("total_tokens", 0)) or None,
        )

        return LLMResponse(
            text=str(choice),
            usage=usage,
            model=self._model,
            mock=False,
        )


def create_chat_client(
    runtime_config: RuntimeConfig,
    *,
    budget_monitor: TokenBudgetMonitor,
    mode: str = "mock",
    mock_response_text: str = "Mock LLM response.",
) -> ChatClient:
    """Create a chat client for mock dry-run or real OpenAI-compatible calls."""

    if mode == "mock":
        return MockChatClient(
            model=runtime_config.app.model,
            budget_monitor=budget_monitor,
            response_text=mock_response_text,
        )
    if mode == "openai":
        return OpenAIChatClient(
            app_config=runtime_config.app,
            environment=runtime_config.environment,
            budget_monitor=budget_monitor,
        )
    raise ValueError(f"Unsupported LLM client mode: {mode}")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate for mock usage tracking."""

    if not text:
        return 0
    return max(1, len(text) // 4)


def _messages_text(messages: list[Mapping[str, str]]) -> str:
    parts = []
    for message in messages:
        parts.append(str(message.get("role", "")))
        parts.append(str(message.get("content", "")))
    return "\n".join(parts)
