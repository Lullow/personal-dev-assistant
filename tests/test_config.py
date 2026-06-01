from __future__ import annotations

import textwrap

import pytest

from personal_dev_assistant.config import (
    AppConfig,
    DEFAULT_OPENAI_BASE_URL,
    load_app_config,
    load_runtime_config,
    resolve_openai_base_url,
)


def test_load_app_config_reads_config_yaml(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            model: "demo-model"
            token_budget:
              max_tokens: 1234
              warning_threshold: 0.5
              hard_cap_enabled: false
            safety:
              require_confirmation_for_risky_commands: false
              allow_file_edits: true
            context:
              max_observation_chars: 999
              max_subagent_summary_chars: 111
            tools:
              command_timeout_seconds: 7
              test_command: "pytest demo_project"
            """
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, environ={})

    assert config.model == "demo-model"
    assert config.token_budget.max_tokens == 1234
    assert config.token_budget.warning_threshold == 0.5
    assert config.token_budget.hard_cap_enabled is False
    assert config.safety.require_confirmation_for_risky_commands is False
    assert config.context.max_observation_chars == 999
    assert config.context.max_subagent_summary_chars == 111
    assert config.tools.command_timeout_seconds == 7
    assert config.tools.test_command == "pytest demo_project"


def test_load_app_config_uses_defaults_when_file_is_missing(tmp_path):
    config = load_app_config(tmp_path / "missing.yaml", environ={})

    assert config == AppConfig()


def test_load_app_config_applies_environment_overrides(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text('model: "from-file"\n', encoding="utf-8")

    config = load_app_config(
        config_path,
        environ={
            "MODEL": "from-env",
            "TOKEN_BUDGET": "42",
            "REQUIRE_COMMAND_APPROVAL": "false",
            "MAX_TOOL_OUTPUT_CHARS": "321",
        },
    )

    assert config.model == "from-env"
    assert config.token_budget.max_tokens == 42
    assert config.safety.require_confirmation_for_risky_commands is False
    assert config.context.max_observation_chars == 321


def test_load_runtime_config_reads_secret_environment_without_requiring_api_call(
    tmp_path, isolated_openai_env
):
    runtime = load_runtime_config(
        tmp_path / "missing.yaml",
        environ={"OPENAI_API_KEY": "test-key"},
    )

    assert runtime.environment.has_openai_api_key is True
    assert runtime.environment.openai_api_key == "test-key"


def test_load_runtime_config_reads_openai_base_url(tmp_path):
    runtime = load_runtime_config(
        tmp_path / "missing.yaml",
        environ={
            "OPENAI_API_KEY": "test-key",
            "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
        },
    )

    assert runtime.environment.openai_base_url == "https://openrouter.ai/api/v1"
    assert runtime.environment.effective_openai_base_url == "https://openrouter.ai/api/v1"


def test_resolve_openai_base_url_defaults_to_openai(isolated_openai_env):
    assert resolve_openai_base_url(None) == DEFAULT_OPENAI_BASE_URL
    assert resolve_openai_base_url("") == DEFAULT_OPENAI_BASE_URL


def test_resolve_openai_base_url_strips_trailing_slash():
    assert (
        resolve_openai_base_url("https://openrouter.ai/api/v1/")
        == "https://openrouter.ai/api/v1"
    )


def test_load_app_config_rejects_invalid_values(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            token_budget:
              max_tokens: 0
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="max_tokens"):
        load_app_config(config_path, environ={})
