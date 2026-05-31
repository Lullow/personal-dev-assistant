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

### 2026-05-28 - Context/output compaction

#### Vad som implementerades

- Lade till deterministic output compaction utan LLM-sammanfattning.
- Lång output bevarar början och slutet av texten.
- Lade till truncation marker och size metadata för original och compacted output.
- Lade till `compact_tool_observation` helper för ToolResult-style observations.

#### VG-krav som stöds

- Context engineering: undvika att raw tool output fyller aktiv context.

#### Tester

- Lade till tester för kort output, lång output, truncation marker, bevarad början/slut och config-styrd maxstorlek.
- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 87 passed.

#### Begränsning / nästa steg

- Bash execution är inte implementerat än.

### 2026-05-28 - Partial file edit tool

#### Vad som implementerades

- Lade till `partial_edit` tool för små, exakta textändringar i tillåtna projektfiler.
- Använder safety checks innan redigering och håller paths inom `project_root`.
- Kräver att `old_text` matchar exakt en gång.
- Avvisar blockerade paths, paths utanför project root, no-op edits, duplicerade matchningar, saknad `old_text` och icke-UTF-8-filer.

#### VG-krav som stöds

- Partial file editing och skydd mot skadliga filändringar.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 116 passed.

#### Begränsning / nästa steg

- Token budget monitoring och LLM/client-lager är inte implementerade än.

### 2026-05-28 - Token budget monitor

#### Vad som implementerades

- Lade till `TokenBudgetMonitor` för session-baserad token- och kostnadsspårning.
- Spårar input tokens, output tokens, total tokens, återstående budget, warning threshold, hard cap och uppskattad kostnad.
- Använder `TokenUsage` från `models.py` och läser budgetinställningar från `AppConfig.token_budget`.

#### VG-krav som stöds

- Real-time token/cost monitoring, budget warnings och hard-cap-beteende.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 123 passed.

#### Begränsning / nästa steg

- LLM client och agent loop är inte implementerade än.

### 2026-05-28 - LLM client layer

#### Vad som implementerades

- Lade till LLM client-abstraktion med budget-medveten `complete()`.
- Lade till `MockChatClient` för tester och dry-run-läge.
- Lade till OpenAI-kompatibel client utan hårdkodade secrets.
- `LLMResponse` innehåller text, `TokenUsage`, model och mock-flagga.
- Varje lyckat anrop uppdaterar `TokenBudgetMonitor`.
- Hard cap stoppar ytterligare anrop innan modellen anropas.

#### VG-krav som stöds

- Token/cost monitoring-integration och grund för LLM-anrop i main agent och sub-agents.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 130 passed.

#### Begränsning / nästa steg

- Main agent loop och sub-agent orchestration är inte implementerade än.
- OpenRouter/base_url-konfiguration kan förbättras senare vid behov.

### 2026-05-28 - Main agent loop

#### Vad som implementerades

- Lade till första `MainAgent`-loopen med ACTION-baserad protocol parsing.
- Stödjer `read_file`, `list_project_files`, `bash`, `partial_edit` och `finish`.
- Håller step count och stoppar vid `max_steps`.
- Stoppar säkert vid token budget hard-cap.
- Kompakterar tool observations innan de läggs till i context.

#### VG-krav som stöds

- Baseline agent-beteende där agenten väljer om den ska fortsätta med tool-calls eller yield tillbaka till användaren.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 138 passed.

#### Begränsning / nästa steg

- Sub-agent orchestration är inte implementerad än.

### 2026-05-30 - Sub-agent orchestration

#### Vad som implementerades

