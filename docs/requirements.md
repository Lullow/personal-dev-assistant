# Requirements

## 1. Overview

This document maps each required VG assignment feature to a concrete feature in Personal Dev Assistant and explains how it is demonstrated today.

The project is intentionally small and realistic for a course assignment. It shows multi-agent coordination, context handling, safe tool use, command execution, partial file editing, configuration, token monitoring, and a repeatable demo — without claiming to be a full Claude Code replacement.

**Current test status:** 153 tests pass (`python -m pytest tests`).

For live presentation steps, see [`demo-script.md`](demo-script.md).

## 2. Requirements checklist

| Requirement | Implemented feature | How it is demonstrated | Status |
| --- | --- | --- | --- |
| Multi-agent system: main agent can start sub-agents and use their results | `MainAgent` + `SubAgentRunner` with roles `planner`, `explorer`, `coder`, and `reviewer`. Sub-agents load prompt files, call `ChatClient`, and return compact `AgentResult` objects. | Integration tests in `tests/test_subagents.py` and `tests/test_main_agent.py`. Main agent delegates via `ACTION: subagents` / `ROLES:`. | **Implemented with limitation** — sub-agents run **sequentially**, not in true parallel. |
| Advanced context engineering: long tool outputs or sub-agent outputs are summarized before being added to active context | Deterministic output compaction in `context/compaction.py`. Tool observations and sub-agent summaries are compacted before returning to the main agent. | Long bash/file output is truncated with preserved start/end and metadata. Sub-agent results use `max_subagent_summary_chars`. Covered by `tests/test_context_compaction.py` and demo observations. | **Implemented with limitation** — compaction is rule-based, not LLM summarization. |
| Token/cost monitoring: real-time tracking, warnings and hard-cap | `TokenBudgetMonitor` integrated through `ChatClient.complete()`. Tracks approximate tokens, warnings, and hard cap from `config.yaml`. | Tests in `tests/test_token_budget.py` and `tests/test_llm_client.py`. Hard cap blocks further LLM calls before the model runs. | **Implemented** |
| Protection against harmful tool calls: safety checker for risky bash commands | Command and path safety checks in `safety/checker.py`. Used by `bash`, `read_file`, `list_project_files`, and `partial_edit`. | Tests in `tests/test_safety.py`. Demo only uses allowlisted commands (`pytest`, `python -m compileall -f`). Destructive commands such as `rm -rf` are blocked. | **Implemented** |
| Bash command execution | Safe `bash` tool with timeout, cwd restriction, safety gating, and output compaction. | Deterministic demo runs `pytest demo_project` before and after the fix. Tests in `tests/test_bash_tool.py`. | **Implemented** |
| Partial file editing | `partial_edit` tool with exact-once match, path safety, and edit guards. | Demo changes one line in `demo_project/calculator.py` (`return a - b` → `return a + b`). Tests in `tests/test_partial_edit.py`. | **Implemented** |
| Packaged/easy setup: Docker or clear setup instructions | `README.md`, `Dockerfile`, `.dockerignore`, and `docker-compose.yml`. Local venv setup documented. | Another person can run tests and demo locally or in Docker. See section 4 for commands. | **Implemented** |
| Config file for configuration | Non-secret runtime settings in `config.yaml` (model, token budget, safety, context limits, tool timeout/test command). | Loaded by config layer; overrides documented in README. Tests in `tests/test_config.py`. | **Implemented** |
| Secrets through environment variables | Secrets and overrides via env vars; template in `.env.example`. Never stored in `config.yaml` or Docker image. | `OPENAI_API_KEY`, `MODEL`, `TOKEN_BUDGET`, etc. Optional at runtime for LLM-backed use. Deterministic demo needs no API key. | **Implemented** |
| Baseline ASSN-2 behavior: the agent decides whether to continue with more tool calls or yield back to the user | `MainAgent` loop chooses tools, sub-agents, or `finish`; respects `max_steps` and budget hard cap. | Covered by `tests/test_main_agent.py`. Deterministic demo mirrors the same stepwise inspect → test → edit → verify workflow. | **Implemented with limitation** — interactive CLI (`personal-dev-assistant`) is still a **placeholder**; full loop is in library code and tests. |

### Related items not in the core checklist

| Area | Status | Notes |
| --- | --- | --- |
| Interactive LLM-backed CLI | **Partly implemented** | `MainAgent`, `ChatClient`, and sub-agents exist; default CLI does not yet run the full loop interactively. |
| Parallel sub-agents | **Future improvement** | Current `SubAgentRunner` runs roles one after another. |
| LLM-based context summarization | **Future improvement** | Current compaction is deterministic truncation, not model-generated summaries. |
| `test_runner` dedicated tool | **Future improvement** | Tests are run through the `bash` tool with `pytest`. |

## 3. Scope boundaries

The VG version stays intentionally small.

- It is **not** a full Claude Code replacement.
- It does **not** support every programming language deeply.
- It does **not** automatically edit large codebases.
- It does **not** attempt large refactors or complex architecture changes.
- It focuses on a **small, reliable demo** on `demo_project/` first.

## 4. Demo proof

The live proof uses a small Python project with an intentional bug in `demo_project/calculator.py` and a failing test in `demo_project/test_calculator.py`.

### Deterministic demo runner

The recommended presentation path is the **deterministic demo runner** (`src/personal_dev_assistant/demo/runner.py`). It:

1. Lists project files (`list_project_files`).
2. Reads the test and calculator files (`read_file`).
3. Runs tests before the fix (`bash` → `pytest demo_project`) — tests fail.
4. Applies the intended one-line fix (`partial_edit`).
5. Refreshes bytecode through a safe bash command (`python -m compileall -f ...`).
6. Runs tests again — tests pass.
7. Prints a before/after summary.

**No real API key is required.** The demo uses the same safe tools and safety rules as the agent layer.

**Local commands:**

```bash
python -m pytest tests
python -m personal_dev_assistant.demo.runner
# or: personal-dev-assistant-demo
```

**Docker commands:**

```bash
docker build -t personal-dev-assistant .
docker run --rm personal-dev-assistant pytest tests
docker run --rm personal-dev-assistant
# or:
docker compose build
docker compose run --rm test
docker compose run --rm demo
```

The demo is **repeatable**: by default it can restore the intentional bug before re-running the fix. Use `--no-restore-initial-state` to skip restore.

### What the demo proves

- Controlled tool use on a local project.
- Safe bash execution and verification with pytest.
- Partial file editing with a minimal, exact change.
- Output compaction and clear terminal summary.
- Offline, presentation-friendly workflow without LLM dependency.

### What the demo does not prove on its own

- Free-form LLM-driven reasoning in a live session.
- Parallel sub-agent execution.
- Full interactive CLI experience.

Those behaviors are implemented and tested separately (`tests/test_main_agent.py`, `tests/test_subagents.py`, `tests/test_llm_client.py`). Mention them during presentation; use the deterministic demo for the reliable live run.

For a step-by-step presentation script, see [`demo-script.md`](demo-script.md).
