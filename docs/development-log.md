# Development Log

Använd den här loggen för att dokumentera arbetet med projektet. Syftet är att visa hur projektet växer fram genom specs, prompts, dokumentation, krav och AI-assisterad utveckling.

## Loggmall

### Datum

YYYY-MM-DD

### Vad jag gjorde

- 

### Vilka prompts jag använde

- 

### Vilka beslut jag tog

- 

### Vad som behöver göras nästa gång

- 

## Loggar

### 2026-05-28 - Foundation package and config models

#### Vad som implementerades

- Skapade Python package structure under `src/personal_dev_assistant/`.
- Lade till config/env loading från `config.yaml` och environment variables.
- Lade till shared data models: `ToolCall`, `ToolResult`, `AgentResult` och `TokenUsage`.
- Lade till minimal CLI som tar emot en user task och skriver en placeholder response.

#### VG-krav som stöds

- Config file för runtime-inställningar.
- Secrets via environment variables.
- Grundstruktur för agent protocol, tool results och token/cost monitoring.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 10 passed.

#### Begränsning / nästa steg

- CLI är fortfarande en placeholder; agent loop, tools, LLM calls och sub-agents är inte implementerade än.

### 2026-05-28 - Safety policy layer

#### Vad som implementerades

- Lade till command classification för `safe`, `risky_requires_confirmation` och `blocked`.
- Blockerar destruktiva kommandon och markerar riskabla kommandon som kräver bekräftelse.
- Lade till blocked path checks för `.env`, `.git/`, `.venv/`, caches, `dist/` och `build/`.
- Uppdaterade safety checker så att shell chaining/control blockeras: `&&`, `||`, `;`, `|`, backticks och `$(`.

#### VG-krav som stöds

- Skydd mot skadliga tool calls, särskilt riskabla bash-kommandon och blockerade paths innan faktisk tool-exekvering implementeras.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 74 passed.

#### Begränsning / nästa steg

- Safety-lagret klassificerar bara kommandon och paths än så länge; det är ännu inte kopplat till ett bash-tool.

### 2026-05-28 - Read-only filesystem tools

#### Vad som implementerades

- Lade till `read_file` tool för säker läsning av textfiler.
- Lade till `list_project_files` tool för kompakt projektlistning utan att läsa filinnehåll.
- Båda tools använder safety checks innan paths används.
- `read_file` stödjer truncation via `config.context.max_observation_chars`.

#### VG-krav som stöds

- Safe tool usage, file inspection och grund för context/output limiting.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 81 passed.

#### Begränsning / nästa steg

- Bash execution och partial file editing är inte implementerade än.

### YYYY-MM-DD

### Vad jag gjorde

- Skapade första projektstrukturen.
- Lade till dokumentationsfiler och prompt-placeholders.

### Vilka prompts jag använde

- Prompt för att skapa repo-struktur utan agentimplementation.

### Vilka beslut jag tog

- Agentimplementation och demo-projekt ska skapas senare.
- Projektet ska börja med tydliga krav, arkitektur och prompts.

### Vad som behöver göras nästa gång

- Förfina kraven.
- Bestämma teknisk stack.
- Planera första minimala implementationen.
