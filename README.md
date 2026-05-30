# Personal Dev Assistant

A small, terminal-based AI coding assistant built for a VG course assignment. The goal is a **school-sized** assistant inspired by tools like Claude Code or Codex CLI — not a full replacement for them.

Personal Dev Assistant helps with a **local code project** by inspecting files, running safe shell commands, making small focused edits, coordinating sub-agents, and keeping context and token usage under control.

## What it does

At a high level, the assistant:

- Reads and lists project files through safety-checked tools.
- Runs approved bash commands (for example `pytest`) inside the project root.
- Applies small, exact-match partial edits instead of rewriting whole files.
- Uses a main agent loop that chooses tools, sub-agents, or a final answer.
- Compacts long tool and sub-agent output before reusing it in context.
- Tracks approximate token usage, warnings, and a hard budget cap.
- Includes a **deterministic demo** that proves the tool workflow without calling a real LLM.

The included demo project (`demo_project/`) contains an intentional bug in `calculator.py` and a failing test that the demo fixes step by step.

## Current feature status

| Area | Status |
| --- | --- |
| Config loading (`config.yaml` + env overrides) | Implemented |
| Safety checker (commands + blocked paths) | Implemented |
| Tools: `read_file`, `list_project_files`, `bash`, `partial_edit` | Implemented |
| Context/output compaction | Implemented |
| Token budget monitor | Implemented |
| LLM client (mock + OpenAI-compatible) | Implemented |
| Main agent loop (`MainAgent`) | Implemented |
| Sub-agent orchestration (`planner`, `explorer`, `coder`, `reviewer`) | Implemented (sequential) |
| Deterministic demo runner | Implemented |
| Interactive CLI wired to full agent loop | **Placeholder only** |
| Docker packaging | **Not yet** |

**153 tests** currently pass.

For implementation history, see [`docs/development-log.md`](docs/development-log.md).

## VG requirements mapping

| Requirement | How this project addresses it | Status |
| --- | --- | --- |
| Multi-agent system | `MainAgent` can run sub-agents via `ACTION: subagents` and use compact `AgentResult` output | Implemented |
| Context engineering | Long tool/sub-agent output is compacted before returning to the main agent | Implemented |
| Token/cost monitoring | `TokenBudgetMonitor` tracks usage, warnings, and hard cap via `ChatClient` | Implemented |
| Protection against harmful tool calls | Safety checker blocks risky/destructive commands and blocked paths before tools run | Implemented |
| Bash command execution | `bash` tool runs approved commands with timeout and output limits | Implemented |
| Partial file editing | `partial_edit` requires a single exact match and respects safety rules | Implemented |
| Config file | Non-secret runtime settings in `config.yaml` | Implemented |
| Secrets via environment variables | API keys and overrides come from env vars (see `.env.example`) | Implemented |
| Baseline agent loop (continue vs yield) | Main agent continues with tools/sub-agents or finishes with a final response | Implemented |
| Packaged/easy setup | Local venv + README setup; Docker not added yet | Partly present |
| Live demo proof | Deterministic demo runner on `demo_project/` | Implemented |

More detail: [`docs/requirements.md`](docs/requirements.md), [`docs/demo-plan.md`](docs/demo-plan.md), [`docs/technical-spec.md`](docs/technical-spec.md).

## Requirements

- **Python 3.12+**
- A terminal
- For the deterministic demo: **no API key required**
- For real LLM-backed agent runs: an OpenAI-compatible API key in the environment

## Setup

Clone the repository and work from the project root:

```bash
git clone <your-repo-url>
cd personal-dev-assistant
```

### 1. Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

On Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install the package and dev dependencies

```bash
pip install -e ".[dev]"
```

This installs the project in editable mode and adds `pytest` for development.

### 3. Optional: configure environment variables

Copy the example file and edit it locally (do **not** commit real secrets):

```bash
cp .env.example .env
```

Load variables into your shell when needed, for example:

```bash
set -a
source .env
set +a
```

The deterministic demo does **not** need `OPENAI_API_KEY`. Real LLM usage is kept separate through environment variables so secrets never belong in `config.yaml`.

## Configuration

Non-secret settings live in [`config.yaml`](config.yaml):

