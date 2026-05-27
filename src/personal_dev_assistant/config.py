"""Configuration and environment loading for Personal Dev Assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class TokenBudgetConfig:
    max_tokens: int = 50_000
    warning_threshold: float = 0.8
    hard_cap_enabled: bool = True


@dataclass(frozen=True)
class SafetyConfig:
    require_confirmation_for_risky_commands: bool = True
    allow_file_edits: bool = True


@dataclass(frozen=True)
class ContextConfig:
    max_observation_chars: int = 4_000
    max_subagent_summary_chars: int = 1_500


@dataclass(frozen=True)
class ToolsConfig:
    command_timeout_seconds: int = 30
    test_command: str = "pytest"


@dataclass(frozen=True)
class AppConfig:
    model: str = "gpt-4o-mini"
    token_budget: TokenBudgetConfig = TokenBudgetConfig()
    safety: SafetyConfig = SafetyConfig()
    context: ContextConfig = ContextConfig()
    tools: ToolsConfig = ToolsConfig()


@dataclass(frozen=True)
class EnvironmentConfig:
    openai_api_key: str | None = None

    @property
    def has_openai_api_key(self) -> bool:
        return bool(self.openai_api_key)


@dataclass(frozen=True)
class RuntimeConfig:
    app: AppConfig
    environment: EnvironmentConfig


def load_runtime_config(
    config_path: str | Path = "config.yaml",
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Load non-secret app config and secret environment settings."""

    env = os.environ if environ is None else environ
    app_config = load_app_config(config_path=config_path, environ=env)
    environment = EnvironmentConfig(openai_api_key=_blank_to_none(env.get("OPENAI_API_KEY")))
    return RuntimeConfig(app=app_config, environment=environment)


def load_app_config(
    config_path: str | Path = "config.yaml",
    environ: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load `config.yaml`, apply environment overrides, and validate values."""

    env = os.environ if environ is None else environ
    data = _read_yaml_mapping(Path(config_path))
    config = _config_from_mapping(data)
    config = _apply_env_overrides(config, env)
    _validate_config(config)
    return config


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    return _parse_simple_yaml(path.read_text(encoding="utf-8"), path)


def _parse_simple_yaml(content: str, path: Path) -> dict[str, Any]:
    """Parse the small config.yaml subset used by this project.

    This intentionally supports only top-level keys and one nested mapping level.
    That keeps the first foundation step dependency-free and easy to test.
    """

    result: dict[str, Any] = {}
    current_section: dict[str, Any] | None = None

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if ":" not in stripped:
            raise ValueError(f"Invalid config line {line_number} in {path}.")

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if not key:
            raise ValueError(f"Invalid empty config key on line {line_number} in {path}.")

        if indent == 0:
            if raw_value == "":
                current_section = {}
                result[key] = current_section
            else:
                current_section = None
                result[key] = _parse_scalar(raw_value)
            continue

        if indent != 2 or current_section is None:
            raise ValueError(f"Unsupported config nesting on line {line_number} in {path}.")

        current_section[key] = _parse_scalar(raw_value)

    return result


def _parse_scalar(value: str) -> Any:
    if value.startswith(("\"", "'")) and value.endswith(("\"", "'")):
        return value[1:-1]

    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def _config_from_mapping(data: Mapping[str, Any]) -> AppConfig:
    defaults = AppConfig()

    token_budget = _nested_mapping(data, "token_budget")
    safety = _nested_mapping(data, "safety")
    context = _nested_mapping(data, "context")
    tools = _nested_mapping(data, "tools")

    return AppConfig(
        model=str(data.get("model", defaults.model)),
        token_budget=TokenBudgetConfig(
            max_tokens=int(token_budget.get("max_tokens", defaults.token_budget.max_tokens)),
            warning_threshold=float(
                token_budget.get(
                    "warning_threshold",
                    defaults.token_budget.warning_threshold,
                )
            ),
            hard_cap_enabled=_as_bool(
                token_budget.get(
                    "hard_cap_enabled",
                    defaults.token_budget.hard_cap_enabled,
                )
            ),
        ),
        safety=SafetyConfig(
            require_confirmation_for_risky_commands=_as_bool(
                safety.get(
                    "require_confirmation_for_risky_commands",
                    defaults.safety.require_confirmation_for_risky_commands,
                )
            ),
            allow_file_edits=_as_bool(
                safety.get("allow_file_edits", defaults.safety.allow_file_edits)
            ),
        ),
        context=ContextConfig(
            max_observation_chars=int(
                context.get(
                    "max_observation_chars",
                    defaults.context.max_observation_chars,
                )
            ),
            max_subagent_summary_chars=int(
                context.get(
                    "max_subagent_summary_chars",
                    defaults.context.max_subagent_summary_chars,
                )
            ),
        ),
        tools=ToolsConfig(
            command_timeout_seconds=int(
                tools.get(
                    "command_timeout_seconds",
                    defaults.tools.command_timeout_seconds,
                )
            ),
            test_command=str(tools.get("test_command", defaults.tools.test_command)),
        ),
    )


def _nested_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Config section `{key}` must be a mapping.")
    return value


def _apply_env_overrides(config: AppConfig, env: Mapping[str, str]) -> AppConfig:
    model = _blank_to_none(env.get("MODEL"))
    token_budget = _blank_to_none(env.get("TOKEN_BUDGET"))
    require_approval = _blank_to_none(env.get("REQUIRE_COMMAND_APPROVAL"))
    max_tool_output = _blank_to_none(env.get("MAX_TOOL_OUTPUT_CHARS"))

    if model is not None:
        config = replace(config, model=model)
    if token_budget is not None:
        config = replace(
            config,
            token_budget=replace(config.token_budget, max_tokens=int(token_budget)),
        )
    if require_approval is not None:
        config = replace(
            config,
            safety=replace(
                config.safety,
                require_confirmation_for_risky_commands=_as_bool(require_approval),
            ),
        )
    if max_tool_output is not None:
        config = replace(
            config,
            context=replace(config.context, max_observation_chars=int(max_tool_output)),
        )

    return config


def _validate_config(config: AppConfig) -> None:
    if not config.model.strip():
        raise ValueError("Config value `model` cannot be empty.")
    if config.token_budget.max_tokens <= 0:
        raise ValueError("Config value `token_budget.max_tokens` must be positive.")
    if not 0 < config.token_budget.warning_threshold <= 1:
        raise ValueError(
            "Config value `token_budget.warning_threshold` must be greater than 0 and at most 1."
        )
    if config.context.max_observation_chars <= 0:
        raise ValueError("Config value `context.max_observation_chars` must be positive.")
    if config.context.max_subagent_summary_chars <= 0:
        raise ValueError(
            "Config value `context.max_subagent_summary_chars` must be positive."
        )
    if config.tools.command_timeout_seconds <= 0:
        raise ValueError("Config value `tools.command_timeout_seconds` must be positive.")
    if not config.tools.test_command.strip():
        raise ValueError("Config value `tools.test_command` cannot be empty.")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError(f"Expected a boolean value, got {value!r}.")


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None
