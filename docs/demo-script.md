# Live Demo Script

Use this script during the VG presentation. It is honest about scope: this is a **school-sized** terminal assistant, not a full Claude Code replacement.

**Recommended path:** run **`personal-dev-assistant chat`** (Interactive Assistant v.2, no API key). Alternative: **deterministic demo runner** (one-shot script). Optional: **`run-agent --llm`** for experimental live LLM use with API key — not the primary demo route.

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

Expected: **294 passed**.

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

## 8b. Interactive Assistant v.2 (primary live demo)

**Start here for the VG presentation** — no API key required.

```bash
personal-dev-assistant chat
```

### Recommended v.2 flow

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

**Narrate while typing:**

1. **open** — safe read; sets current file in session state.
2. **review it** — main assistant delegates to deterministic **code reviewer**, **test reasoning agent**, and **fix planner**; explains `add()` subtracts instead of adds.
3. **fix it** — creates **pending proposed edit** + **mini diff**; file **not** changed yet (`propose_edit` validation + reviewer gate).
4. **apply** — user explicitly approves; **`partial_edit`** applies `return a - b` → `return a + b`.
5. **run tests** — safe `pytest demo_project`; tests pass.
6. **show token usage** — session budget / local estimate.
7. **compact context** — trims action history; keeps current file and pending-edit summary.

**Restore** `demo_project/calculator.py` to `return a - b` after the demo if you want to repeat.

Say clearly: **deterministic, stateful session** — not free-form LLM chat. Natural phrases map to the same safe commands.

### Alternative: one-shot deterministic demo

```bash
python -m personal_dev_assistant.demo.runner
```

Same bug/fix story without step-by-step user commands. Good backup if short on time.

### Optional: experimental LLM mode

```bash
export OPENAI_API_KEY=your-openrouter-key-here
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
personal-dev-assistant run-agent "Inspect demo_project, run pytest, and propose a fix for the failing test" --llm
```

Point out **AGENT TRACE**, trace-grounded guards (no false test/edit claims), and **reviewer gate**. Mention `--apply-proposed-edits` only for low/medium-risk apply demo. **High-risk edits stay blocked.** Not required for VG.

---

## 9. Strengths

- **Clear scope** — small, understandable demo project.
- **Safety first** — commands and paths checked before tools run.
- **Honest architecture** — main agent, sub-agents, tools, context, budget are separate layers.
- **Tested** — 294 automated tests including safety, tools, agents, interactive v.2, and experimental run-agent.
- **Repeatable** — deterministic demo; Docker for another machine; no API key for demo.
- **Documentation** — requirements, architecture, safety, dev log, README.

---

## 10. Weaknesses / limitations (say these proactively)

- **Not a production Claude Code replacement** — limited to small, local workflows.
- **Deterministic chat v.2 is the primary demo** — stateful session with pending edits and explicit `apply`; not free-form LLM.
- **Experimental LLM mode is optional** — requires API key; trace-grounded guards; reviewer gate; `chat`/demo remain primary paths.
- **Sub-agents are sequential** — no parallel execution.
- **Small demo only** — one intentional bug, one-line fix; not large refactors.
- **LLM demo needs API key + network** — separated via env vars; not required for VG live demo.

---

## 11. Frågor jag kan få under redovisningen

Korta svar jag kan använda om jag blir osäker — fakta är desamma, men formuleringen är min egen.

**F: Är det verkligen multi-agent?**  
**Jag kan svara ungefär så här:** Ja. I experimentellt läge kan `MainAgent` anropa `planner`, `explorer`, `coder` och `reviewer` via `ACTION: subagents`. I `chat` v.2 visar jag deterministiska review-subagents (code reviewer, test agent, fix planner) som main assistant sammanfattar. Live-demo fokuserar på det tydliga verktygsflödet.

**F: Hur stoppar ni farliga kommandon?**  
**Jag kan svara ungefär så här:** En safety checker körs innan tools. Destruktiva kommandon som `rm -rf` blockeras, och känsliga paths som `.env` får inte läsas eller ändras. Samma regler gäller i demo, chat och experimentellt LLM-läge.

**F: Hur hanterar ni lång tool-output / context?**  
**Jag kan svara ungefär så här:** Långa observationer kompakteras deterministiskt (start + slut + metadata). I chat v.2 kan jag köra `compact context` så att viktig session state (current file, pending edit) behålls men action history trimmas.

**F: Hur funkar token- och kostnadsspårning?**  
**Jag kan svara ungefär så här:** `TokenBudgetMonitor` räknar ungefärliga tokens, varnar nära gränsen och stoppar vid hard cap. I chat visar `show token usage` sessionens budget — deterministiska uppskattningar utan API-nyckel. Vid riktig LLM går det via `ChatClient`.

**F: Varför inte live-LLM som huvuddemo?**  
**Jag kan svara ungefär så här:** `personal-dev-assistant chat` och demo runner är stabila offline och behöver ingen nyckel. Experimentellt `run-agent --llm` finns för den som vill visa riktig modell — men det är extra, inte krav för VG.

**F: Vilket LLM använder ni i experimentellt läge?**  
**Jag kan svara ungefär så här:** OpenAI-kompatibel client med `OPENAI_API_KEY` och `OPENAI_BASE_URL=https://openrouter.ai/api/v1`. Standardmodell i `config.yaml` är `openai/gpt-5.1-codex-mini`. Hemligheter ligger i `.env`, inte i repot.

**F: Kan någon annan köra projektet enkelt?**  
**Jag kan svara ungefär så här:** Ja — README har venv-steg, och Docker kör tester och demo utan inbakad API-nyckel. `pip install -e ".[dev]"` och `pytest tests` räcker lokalt.

**F: Vad skulle du förbättra härnäst?**  
**Jag kan svara ungefär så här:** Mer generell review utöver demo-buggen, eventuellt live-LLM i chat, parallella subagents — medvetet utanför nuvarande scope. v.2 chat är redan min primära produktlika demo-väg.

---

## 12. Min föreslagna presentationsordning

Det här är ordningen jag själv följer — hellre lugn och tydlig än att stressa igenom allt.

1. **Kort pitch + problem** (ca 30 s) — vad projektet gör och varför safety/context spelar roll.
2. **Arkitektur** (ca 1 min) — peka på `docs/architecture.md` eller skissa User → chat/demo/LLM → tools → safety.
3. **VG-krav** (ca 1 min) — snabb genomgång av tabellen i detta script eller `docs/requirements.md`.
4. **`pytest tests`** (ca 1 min) — visa **294 passed** för trovärdighet.
5. **`personal-dev-assistant chat`** (ca 4–5 min) — **huvuddemo**: open → review → fix → apply → run tests → token usage → compact → exit.
6. **Valfritt** (ca 1–2 min) — `demo.runner` one-shot eller kort `run-agent --llm` om tid och nyckel finns.
7. **Styrkor + begränsningar** (ca 1 min) — säg proaktivt vad som *inte* är Claude Code (sektion 10).
8. **Frågor** — använd sektion 11 om något dyker upp.

Kom ihåg: visa hellre ett stabilt och tydligt flöde än att försöka visa allt.