- Lade till `SubAgentRunner` under `src/personal_dev_assistant/agents/`.
- Stödjer sub-agent-roller: `planner`, `explorer`, `coder` och `reviewer`.
- Varje sub-agent laddar sin egen promptfil från `prompts/` (t.ex. `planner_agent.md`).
- Sub-agents anropar befintlig `ChatClient` och returnerar strukturerade `AgentResult`-objekt via ett enkelt response-protokoll (`ROLE`, `SUMMARY`, `FINDING`, `RISK_LEVEL`, `NEXT_STEP`).
- `MainAgent` stödjer `ACTION: subagents` med `ROLES:` för flera roller i samma steg.
- Sub-agent-resultat kompakteras innan de läggs till i main agents observations.
- Okända roller avvisas tydligt utan LLM-anrop.

#### VG-krav som stöds

- Main agent kan starta sub-agents och använda deras resultat i loopen.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 146 passed.

#### Begränsning / nästa steg

- Sub-agents körs sekventiellt; riktig parallell körning kan bli en framtida förbättring.

### 2026-05-30 - Deterministic demo runner

#### Vad som implementerades

- Lade till end-to-end demo runner under `src/personal_dev_assistant/demo/`.
- Demon använder befintliga safe tools: `list_project_files`, `read_file`, `bash` och `partial_edit`.
- Kör tester före och efter fix via `bash` (`pytest demo_project`).
- Applicerar avsedd one-line-fix i `demo_project/calculator.py` (`return a - b` → `return a + b`).
- Deterministiskt flöde utan LLM; kräver ingen riktig API-nyckel.
- Repeterbart: kan återställa initial bug-state eller rapportera att ingen edit behövs om projektet redan är fixat.
- CLI-entrypoint: `python -m personal_dev_assistant.demo.runner` och `personal-dev-assistant-demo`.

#### VG-krav som stöds

- Live/demo-bevis för bash-exekvering, partial file editing, safety och tool workflow i `demo_project/`.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 153 passed.

#### Begränsning / nästa steg

- README, setup/demo-instruktioner och packaging behöver fortfarande poleras.

### 2026-05-30 - Docker packaging

#### Vad som implementerades

- Lade till `Dockerfile` för att köra projektet i container.
- Lade till `.dockerignore` så secrets, venv och cache-filer inte kopieras in i imagen.
- Lade till `docker-compose.yml` med `test`- och `demo`-services.
- Docker-imagen kan köra testsuite och deterministisk demo.
- Deterministisk demo kräver ingen API-nyckel; secrets skickas endast som valfri runtime-input via `.env`.
- Uppdaterade `README.md` med Docker build/run-instruktioner.

#### Verifiering

- `docker build -t personal-dev-assistant .`
- `docker run --rm personal-dev-assistant pytest tests`
- `docker run --rm personal-dev-assistant`
- `docker compose build`
- `docker compose run --rm test`
- `docker compose run --rm demo`

#### VG-krav som stöds

- Packaged/easy setup så en annan person kan bygga och köra projektet reproducerbart.

#### Tester

- Kördes i Docker: `docker run --rm personal-dev-assistant pytest tests`
- Resultat: 153 passed.

#### Begränsning / nästa steg

- Final demo script/rehearsal behövs fortfarande.

### 2026-05-30 - Presentation-friendly demo output

#### Vad som implementerades

- Förbättrade deterministisk demo-terminaloutput för live-presentation.
- Lade till numrerade steg och `[OK]` / `[FAIL]` / `[STEP]`-markörer.
- Lade till before/after test status i outputen.
- Lade till mini diff för one-line-fixen (`return a - b` → `return a + b`).
- Lade till VG feature checklist i demo-outputen.
- Lade till `--plain` för original enkel output.
- Uppdaterade `README.md` och `docs/demo-script.md`.

#### VG-krav / presentationsnytta

- Klasskamrater kan lättare förstå workflow steg för steg.
- Gabriel kan tydligt se vilka VG-features som demonstreras i demon.

#### Verifiering

- Docker-imagen byggdes om och deterministisk demo verifierades med ny visual output.
- `docker build -t personal-dev-assistant .`
- `docker run --rm personal-dev-assistant`

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 157 passed.

#### Begränsning / nästa steg

- Interaktivt terminal-läge för assistanten är inte implementerat än.

