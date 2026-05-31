"""CLI entrypoint for Personal Dev Assistant."""

from __future__ import annotations

import argparse
from pathlib import Path

from personal_dev_assistant.config import load_app_config, load_runtime_config
from personal_dev_assistant.interactive import run_interactive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="personal-dev-assistant",
        description="Small terminal-based coding assistant.",
    )

    subparsers = parser.add_subparsers(dest="mode")

    chat_parser = subparsers.add_parser(
        "chat",
        help="Start deterministic interactive terminal mode.",
    )
    chat_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the non-secret YAML config file.",
    )
    chat_parser.add_argument(
        "--project-root",
        default=".",
        help="Project root for safe tool operations.",
    )

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Alias for chat mode.",
    )
    interactive_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the non-secret YAML config file.",
    )
    interactive_parser.add_argument(
        "--project-root",
        default=".",
        help="Project root for safe tool operations.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Legacy single-task placeholder (non-interactive).",
    )
    run_parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the non-secret YAML config file.",
    )
    run_parser.add_argument("task", help="User task for the assistant.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode in {"chat", "interactive"}:
        app_config = load_app_config(Path(args.config))
        return run_interactive(
            project_root=args.project_root,
            app_config=app_config,
        )

    if args.mode == "run":
        runtime_config = load_runtime_config(Path(args.config))
        api_key_status = "configured" if runtime_config.environment.has_openai_api_key else "missing"
        print("Personal Dev Assistant legacy run mode.")
        print(f"Task received: {args.task}")
        print(f"Model setting: {runtime_config.app.model}")
        print(f"OPENAI_API_KEY: {api_key_status}")
        print("Tip: use 'personal-dev-assistant chat' for interactive terminal mode.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
