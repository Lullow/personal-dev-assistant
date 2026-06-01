"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import pytest

OPENAI_ENV_VARS = ("OPENAI_API_KEY", "OPENAI_BASE_URL")


def clear_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove OpenAI/OpenRouter env vars so tests do not inherit the developer shell."""

    for name in OPENAI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def isolated_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure OPENAI_API_KEY and OPENAI_BASE_URL are unset for this test."""

    clear_openai_env(monkeypatch)
