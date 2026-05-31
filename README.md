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
| Interactive terminal mode (`chat`) | Implemented (deterministic MVP, no API key) |
| Experimental LLM agent mode (`run-agent --llm`) | Implemented (optional, restricted, requires API key; safe `propose_edit` by default) |
| LLM-backed free-form chat | **Not implemented** |
| Docker packaging | Implemented |

**192 tests** currently pass.

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
| Packaged/easy setup | Local venv + README + Docker | Implemented |
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

## Docker setup

Docker provides a reproducible way to run tests and the deterministic demo without setting up a local virtual environment. **No API key is required** for the demo image default command.

### Build the image

From the project root:

```bash
docker build -t personal-dev-assistant .
```

Or with Compose:

```bash
docker compose build
```

Secrets are **not** baked into the image. Do not copy `.env` into the Dockerfile.

### Run tests in Docker

```bash
docker run --rm personal-dev-assistant pytest tests
```

Or:

```bash
docker compose run --rm test
```

Expected result: **153 passed**.

### Run the deterministic demo in Docker

```bash
docker run --rm personal-dev-assistant
```

Or:

```bash
docker compose run --rm demo
```

The default container command runs `personal-dev-assistant-demo` against `/app`. No `OPENAI_API_KEY` is needed.

To re-run with restore (default demo behavior inside the container):

```bash
docker compose run --rm demo
```

Each container run starts from the image copy of `demo_project/`. The demo restores the intentional bug when needed, then applies the fix again.

### Optional environment variables in Docker

For future LLM-backed runs, pass secrets at **runtime** only:

```bash
docker run --rm --env-file .env personal-dev-assistant personal-dev-assistant "Your task"
```

Or with Compose:

```bash
docker compose run --rm --env-file .env demo
```

Only create `.env` locally from [`.env.example`](.env.example). Never commit real API keys.

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
python -m personal_dev_assistant.demo.runner --plain
```

By default the demo prints **presentation-friendly output** with numbered steps, `[OK]` / `[FAIL]` markers, a mini diff, and a VG feature checklist. Use `--plain` for the original simple text output.

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

## Interactive terminal mode

Start a deterministic command-driven assistant session. This is **not** a free-form LLM chat — no API key required.

```bash
personal-dev-assistant chat
# or
personal-dev-assistant interactive
# or
python -m personal_dev_assistant.cli chat
```

On start:

```text
Personal Dev Assistant
Deterministic interactive mode — not a free-form LLM session. No API key required.
Ready when you are.
```

| Command | Action |
| --- | --- |
| `help` | Show available commands |
| `exit` / `quit` | Leave interactive mode |
| `list` | List project files safely |
| `read <path>` | Read a file (tracks last read path) |
| `review` | Review demo_project or last read file |
| `test` | Run `pytest demo_project` via safe bash tool |
| `fix` | Scripted MAIN AGENT → PLANNER → EXPLORER → CODER → REVIEWER → PARTIAL_EDIT → BASH |
| `tokens` | Show token budget status |

Example:

```text
> read demo_project/calculator.py
> test
> fix
> tokens
> quit
```

## Experimental LLM agent mode (optional)

This is **not** the primary demo path. Use the deterministic demo or `chat` mode for presentations without an API key.

Requires `OPENAI_API_KEY` in the environment:

```bash
export OPENAI_API_KEY=your-key-here
personal-dev-assistant run-agent "Inspect demo_project and run pytest" --llm
```

What it does:

- Uses the real `MainAgent` loop and OpenAI-compatible `ChatClient`
- Respects max steps, token hard cap, safety checks, and existing tools
- Allows: `read_file`, `list_project_files`, `bash`, `propose_edit`, `finish`
- **Does not allow** direct LLM-driven `partial_edit`, `write_file`, or `subagents`
- Stops safely if the model returns an invalid action format or a disallowed action
- Does not auto-execute risky commands (they are blocked by the safety layer)

### Safe proposed edits (default)

In experimental LLM mode, the model may propose a change with `ACTION: propose_edit` instead of editing files directly. By default, proposals are **validated but not applied** — the file on disk stays unchanged.

The model must use this strict format:

```text
ACTION: propose_edit
PATH: relative/path.py
OLD_TEXT:
exact old text
NEW_TEXT:
exact new text
REASON:
short reason
```

When a proposal is received, the system:

- validates the path (same rules as `partial_edit`)
- requires non-empty `OLD_TEXT` that appears exactly once in the file
- rejects no-op edits, blocked paths, and binary/non-UTF-8 files
- returns a compact observation with a mini diff when valid
- tells you how to apply the edit safely if you choose to

**By default, nothing is written.** To actually apply validated proposals, opt in explicitly:

```bash
personal-dev-assistant run-agent "Fix the calculator bug" --llm --apply-proposed-edits
```

With `--apply-proposed-edits`, valid proposals are applied through the existing `partial_edit` tool (same safety checks; no bypass). Without the flag, you can review the mini diff in the agent output first.

Example output starts with:

```text
*** EXPERIMENTAL LLM AGENT MODE ***
Optional live LLM path — not the primary demo route.
Proposed edits are validated by default and not applied unless --apply-proposed-edits is set.
```

## Project layout

```text
personal-dev-assistant/
├── config.yaml              # Non-secret runtime settings
├── .env.example             # Secret/env override template
├── Dockerfile               # Container image for tests and demo
├── docker-compose.yml       # Convenience commands for test/demo
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
- **Interactive mode is deterministic** — scripted commands and agent-style labels, not free-form LLM chat.
- **Sub-agents run sequentially**, not in parallel.
- **Experimental LLM mode is restricted** — read/list/bash/propose_edit/finish; direct edits require `--apply-proposed-edits`.
- **Demo and chat remain the primary presentation paths** without an API key.
- **Small project scope.** It is meant for `demo_project/`-scale tasks, not large refactors.

## Suggested VG presentation flow

1. Show the repo structure and `docs/requirements.md`.
2. Run `pytest tests` (locally or with `docker compose run --rm test`).
3. Run `python -m personal_dev_assistant.demo.runner` or `docker compose run --rm demo` to show:
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
