# Live Demo Script

Use this script during the VG presentation. It is honest about scope: this is a **school-sized** terminal assistant, not a full Claude Code replacement.

**Recommended path:** run the **deterministic demo** (no API key, no network, repeatable). For a hands-on feel, use **`personal-dev-assistant chat`**. Real `MainAgent` + `SubAgentRunner` architecture exists in code and tests; interactive mode is an MVP without free-form LLM chat.

Estimated time: **8–12 minutes**.

---

## 1. Short pitch (30 seconds)

> Personal Dev Assistant is a small terminal coding assistant for local projects. It inspects files, runs safe bash commands, makes focused edits, coordinates sub-agents, and keeps context and token usage under control. For the live demo I use a deterministic workflow on a tiny Python project with an intentional bug — no API key required.

---

## 2. Problem it solves

- Developers need help in a **local repo** without blindly running risky commands or flooding the LLM with raw logs.
- A course-sized assistant should show: **safe tools**, **stepwise workflow**, **multi-agent coordination**, **context compaction**, and **budget awareness**.
- This project proves those ideas on `demo_project/`: find a failing test, inspect code, apply one minimal fix, verify with pytest.

---

## 3. Architecture overview (1 minute)

Point to `docs/architecture.md` or sketch:

```text
User → Main Agent → (Sub-agents | Tools) → Safety Checker
                         ↓
              Context compaction + Token budget
```

**Say briefly:**

- **Main agent** — decides tools, sub-agents, or finish.
- **Sub-agents** — `planner`, `explorer`, `coder`, `reviewer` (sequential today).
- **Tools** — `list_project_files`, `read_file`, `bash`, `partial_edit`.
- **Safety** — blocks destructive commands and sensitive paths before execution.
- **Context** — compacts long tool/sub-agent output before the next step.
- **Token monitor** — tracks usage, warnings, hard cap (used by LLM client in tests).

---

## 4. VG requirements mapping (1 minute)

| Requirement | Where to show it |
| --- | --- |
| Multi-agent | `MainAgent` + `SubAgentRunner`; mention tests in `tests/test_subagents.py` |
| Context engineering | Compaction in tools/demo observations; `docs/context-strategy.md` |
| Token/cost monitoring | `TokenBudgetMonitor`; tests in `tests/test_token_budget.py` |
| Harmful tool-call protection | Safety checker; demo uses only allowed commands |
| Bash execution | Demo runs `pytest` and `python -m compileall -f` via `bash` tool |
| Partial file editing | Demo fixes one line in `demo_project/calculator.py` |
| Config + secrets | `config.yaml` + `.env.example` (secrets never in config) |
| Agent continue vs yield | Main agent loop; deterministic demo mirrors the workflow |
| Packaged setup | README + Docker |
| Live demo proof | Deterministic demo below |

---

## 5. Pre-demo checklist

- [ ] Repo cloned; terminal at project root
- [ ] **Either** local venv activated **or** Docker image built
- [ ] `demo_project/calculator.py` contains `return a - b` (buggy state) — demo restores automatically if already fixed
- [ ] No API key needed for deterministic demo
- [ ] Optional: open `docs/requirements.md`, `docs/safety-policy.md`, `config.yaml`

---

## 6. Terminal commands

### Option A — Local (venv)

```bash
cd personal-dev-assistant
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Run tests (credibility):**

```bash
python -m pytest tests
```

Expected: **153 passed**.

**Run deterministic demo (main presentation):**

```bash
python -m personal_dev_assistant.demo.runner
```

Or:

```bash
personal-dev-assistant-demo
```

**Re-run demo (restores bug by default):**

```bash
python -m personal_dev_assistant.demo.runner
```

**Skip restore (already fixed):**

```bash
python -m personal_dev_assistant.demo.runner --no-restore-initial-state
```

### Option B — Docker (no local venv)

```bash
cd personal-dev-assistant
docker build -t personal-dev-assistant .
```

**Run tests:**

```bash
docker run --rm personal-dev-assistant pytest tests
```

Or:

```bash
docker compose build
docker compose run --rm test
```

**Run deterministic demo:**

```bash
docker run --rm personal-dev-assistant
```

Or:

```bash
docker compose run --rm demo
```

No `OPENAI_API_KEY` required for any of the above demo commands.

**Optional — LLM env at runtime only (not for live demo):**

```bash
docker run --rm --env-file .env personal-dev-assistant personal-dev-assistant "Your task"
```

---

## 7. What to point out during the demo

While the demo runs, narrate each step:

1. **List project files** — controlled inspection, not raw shell `find`.
2. **Read test + calculator** — bounded file reads; blocked paths like `.env` would be rejected.
3. **Run tests before fix** — safe `pytest demo_project`; tests **fail** (`add(2, 3)` returns `-1`).
4. **Partial edit** — one exact replacement: `return a - b` → `return a + b`; not a full file rewrite.
5. **Refresh bytecode** — safe `python -m compileall -f` via bash (no direct `__pycache__` deletion).
6. **Run tests after fix** — tests **pass**.
7. **Summary** — before/after result in plain language.

**Optional 30-second digression:** show `config.yaml` (non-secret settings) and `.env.example` (API key only at runtime).

**Do not claim:** the live demo is LLM-driven. Say: *"The same tools and safety rules are what the main agent uses; agent/sub-agent logic is tested separately."*

---

## 8. Expected demo output summary

Default output is **presentation-friendly** (numbered steps, markers, mini diff, VG checklist). Use `--plain` for the original simple format.

You should see output similar to:

```text
==============================================================================
           Personal Dev Assistant — Deterministic Live Demo
