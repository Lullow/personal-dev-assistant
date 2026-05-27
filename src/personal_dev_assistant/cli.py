"""Minimal CLI entrypoint for the first foundation step."""

from __future__ import annotations

import argparse
from pathlib import Path

from personal_dev_assistant.config import load_runtime_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-dev-assistant",
        description="Small terminal-based coding assistant foundation CLI.",
    )
    parser.add_argument("task", help="User task for the assistant.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the non-secret YAML config file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime_config = load_runtime_config(Path(args.config))

    api_key_status = "configured" if runtime_config.environment.has_openai_api_key else "missing"
    print("Personal Dev Assistant foundation is ready.")
    print(f"Task received: {args.task}")
    print(f"Model setting: {runtime_config.app.model}")
    print(f"OPENAI_API_KEY: {api_key_status}")
    print("Placeholder response: agent loop, tools, LLM calls, and sub-agents are not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
