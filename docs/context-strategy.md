# Context Strategy

The assistant should keep active context small and useful. Raw tool logs can be long, repetitive, or noisy, so the main agent should receive compact observations unless full content is necessary.

## Active context vs raw logs

Active context is the information sent into the next agent decision. It should contain:

- the user task
- current plan
- relevant file summaries or short file excerpts
- compact tool observations
- sub-agent summaries
- token budget status

Raw logs are full command outputs, full file contents, or verbose sub-agent details. Raw logs may be stored for debugging, but they should not automatically be added to active context.

## Max observation size

The default max observation size is `4000` characters, configured by `context.max_observation_chars` in `config.yaml`.

When a tool result is shorter than the limit, it can be returned directly. When it is longer, the tool should return:

- a short summary
- the most relevant error lines or changed lines
- whether the output was truncated
- an optional raw log reference for debugging

## Summarization and compaction

Summaries should preserve:

- command or tool name
- success/failure status
- exit code when available
- important errors
- files inspected or changed
- next useful action

Summaries should remove:

- repeated stack trace lines unless needed
- long passing-test output
- dependency installation noise
- unrelated file listings
- implementation details that do not affect the next decision

The context manager should compact older observations when active context grows too large. Recent user instructions and safety decisions must be preserved.

## Sub-agent output compaction

Sub-agents should not return raw exploration logs to the main agent. They should return structured summaries with:

- role
- short summary
- key findings
- risk level
- recommended next step

Example:

```yaml
role: "explorer"
summary: "The failing demo test checks add(2, 3) == 5, but add returns a - b."
findings:
  - "demo_project/test_calculator.py expects addition."
  - "demo_project/calculator.py currently subtracts."
risk_level: "low"
recommended_next_step: "Ask coder agent to prepare a one-line partial edit."
```

The main agent may keep the full sub-agent result in raw logs, but only the compact summary should be used for the next prompt.

## Interactive Assistant v.2 session compaction

Chat mode (`personal-dev-assistant chat`) maintains session state separately from the main agent loop:

- **Preserved across compaction:** `current_file_path`, `current_file_content`, `pending_edit`, `last_review_summary`, `last_test_result`, and a rolling `context_summary`.
- **Trimmed:** `action_history` — older command summaries are folded into `context_summary` when the user runs `compact context` or when history exceeds a character threshold (automatic compaction).
- **Manual compaction** prints a short summary: actions before/after, kept session keys.
- **Not LLM-driven:** compaction rules are deterministic; no API key required.

This mirrors the same principle as tool observation compaction: keep what the user and assistant need for the next step, drop verbose history.
