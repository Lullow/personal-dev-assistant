# Test Plan

The test strategy should prove the VG requirements without making the project too large. Unit tests should cover core rules, integration tests should cover agent coordination, and the demo should show the full workflow.

## Unit tests

### Config

- Loads `config.yaml`.
- Applies documented defaults for missing optional values.
- Allows environment variables to override config values.
- Rejects invalid values with clear errors.
- Requires `OPENAI_API_KEY` before starting an LLM-backed session.

### Safety

- Blocks destructive commands such as `rm -rf`, `sudo`, and `git reset --hard`.
- Requires confirmation for risky commands such as installs and git writes.
- Allows safe commands such as `pytest` and `python --version`.
- Blocks reads and edits to `.env`, `.git/`, `.venv/`, `__pycache__/`, and `.pytest_cache/`.

### Tools

- `read_file` returns allowed file content and rejects blocked paths.
- `bash` routes every command through the safety checker.
- `bash` captures exit code, stdout, and stderr.
- `bash` applies timeout and output size limits.
- `partial_edit` only replaces an exact single match.
- `partial_edit` rejects duplicate matches and blocked paths.
- `test_runner` uses the configured test command and summarizes results.

### Context

- Short observations are kept directly.
- Long observations are summarized and marked as truncated.
- Raw logs are kept separate from active context.
- Sub-agent results are compacted before returning to the main agent.

### Token budget

- Tracks approximate token usage per interaction.
- Emits a warning when usage reaches the configured threshold.
- Stops or refuses further tool/agent calls when the hard cap is reached.

## Integration tests

### Main agent loop

- Accepts a user task.
- Chooses whether to answer, call a tool, call a sub-agent, or finish.
- Stops with a clear final response when the task is complete.
- Preserves user instructions across multiple steps.

### Sub-agent orchestration

- Main agent can request a planner summary.
- Main agent can request an explorer summary after file inspection.
- Main agent can request a coder edit proposal.
- Main agent can request reviewer/safety approval before risky actions.
- Main agent receives compact structured outputs, not raw sub-agent logs.

## Demo acceptance criteria

The demo uses `demo_project/`.

Starting state:

- `demo_project/test_calculator.py` contains a failing test for `add(2, 3) == 5`.
- `demo_project/calculator.py` contains the intentional bug.

The assistant should:

1. Inspect the relevant demo files.
2. Run the configured test command.
3. Detect the failing behavior.
4. Explain the minimal fix.
5. Apply a safe partial edit to `demo_project/calculator.py`.
6. Run the tests again.
7. Report the final test result and summarize the change.

The demo passes when:

- The assistant fixes only the intended bug.
- The final test run passes.
- The terminal output shows safe command handling.
- Long outputs, if any, are summarized before being reused as context.
- The final response clearly states what changed, why, and how it was verified.
