# Architecture

Det här dokumentet beskriver arkitekturen på hög nivå för Personal Dev Assistant.

## Översikt

```text
User
  |
  +--> Interactive Assistant v.2 (chat)     [primär demo-väg, deterministisk]
  +--> Deterministic demo runner             [alternativ one-shot demo]
  +--> Experimental run-agent --llm          [valfri, API-nyckel]
  |
  v
Main Agent
  |
  +--> Planner / Explorer / Coder / Reviewer (MainAgent subagents)
  +--> Interactive review subagents (chat: code reviewer, test agent, fix planner)
  |
  v
Tools <--> Context compaction <--> Token Monitor
  |
  v
Safety Checker
```

## Main Agent

Main agent är systemets samordnare. Den tar emot användarens uppgift, avgör vad som behöver göras och väljer om den ska svara direkt eller använda tools och sub-agenter. Används i experimentellt `run-agent --llm`-läge.

## Interactive Assistant v.2 (chat)

Primär presentationsväg — **ingen API-nyckel**.

Paketet `src/personal_dev_assistant/interactive/`:

| Modul | Roll |
| --- | --- |
| `session.py` | `InteractiveSession` — current file, pending edit, review, test result, action history |
| `review.py` | Deterministiska review-subagents: code reviewer, test reasoning agent, fix planner |
| `assistant.py` | Kommandoloop, tool-anrop, apply/reject, compaction |
| `parsing.py` | Deterministisk command parser + natural phrases |

Typiskt flöde: `open` → `review` → `fix it` (pending edit) → `apply` (partial_edit) → `run tests`.

## Planner / Explorer / Coder / Reviewer (MainAgent)

Sub-agents för `MainAgent` (experimentellt LLM-läge och tester). Körs sekventiellt via `ACTION: subagents`. Chat v.2 använder egna deterministiska review-funktioner i stället.

## Tools

Implementerade tools:

- `read_file`, `list_project_files` — säker filinspektion
- `bash` — godkända kommandon (t.ex. `pytest demo_project`)
- `partial_edit` — exakt en gång-matchning med safety checks
- `propose_edit` — validering + reviewer gate; apply endast explicit (`--apply-proposed-edits` eller chat `apply`)

## Context compaction

Long tool/sub-agent output kompakteras innan nästa steg (`context/compaction.py`). Chat v.2 har dessutom session compaction via `compact context` (bevarar current file och pending edit).

## Token Monitor

`TokenBudgetMonitor` spårar ungefärlig tokenanvändning, varningar och hard cap. Chat v.2 visar deterministiska session-estimat via `show token usage`.

## Safety Checker

Safety checker kontrollerar riskabla operationer innan de körs — bash-kommandon, blockerade paths, filändringar. Experimentellt LLM-läge blockerar direkt `partial_edit`; trace-grounded guards förhindrar falska FINAL-påståenden.

## Experimentellt LLM-läge (valfritt)

`personal-dev-assistant run-agent "..." --llm` — riktig `MainAgent` + OpenAI-kompatibel client. Tillåtna actions: `read_file`, `list_project_files`, `bash`, `propose_edit`, `finish`. Reviewer gate på `propose_edit`; apply via `--apply-proposed-edits` (low/medium risk only).