### 2026-05-30 - Interactive terminal assistant mode

#### Vad som implementerades

- Lade till `personal-dev-assistant chat` och `interactive` (alias) i CLI.
- Visar welcome-meddelande och `Ready when you are.` vid start.
- Stödjer kommandon: `help`, `list`, `read`, `review`, `test`, `fix`, `tokens`, `exit`/`quit`.
- Använder befintliga safe tools: `read_file`, `list_project_files`, `bash`, `partial_edit`.
- `fix`-kommandot visar agent-style flow med MAIN AGENT, PLANNER, EXPLORER, CODER och REVIEWER.
- `tokens`-kommandot visar token budget via `TokenBudgetMonitor`.
- Deterministisk MVP utan API-nyckel; inte free-form LLM-chat.
- Uppdaterade `README.md` och `docs/demo-script.md`.

#### VG-krav / presentationsnytta

- Projektet känns mer som en användbar assistant och är lättare för klasskamrater att förstå.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 170 passed.

#### Begränsning / nästa steg

- Free-form LLM-läge och stöd för bredare buggar kan bli framtida förbättringar.

### 2026-05-30 - Experimental LLM agent mode

#### Vad som implementerades

- Lade till experimentellt `personal-dev-assistant run-agent "task" --llm`-läge.
- Tydligt markerat som experimentellt och valfritt; inte primär demo-väg.
- Kräver `OPENAI_API_KEY` från environment variables.
- Använder befintlig `MainAgent` och OpenAI-kompatibel `ChatClient`.
- Använder `TokenBudgetMonitor`.
- Respekterar max steps, token hard-cap, safety checks, blockerade paths och safe bash-begränsningar.
- Första versionen tillåter endast `read_file`, `list_project_files`, `bash` och `finish`.
- `partial_edit` och subagents är avsiktligt inaktiverade i experimentellt läge av säkerhetsskäl.
- Ogiltigt model action-format stoppar säkert.
- Lade till tester i `tests/test_run_agent.py`.
- Uppdaterade `README.md` och `docs/demo-script.md`.

#### VG-krav / presentationsnytta

- Visar en säker väg mot en riktig LLM-driven agent samtidigt som deterministisk demo fortsätter vara primär pålitlig demo.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 180 passed.

#### Begränsning / nästa steg

- Låt LLM föreslå edits säkert, lägg till reviewer/sub-agent-godkännande innan `partial_edit` aktiveras.

### 2026-05-30 - Experimental proposed edit mode

#### Vad som implementerades

- Lade till `ACTION: propose_edit` i experimentellt LLM-läge (`run-agent --llm`).
- Föreslagna edits valideras men appliceras **inte** som standard; filer på disk ändras inte utan explicit flagga.
- Lade till CLI-flaggan `--apply-proposed-edits` för att applicera validerade förslag.
- Applicering går endast via befintliga `partial_edit`-verktyget — ingen bypass av safety-lagret.
- Validering använder samma regler som `partial_edit`: blockerade paths, paths inom project root, UTF-8-textfiler, icke-tom `old_text`, exakt-en gång-matchning, avvisning av duplicerade matchningar, no-op edits och binary/icke-UTF-8-filer.
- Observations inkluderar mini diff och apply hint när ett förslag är giltigt.
- `partial_edit` förblir blockerad som direkt LLM-action i experimentellt läge.
- Subagents förblir inaktiverade i experimentellt LLM-läge.
- Lade till `tests/test_propose_edit.py` och utökade `tests/test_run_agent.py`.
- Uppdaterade `README.md` och `docs/safety-policy.md`.

#### Produkt- och säkerhetsnytta

- Säker väg mot LLM-driven kodredigering utan att ge modellen obegränsad skrivåtkomst.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 192 passed.

#### Begränsning / nästa steg

- Lägg till reviewer/sub-agent-godkännande innan föreslagna edits appliceras automatiskt, eller inför JSON-schema-liknande response-format för mer robust parsing.

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