| Section | Purpose |
| --- | --- |
| `model` | Default model name for LLM-backed runs |
| `token_budget` | Session token limit, warning threshold, hard cap |
| `safety` | Risky-command confirmation and whether file edits are allowed |
| `context` | Max chars for tool observations and sub-agent summaries |
| `tools` | Command timeout and test command (`pytest`) |

Environment variables can override some values:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | API key for OpenAI-compatible LLM calls |
| `MODEL` | Overrides `model` in `config.yaml` |
| `TOKEN_BUDGET` | Overrides `token_budget.max_tokens` |
| `REQUIRE_COMMAND_APPROVAL` | Overrides `safety.require_confirmation_for_risky_commands` |
| `MAX_TOOL_OUTPUT_CHARS` | Overrides `context.max_observation_chars` |

See [`.env.example`](.env.example) for the full list.

## Run tests

From the project root with the venv activated:

```bash
python -m pytest tests
```

Or, if installed:

```bash
pytest tests
```

Expected result: **153 passed**.

## Run the deterministic demo

The demo proves the end-to-end tool workflow on `demo_project/` **without a real API key**. It:

1. Lists project files
2. Reads the calculator and test files
3. Runs `pytest demo_project` (tests fail before the fix)
4. Applies the intended one-line fix in `demo_project/calculator.py`
5. Refreshes bytecode through a safe `bash` command (`python -m compileall -f ...`)
6. Runs tests again and prints a before/after summary

### Run once

From the repo root:

```bash
python -m personal_dev_assistant.demo.runner
```

Or, after install:

```bash
personal-dev-assistant-demo
```

Optional flags:

```bash
python -m personal_dev_assistant.demo.runner --project-root .
python -m personal_dev_assistant.demo.runner --config config.yaml
```

### Reset and re-run the demo

The demo is designed to be repeatable for presentations.

**Default behavior:** if `demo_project/calculator.py` is already fixed, the demo restores the intentional bug first, then runs the full workflow again.

To skip restore and only inspect an already-fixed project:

```bash
python -m personal_dev_assistant.demo.runner --no-restore-initial-state
```

**Manual reset:** set the calculator back to the buggy line:

```python
return a - b
```

Then run the demo again normally.

**If the demo was already run:** the file may currently contain `return a + b`. Running the demo again with default settings restores the bug and re-runs the fix automatically.

## Project layout

```text
personal-dev-assistant/
├── config.yaml              # Non-secret runtime settings
├── .env.example             # Secret/env override template
├── demo_project/            # Small Python demo with intentional bug
├── docs/                    # Requirements, specs, demo plan, dev log
├── prompts/                 # Agent prompt files
├── src/personal_dev_assistant/
│   ├── agents/              # Main agent + sub-agent runner
│   ├── demo/                # Deterministic demo runner
│   ├── tools/               # read_file, bash, partial_edit, ...
│   ├── safety/              # Command/path safety checks
│   ├── context/             # Output compaction
│   ├── budget/              # Token budget monitor
│   └── llm/                 # Chat client layer
└── tests/                   # Unit and integration tests
```

## Current limitations

Be honest about scope — this is a course-sized assistant, not production tooling.

- **Not a full Claude Code replacement.** It targets a small, demo-friendly workflow.
- **CLI is still a placeholder** for LLM-backed interactive use; the deterministic demo is the polished presentation path today.
- **Sub-agents run sequentially**, not in parallel.
- **No Docker image yet.** Setup is local venv + documented commands.
- **Demo is scripted**, not LLM-driven. The main agent loop exists in code/tests but is not the default user-facing CLI yet.
- **Small project scope.** It is meant for `demo_project/`-scale tasks, not large refactors.

## Suggested VG presentation flow

1. Show the repo structure and `docs/requirements.md`.
2. Run `pytest tests` to show automated coverage.
3. Run `python -m personal_dev_assistant.demo.runner` to show:
   - safe bash execution
   - partial file editing
   - before/after test verification
   - no API key required
4. Optionally mention that LLM-backed agent/sub-agent behavior is implemented in code and covered by tests, with secrets loaded from env vars when used.

## Further reading

- [`docs/requirements.md`](docs/requirements.md) — VG requirement mapping
- [`docs/demo-plan.md`](docs/demo-plan.md) — intended demo narrative
- [`docs/technical-spec.md`](docs/technical-spec.md) — tool and config contracts
- [`docs/development-log.md`](docs/development-log.md) — build history
- [`docs/safety-policy.md`](docs/safety-policy.md) — blocked commands and paths