==============================================================================

[STEP] Goal: find and fix the failing test in demo_project/
[STEP] Uses safe tools only — no API key required.

1. [STEP] List project files
   Inspect the project structure without reading every file's full content.
   [OK] Listed ...

...

Test status
   Before fix: [FAIL] tests failed
   After fix:  [OK] tests passed

One-line fix applied
- return a - b
+ return a + b

VG feature checklist shown in this demo
   [x] Safe bash execution (pytest + compileall)
   ...

==============================================================================
                                Demo SUCCESS
==============================================================================
```

Plain output (`--plain`):

```text
Personal Dev Assistant demo completed.
Before fix: tests failed.
...
Steps:
- list_project_files: ok — ...
```

Exit code **0** = success.

---

## 8b. Optional interactive terminal mode

```bash
personal-dev-assistant chat
```

Suggested flow:

```text
> read demo_project/calculator.py
> test
> fix
> tokens
> quit
```

Say clearly: **deterministic command-driven MVP**, not free-form LLM chat. The `fix` command shows MAIN AGENT → PLANNER → EXPLORER → CODER → REVIEWER → PARTIAL_EDIT → BASH with real safe tools.

---

## 9. Strengths

- **Clear scope** — small, understandable demo project.
- **Safety first** — commands and paths checked before tools run.
- **Honest architecture** — main agent, sub-agents, tools, context, budget are separate layers.
- **Tested** — 170 automated tests including safety, tools, agents, sub-agents, and interactive mode.
- **Repeatable** — deterministic demo; Docker for another machine; no API key for demo.
- **Documentation** — requirements, architecture, safety, dev log, README.

---

## 10. Weaknesses / limitations (say these proactively)

- **Not a production Claude Code replacement** — limited to small, local workflows.
- **Deterministic demo and chat are scripted** — safest for presentation; not free-form LLM sessions.
- **Interactive chat is an MVP** — real `MainAgent`/`SubAgentRunner` with LLM exist in library code + tests.
- **Sub-agents are sequential** — no parallel execution.
- **Small demo only** — one intentional bug, one-line fix; not large refactors.
- **LLM demo needs API key + network** — separated via env vars; not required for VG live demo.

---

## 11. Likely teacher questions and short answers

**Q: Is this really multi-agent?**  
A: Yes. `MainAgent` can delegate to `planner`, `explorer`, `coder`, and `reviewer` via `ACTION: subagents`. Sub-agents return compact `AgentResult` objects. Covered by integration tests; live demo focuses on the tool workflow.

**Q: How do you prevent harmful commands?**  
A: A safety checker classifies commands as safe, risky (needs confirmation), or blocked. Tools call it before execution. Destructive commands like `rm -rf` and paths like `.env` are blocked.

**Q: How do you handle long tool output?**  
A: Deterministic compaction truncates long output and keeps start/end plus metadata. Sub-agent summaries have a separate size limit in config.

**Q: How is token/cost monitoring done?**  
A: `TokenBudgetMonitor` tracks approximate tokens per LLM call, warns near threshold, and stops at hard cap. Wired through `ChatClient`; tested with mock client.

**Q: Why not demo the LLM live?**  
A: Deterministic demo is reliable offline and needs no API key. LLM behavior is tested with scripted clients; secrets stay in env vars, not in the repo or Docker image.

**Q: Can someone else run it easily?**  
A: Yes. README has venv steps; Docker runs tests and demo with documented commands. No secrets baked into the image.

**Q: What would you improve next?**  
A: Wire interactive CLI to `MainAgent`, optional live LLM demo, parallel sub-agents, and broader project support — outside current scope.

---

## 12. Suggested presentation order

1. Pitch + problem (30 s)
2. Architecture diagram (1 min)
3. VG requirements table — quick scan (1 min)
4. `pytest tests` — 153 passed (1 min)
5. Deterministic demo — local or Docker (3–4 min)
6. Strengths + limitations — honest close (1 min)
7. Q&A — use section 11

Good luck.
