"""Optional LLM intent classification for interactive chat (command routing only)."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from personal_dev_assistant.budget import TokenBudgetMonitor
from personal_dev_assistant.config import RuntimeConfig
from personal_dev_assistant.llm.client import (
    BudgetExceededError,
    ChatClient,
    MissingApiKeyError,
    create_chat_client,
)

ALLOWED_INTENTS: frozenset[str] = frozenset(
    {
        "help",
        "list",
        "read",
        "current",
        "review",
        "fix",
        "apply",
        "reject",
        "test",
        "tokens",
        "compact",
        "exit",
        "unknown",
    }
)

_ACCEPTABLE_CONFIDENCE: frozenset[str] = frozenset({"high", "medium"})

_INTENT_SYSTEM_PROMPT = """You classify user input for a terminal coding assistant.

Return ONLY one JSON object with this shape (no markdown, no prose):
{
  "intent": "<one allowed intent>",
  "arg": "<string or null>",
  "confidence": "high|medium|low",
  "reason": "short explanation"
}

Allowed intents (choose exactly one):
help, list, read, current, review, fix, apply, reject, test, tokens, compact, exit, unknown

Rules:
- Classify intent only. Never output bash commands, file edits, or tool calls.
- Use read only when the user clearly wants to open/read a file; put the relative path in arg.
- Use apply only when the user explicitly wants to apply an already pending edit.
- Use unknown when the request is unclear or outside allowed intents.
- Prefer unknown over guessing when unsure."""

_INTENT_UNKNOWN_USER_MESSAGE = (
    "Could not confidently interpret that request. "
    "Try a command from help, or rephrase more clearly."
)
_INTENT_APPLY_REQUIRES_SLASH_MESSAGE = "Applying edits requires explicit /apply."


@dataclass(frozen=True)
class IntentClassification:
    """Structured LLM intent classification result."""

    intent: str
    arg: str | None
    confidence: str
    reason: str


class IntentClassifier(ABC):
    """Classifies natural language into allowed interactive commands."""

    @abstractmethod
    def classify(self, user_input: str) -> IntentClassification | None:
        """Return a classification, or None on failure."""


class ScriptedIntentClassifier(IntentClassifier):
    """Test double that returns predefined classifications per input."""

    def __init__(
        self,
        responses: Mapping[str, IntentClassification | dict[str, object]],
    ) -> None:
        self._responses: dict[str, IntentClassification] = {}
        for key, value in responses.items():
            if isinstance(value, IntentClassification):
                self._responses[key.strip().lower()] = value
            else:
                self._responses[key.strip().lower()] = IntentClassification(
                    intent=str(value["intent"]),
                    arg=value.get("arg"),  # type: ignore[arg-type]
                    confidence=str(value.get("confidence", "high")),
                    reason=str(value.get("reason", "")),
                )

    def classify(self, user_input: str) -> IntentClassification | None:
        key = user_input.strip().lower()
        return self._responses.get(key)


class ChatIntentClassifier(IntentClassifier):
    """Uses an OpenAI-compatible chat client for JSON intent classification only."""

    def __init__(self, chat_client: ChatClient) -> None:
        self._chat_client = chat_client

    def classify(self, user_input: str) -> IntentClassification | None:
        try:
            response = self._chat_client.complete(
                [
                    {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_input.strip()},
                ]
            )
        except (BudgetExceededError, MissingApiKeyError, OSError, ValueError):
            return None

        return parse_intent_json(response.text)


def parse_intent_json(text: str) -> IntentClassification | None:
    """Parse and validate intent JSON from model output."""

    payload = _extract_json_object(text)
    if payload is None:
        return None

    intent = str(payload.get("intent", "")).strip().lower()
    if intent not in ALLOWED_INTENTS:
        return None

    confidence = str(payload.get("confidence", "")).strip().lower()
    if confidence not in _ACCEPTABLE_CONFIDENCE | {"low"}:
        return None

    arg_value = payload.get("arg")
    arg: str | None
    if arg_value is None:
        arg = None
    else:
        stripped = str(arg_value).strip()
        arg = stripped or None

    reason = str(payload.get("reason", "")).strip()

    return IntentClassification(
        intent=intent,
        arg=arg,
        confidence=confidence,
        reason=reason,
    )


def classification_to_command(
    classification: IntentClassification,
) -> tuple[str, str | None, str | None]:
    """Convert classification to command name, arg, and optional user message."""

    if classification.confidence not in _ACCEPTABLE_CONFIDENCE:
        return "unknown", None, _INTENT_UNKNOWN_USER_MESSAGE

    if classification.intent == "unknown":
        return "unknown", None, _INTENT_UNKNOWN_USER_MESSAGE

    if classification.intent not in ALLOWED_INTENTS:
        return "unknown", None, _INTENT_UNKNOWN_USER_MESSAGE

    if classification.intent == "apply":
        return "unknown", None, _INTENT_APPLY_REQUIRES_SLASH_MESSAGE

    return classification.intent, classification.arg, None


def create_intent_classifier(
    runtime_config: RuntimeConfig,
    *,
    budget_monitor: TokenBudgetMonitor,
    mode: str = "openai",
) -> IntentClassifier | None:
    """Build a chat-backed intent classifier when an API key is configured."""

    if not runtime_config.environment.has_openai_api_key:
        return None

    client = create_chat_client(
        runtime_config,
        budget_monitor=budget_monitor,
        mode=mode,
    )
    return ChatIntentClassifier(client)


def _extract_json_object(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict):
        return None
    return parsed
