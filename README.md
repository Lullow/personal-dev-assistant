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
| Interactive terminal mode (`chat`) — **Interactive Assistant v.2** | Implemented (stateful session, deterministic review, pending edits; no API key) |
| Experimental LLM agent mode (`run-agent --llm`) | Implemented (optional, restricted, requires API key; trace-grounded guards; safe `propose_edit` by default) |
| LLM-backed free-form chat | **Not implemented** |
| Docker packaging | Implemented |

**294 tests** currently pass.

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

Expected result: **294 passed**.

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
| `OPENAI_API_KEY` | API key for OpenAI-compatible LLM calls (use your [OpenRouter](https://openrouter.ai/) key for experimental mode) |
| `OPENAI_BASE_URL` | API base URL (set to `https://openrouter.ai/api/v1` for OpenRouter) |
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

Expected result: **294 passed**.

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

## Interactive Assistant v.2 (primary demo path)

**Recommended presentation path:** `personal-dev-assistant chat` — no API key required.

Start a stateful, command-driven terminal session:

```bash
personal-dev-assistant chat
# or
personal-dev-assistant interactive
```

On start you see a short welcome and a hint to type `help`.

### Recommended demo flow

```text
> open demo_project/calculator.py
> review it
> fix it
> apply
> run tests
> show token usage
> compact context
> exit
```

After the demo, restore `demo_project/calculator.py` to `return a - b` if you want to repeat the flow.

### What v.2 demonstrates

| Capability | How it works |
| --- | --- |
| Stateful session | `InteractiveSession` tracks current file, review, pending edit, tests, and action history |
| Current file | `open <path>` reads safely and sets the active file |
| Multi-agent-style review | Deterministic **code reviewer**, **test reasoning agent**, and **fix planner**; main assistant combines results |
| Pending proposed edit | `fix it` validates via `propose_edit` (no disk write); shows **mini diff** |
| Explicit approval | `apply` writes only after your command, through safe **`partial_edit`** |
| Reject | `reject` clears pending edit without changing files |
| Safe tests | `run tests` runs `pytest demo_project` via the bash tool |
| Token display | `show token usage` shows session budget / local estimate |
| Context compaction | `compact context` trims history while preserving file, pending edit, and review summary |

Natural phrases work with deterministic parsing (not LLM), for example:
`show current file`, `can you review it`, `fix the bug`, `run pytest`, `budget`.

| Command | Action |
| --- | --- |
| `help` | Show available commands |
| `exit` / `quit` | Leave interactive mode |
| `list` | List project files safely |
| `open <path>` / `read <path>` | Open a file into the current session |
| `show current file` | Show current path and content preview |
| `review` | Review current file (or demo_project if none open) |
| `fix` / `fix it` | Create pending proposed edit + mini diff (no file change) |
| `apply` | Apply pending edit via safe `partial_edit` |
| `reject` | Clear pending edit |
| `test` / `run tests` | Run `pytest demo_project` |
| `tokens` / `show token usage` | Show token budget status |
| `compact context` | Compact session history |

Implementation lives under `src/personal_dev_assistant/interactive/` (`assistant.py`, `session.py`, `review.py`, `parsing.py`).

### Deterministic demo runner (alternative path)

The one-shot demo runner remains available for scripted presentations:

```bash
python -m personal_dev_assistant.demo.runner
# or
personal-dev-assistant-demo
```

It auto-runs list → read → pytest → fix → compileall → pytest with no user input. Use **chat v.2** when you want to show session state, user approval, and subagent-style review step by step.

## Experimental LLM agent mode (optional)

This is **not** the primary demo path. Use **`personal-dev-assistant chat`** or the deterministic demo runner for presentations without an API key.

Requires `OPENAI_API_KEY` (and OpenRouter base URL) in the environment. Default model in [`config.yaml`](config.yaml) is `openai/gpt-5.1-codex-mini`.

Create `.env` from [`.env.example`](.env.example):

```bash
OPENAI_API_KEY=your-openrouter-key-here
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

```bash
export OPENAI_API_KEY=your-openrouter-key-here
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
personal-dev-assistant run-agent "Inspect demo_project, run pytest, and propose a fix for the failing test" --llm
```

What it does:

- Uses the real `MainAgent` loop and OpenAI-compatible `ChatClient`
- Respects max steps, token hard cap, safety checks, and existing tools
- Allows: `read_file`, `list_project_files`, `bash`, `propose_edit`, `finish`
- **Does not allow** direct LLM-driven `partial_edit`, `write_file`, or `subagents`
- Stops safely if the model returns an invalid action format or a disallowed action
- Does not auto-execute risky commands (they are blocked by the safety layer)
- **Trace-grounded guards** — final summaries cannot claim test results without `bash`, or proposed-edit/reviewer status without `propose_edit`; `propose_edit` requires prior `read_file` on the target path

### Safe proposed edits (default)

In experimental LLM mode, the model may propose a change with `ACTION: propose_edit` instead of editing files directly. By default, proposals are **validated but not applied** — the file on disk stays unchanged.

**Primary demo:** use `personal-dev-assistant chat` (Interactive v.2) or `python -m personal_dev_assistant.demo.runner` (no API key). Experimental `run-agent` is for showing a real LLM loop when you have a key.

#### Review only (default)

```bash
export OPENAI_API_KEY=your-openrouter-key-here
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
personal-dev-assistant run-agent "Inspect demo_project, run pytest, and propose a fix" --llm
```

Terminal output includes a step-by-step **AGENT TRACE** (`[LLM DECISION]`, `[TOOL RESULT]`, `[SAFETY]`, `[REVIEWER]`), run summary, token budget, and **FINAL ANSWER**. Files are not modified.

#### Apply low/medium-risk proposals

```bash
personal-dev-assistant run-agent "Fix the calculator bug in demo_project" --llm --apply-proposed-edits
```

Same trace format as review-only mode.

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
- runs a deterministic reviewer gate (`risk_level`: low / medium / high)
- requires non-empty `OLD_TEXT` that appears exactly once in the file
- rejects no-op edits, blocked paths, and binary/non-UTF-8 files
- returns a compact observation with `reviewer_summary`, `recommendation`, and a mini diff when valid
- tells you how to apply the edit safely if you choose to

**By default, nothing is written.** With `--apply-proposed-edits`, only **low** and **medium** risk proposals are applied through the existing `partial_edit` tool (same safety checks; no bypass). **High** risk proposals are reviewed but never auto-applied. Direct LLM `partial_edit` remains blocked.

Example output starts with:

```text
======================================================================
*** EXPERIMENTAL LLM AGENT MODE ***
Optional live LLM path — NOT the primary demo route.
======================================================================
--- Step 1 ---
  [LLM DECISION] ACTION: list_project_files
  [TOOL RESULT] ...
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
│   ├── interactive/       # Interactive Assistant v.2 (chat session)
│   ├── tools/               # read_file, bash, partial_edit, propose_edit, ...
│   ├── safety/              # Command/path safety checks
│   ├── context/             # Output compaction
│   ├── budget/              # Token budget monitor
│   └── llm/                 # Chat client layer
└── tests/                   # Unit and integration tests
```

## Current limitations

Be honest about scope — this is a course-sized assistant, not production tooling.

- **Not a full Claude Code replacement.** It targets a small, demo-friendly workflow.
- **Interactive v.2 is deterministic** — session state and subagent-style review are scripted; not free-form LLM chat.
- **Sub-agents run sequentially**, not in parallel (in `MainAgent`; chat uses deterministic review subagents).
- **Experimental LLM mode is restricted** — read/list/bash/propose_edit/finish; direct `partial_edit` blocked; trace-grounded final guards; apply only via `--apply-proposed-edits` for low/medium risk.
- **Chat and deterministic demo are the primary presentation paths** — no API key required.
- **Small project scope.** It is meant for `demo_project/`-scale tasks, not large refactors.

## Suggested VG presentation flow

1. Show the repo structure and `docs/requirements.md`.
2. Run `pytest tests` (locally or with `docker compose run --rm test`) — **294 passed**.
3. Run **`personal-dev-assistant chat`** (primary path) with the v.2 flow:
   - open → review → fix → apply → run tests → token usage → compact context
   - no API key; shows session state, subagents, pending edit, user approval, safety
4. Optionally run `python -m personal_dev_assistant.demo.runner` for the one-shot scripted demo.
5. Optionally mention experimental `run-agent --llm` (API key, trace output, reviewer gate) — not required for VG.

## Further reading

- [`docs/requirements.md`](docs/requirements.md) — VG requirement mapping
- [`docs/demo-plan.md`](docs/demo-plan.md) — intended demo narrative
- [`docs/technical-spec.md`](docs/technical-spec.md) — tool and config contracts
- [`docs/development-log.md`](docs/development-log.md) — build history
- [`docs/safety-policy.md`](docs/safety-policy.md) — blocked commands and paths
