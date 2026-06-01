# Technical Spec

This document defines the small implementation target for Personal Dev Assistant. The goal is a clear, demo-friendly terminal assistant, not a full coding-agent platform.

## Python version and tech stack

- Python: 3.12.
- Runtime style: terminal CLI application.
- Testing: `pytest`.
- Configuration: `config.yaml` for non-secret settings and environment variables for secrets.
- LLM provider: OpenAI-compatible chat API (OpenRouter supported via env vars and `config.yaml` model id).
- Packaging target: simple local install/run instructions first. Before final submission, the project should either include Docker packaging or a very clear, idiot-proof setup guide.

## Configuration

The project root contains a non-secret `config.yaml` with default runtime settings.

```yaml
model: "openai/gpt-5.1-codex-mini"
token_budget:
  max_tokens: 50000
  warning_threshold: 0.8
  hard_cap_enabled: true
safety:
  require_confirmation_for_risky_commands: true
  allow_file_edits: true
context:
  max_observation_chars: 4000
  max_subagent_summary_chars: 1500
tools:
  command_timeout_seconds: 30
  test_command: "pytest"
```

Expected behavior:

- Missing optional config values should fall back to documented defaults.
- Invalid config values should produce a clear error before the agent starts.
- Secret values must never be stored in `config.yaml`.

## Environment variables

Required for experimental LLM mode with OpenRouter:

- `OPENAI_API_KEY`: your OpenRouter API key.
- `OPENAI_BASE_URL`: `https://openrouter.ai/api/v1`

Optional:

- `MODEL`: overrides `model` from `config.yaml`.
- `TOKEN_BUDGET`: overrides `token_budget.max_tokens`.
- `REQUIRE_COMMAND_APPROVAL`: overrides `safety.require_confirmation_for_risky_commands`.
- `MAX_TOOL_OUTPUT_CHARS`: overrides `context.max_observation_chars`.

## CLI behavior

The CLI should support a small interactive flow:

1. Load `config.yaml`.
2. Load required prompt files from `prompts/`.
3. Validate required environment variables.
4. Start a main-agent loop in the current working directory.
5. Accept a user task.
6. Decide whether to answer directly, call a tool, or ask a sub-agent for help.
7. Show short observations and final summaries in the terminal.

The first implementation may also support a single-command demo mode:

```bash
personal-dev-assistant "Find and fix the failing test in demo_project"
```

## Agent protocol

All agents should return structured results so the main loop can make predictable decisions.

Main agent expected output:

```yaml
thought_summary: "Short private-work summary safe to show in logs"
action:
  type: "respond | tool_call | subagent_call | finish"
  name: "optional tool or sub-agent name"
  input: {}
final_response: "Only set when type is respond or finish"
```

Sub-agent expected output:

```yaml
role: "planner | explorer | coder | reviewer"
summary: "Compact result for the main agent"
findings:
  - "Important observation or recommendation"
risk_level: "low | medium | high"
recommended_next_step: "Concrete next action"
```

The main agent should only receive compact sub-agent summaries, not full raw logs.

## Tool contracts

### `read_file`

Purpose: read a text file from the project directory.

Input:

```yaml
path: "relative/path.py"
```

Output:

```yaml
ok: true
path: "relative/path.py"
content: "file content or truncated content"
truncated: false
summary: "set when content is too large"
```

Rules:

- Must reject blocked paths from `docs/safety-policy.md`.
- Must limit output according to `context.max_observation_chars`.

### `bash`

Purpose: run an approved shell command in the project directory.

Input:

```yaml
command: "pytest demo_project"
```

Output:

```yaml
ok: true
exit_code: 0
stdout: "captured stdout or truncated stdout"
stderr: "captured stderr or truncated stderr"
summary: "short observation for context"
```

Rules:

- Must pass through the safety checker before execution.
- Must apply a timeout.
- Must summarize long output before returning it to the main agent.

### `partial_edit`

Purpose: make a small, focused edit to an allowed text file.

Input:

```yaml
path: "relative/path.py"
old_text: "exact text to replace"
new_text: "replacement text"
reason: "why this edit is needed"
```

Output:

```yaml
ok: true
path: "relative/path.py"
changed: true
summary: "what changed"
```

Rules:

- Must reject blocked paths.
- Must require `old_text` to match exactly once.
- Must avoid rewriting entire files unless the file is very small and the plan explicitly allows it.
- Should be reviewed by the reviewer/safety step before execution when the edit is risky.

### `test_runner`

Purpose: run the configured test command.

Input:

```yaml
target: "demo_project"
```

Output:

```yaml
ok: true
exit_code: 0
summary: "test result summary"
raw_output_ref: "optional path or identifier for raw logs"
```

Rules:

- Should use `tools.test_command` from `config.yaml`.
- Should route execution through the `bash` tool so command safety and output limits are reused.
