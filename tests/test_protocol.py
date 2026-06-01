from __future__ import annotations

from personal_dev_assistant.agents.protocol import parse_agent_action


def test_parse_inline_bash_command():
    action = parse_agent_action("ACTION: bash command: pytest demo_project")

    assert action.name == "bash"
    assert action.params["command"] == "pytest demo_project"


def test_parse_inline_read_file_path():
    action = parse_agent_action(
        "ACTION: read_file path: demo_project/calculator.py"
    )

    assert action.name == "read_file"
    assert action.params["path"] == "demo_project/calculator.py"


def test_parse_inline_propose_edit_path_without_blocks_still_missing_fields():
    action = parse_agent_action(
        "ACTION: propose_edit path: demo_project/calculator.py"
    )

    assert action.name == "propose_edit"
    assert action.params["path"] == "demo_project/calculator.py"
    assert "old_text" not in action.params or not action.params.get("old_text", "").strip()
    assert "new_text" not in action.params or not action.params.get("new_text", "").strip()


def test_parse_standard_multiline_bash_still_works():
    text = "ACTION: bash\nCOMMAND: pytest demo_project"
    action = parse_agent_action(text)

    assert action.name == "bash"
    assert action.params["command"] == "pytest demo_project"


def test_unsupported_inline_action_not_normalized_to_allowed_action():
    action = parse_agent_action("ACTION: run_shell command: pytest demo_project")

    assert action.name == "run_shell"
    assert "command" not in action.params


def test_experimental_agent_inline_bash_not_blocked(tmp_path):
    from personal_dev_assistant.agents import MainAgent
    from personal_dev_assistant.agents.main import (
        EXPERIMENTAL_ACTION_PROTOCOL,
        EXPERIMENTAL_ALLOWED_ACTIONS,
    )
    from personal_dev_assistant.budget import TokenBudgetMonitor
    from personal_dev_assistant.config import AppConfig, EnvironmentConfig, RuntimeConfig
    from tests.test_main_agent import ScriptedChatClient

    runtime = RuntimeConfig(
        app=AppConfig(),
        environment=EnvironmentConfig(),
    )
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            "ACTION: bash command: pytest demo_project",
            "ACTION: finish\nFINAL: Done.",
        ],
    )
    agent = MainAgent(
        runtime_config=runtime,
        chat_client=client,
        project_root=tmp_path,
        budget_monitor=monitor,
        allowed_actions=EXPERIMENTAL_ALLOWED_ACTIONS,
        stop_on_invalid_action=True,
        action_protocol=EXPERIMENTAL_ACTION_PROTOCOL,
    )

    result = agent.run("Run tests.")

    assert result.stopped_reason == "finish"
    assert not any("not allowed" in obs for obs in result.observations)


def test_parse_split_action_line_list_project_files():
    action = parse_agent_action("ACTION:\nlist_project_files")

    assert action.name == "list_project_files"
    assert action.params == {}


def test_parse_split_action_line_bash_with_command():
    text = "ACTION:\nbash\nCOMMAND: pytest demo_project"
    action = parse_agent_action(text)

    assert action.name == "bash"
    assert action.params["command"] == "pytest demo_project"


def test_parse_split_action_line_read_file_with_path():
    text = "ACTION:\nread_file\nPATH: demo_project/calculator.py"
    action = parse_agent_action(text)

    assert action.name == "read_file"
    assert action.params["path"] == "demo_project/calculator.py"


def test_parse_split_action_line_unknown_prose_remains_unknown():
    action = parse_agent_action("ACTION:\nI am sorry, but I cannot help with that.")

    assert action.name == "unknown"


def test_experimental_agent_split_action_list_not_unknown(tmp_path):
    from personal_dev_assistant.agents import MainAgent
    from personal_dev_assistant.agents.main import (
        EXPERIMENTAL_ACTION_PROTOCOL,
        EXPERIMENTAL_ALLOWED_ACTIONS,
    )
    from personal_dev_assistant.budget import TokenBudgetMonitor
    from personal_dev_assistant.config import AppConfig, EnvironmentConfig, RuntimeConfig
    from tests.test_main_agent import ScriptedChatClient

    runtime = RuntimeConfig(
        app=AppConfig(),
        environment=EnvironmentConfig(),
    )
    monitor = TokenBudgetMonitor(runtime.app)
    client = ScriptedChatClient(
        model=runtime.app.model,
        budget_monitor=monitor,
        responses=[
            "ACTION:\nlist_project_files",
            "ACTION: finish\nFINAL: Done.",
        ],
    )
    agent = MainAgent(
        runtime_config=runtime,
        chat_client=client,
        project_root=tmp_path,
        budget_monitor=monitor,
        allowed_actions=EXPERIMENTAL_ALLOWED_ACTIONS,
        stop_on_invalid_action=True,
        action_protocol=EXPERIMENTAL_ACTION_PROTOCOL,
    )

    result = agent.run("List files.")

    assert result.stopped_reason == "finish"
    assert not any("invalid_action" in obs.lower() for obs in result.observations)
