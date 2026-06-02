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

### 2026-05-30 - Natural interactive command parsing

#### Vad som implementerades

- Förbättrade deterministisk command parser i `personal-dev-assistant chat` / `interactive`.
- Lade till natural/synonym inputs, t.ex. `show files`, `open <path>`, `can you review it`, `run tests`, `fix the bug`, `show token usage`.
- Befintliga fasta kommandon (`help`, `list`, `read <path>`, `review`, `test`, `fix`, `tokens`, `exit`/`quit`) fungerar oförändrat.
- Parsern strippar artiga prefix som `can you`, `could you`, `please` och `please can you` innan intent-matchning.
- Token/budget-intents prioriteras före file-display-intents som `show <path>` (t.ex. `show token usage` → `tokens`, inte `read`).
- Ingen LLM-parsing tillagd; fortfarande deterministisk och säker.
- Utökade tester i `tests/test_interactive.py`.
- Uppdaterade `README.md` och `docs/demo-script.md`.

#### Presentationsnytta

- Interaktivt läge känns mer naturligt och är lättare för klasskamrater att förstå utan att memorera exakta kommandon.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 225 passed.

#### Begränsning / nästa steg

- Free-form LLM-chat är fortfarande experimentell och separat från deterministiskt interaktivt läge (`run-agent --llm`).

### 2026-05-30 - Reviewer gate for proposed edits

#### Vad som implementerades

- Lade till deterministisk reviewer gate för experimentella `propose_edit`-förslag (`propose_edit_review.py`).
- Klassificerar föreslagna edits som **low**, **medium** eller **high** risk.
- **Low** risk för små, fokuserade edits i demo-/testpaths (t.ex. `demo_project/`, `tests/`, `test_*.py`, `*_test.py`).
- **Medium/high** risk för bredare replacements eller edits utanför demo-/testpaths.
- **High-risk** edits blockeras även med `--apply-proposed-edits`.
- Endast **low** och **medium** risk kan appliceras när apply-flaggan är satt.
- Output inkluderar `risk_level`, `reviewer_summary`, `recommendation`, `valid`, `applied` och `mini_diff`.
- Faktiska filändringar går fortfarande endast via `partial_edit` — ingen bypass.
- Direkt `partial_edit` från LLM förblir blockerad i experimentellt läge; subagents förblir inaktiverade.
- Lade till `tests/test_propose_edit_review.py` och utökade `tests/test_propose_edit.py` / `tests/test_run_agent.py`.
- Uppdaterade `README.md` och `docs/safety-policy.md`.

#### Produkt- och säkerhetsnytta

- LLM kan föreslå ändringar med tydlig riskbedömning innan något skrivs till disk; automatisk apply är begränsad till säkrare förslag.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 243 passed.

#### Begränsning / nästa steg

- Förbättra strukturerat response-format, t.ex. JSON schema, eller lägg till sub-agent reviewer-godkännande i experimentellt LLM-läge.

### 2026-05-30 - Experimental LLM agent trace output

#### Vad som implementerades

- Förbättrade terminaloutput för experimentellt `run-agent`-läge (`format_experimental_output` i `run_agent.py`).
- Lade till tydlig sektion **AGENT TRACE** med steg-för-steg-spårning (`AgentStepRecord` i `MainAgent`).
- Visar `[LLM DECISION]`, `[TOOL RESULT]`, `[SAFETY]`, `[REVIEWER]`, token budget, körningssammanfattning och **FINAL ANSWER**.
- Deterministisk `chat` och demo förblir primära presentationsvägar.
- Safety checks försvagades inte; direkt `partial_edit` från LLM förblir blockerad.
- Föreslagna edits går fortfarande via `propose_edit` och reviewer gate.
- Utökade tester i `tests/test_run_agent.py` (scripted/mock clients).
- Uppdaterade `README.md` och `docs/demo-script.md`.

#### Produktnytta

- Experimentellt LLM-läge är lättare att förstå och närmare en riktig LLM-driven agent-loop vid demonstration.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 246 passed.

#### Begränsning / nästa steg

- Testa mot riktig API-nyckel/modell och förbättra action-format-robusthet vid behov (t.ex. JSON schema).

### 2026-06-01 - OpenRouter model configuration

#### Vad som implementerades

- Uppdaterade standardmodell i `config.yaml` till `openai/gpt-5.1-codex-mini`.
- Uppdaterade `.env.example`, `README.md` och `docs/technical-spec.md` för OpenRouter-setup.
- Experimentellt LLM-läge använder OpenRouter via OpenAI-kompatibla environment variables:
  - `OPENAI_API_KEY`
  - `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
- Deterministisk demo och `chat` kräver fortfarande ingen API-nyckel.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 246 passed.

#### Begränsning / nästa steg

- Verifiera riktigt `run-agent`-beteende mot OpenRouter och fixa base URL-stöd vid behov.

### 2026-06-01 - OpenAI-compatible base URL support

#### Vad som implementerades

- Lade till `OPENAI_BASE_URL`-stöd i runtime/environment config.
- `ChatClient` använder nu konfigurerad OpenAI-kompatibel base URL i stället för att alltid använda standard OpenAI-endpoint.
- OpenRouter-anrop går mot `https://openrouter.ai/api/v1/chat/completions`.
- Standard OpenAI-kompatibel URL används när `OPENAI_BASE_URL` saknas.
- Förbättrade testisolering så lokala `OPENAI_API_KEY` / `OPENAI_BASE_URL` i shell inte påverkar tester.
- Lade till/uppdaterade tester i `tests/test_config.py`, `tests/test_llm_client.py`, `tests/test_run_agent.py` och `tests/conftest.py`.

#### Produktnytta

- Experimentellt LLM-läge kan använda OpenRouter säkert via environment variables.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 253 passed.

#### Begränsning / nästa steg

- Fortsatt verifiering av riktiga OpenRouter-körningar i `run-agent --llm`.

### 2026-06-01 - Experimental LLM parse failure debugging

#### Vad som implementerades

- Förbättrade felsökning vid ogiltiga actions i experimentellt `run-agent`-läge.
- När modellen returnerar ett oparsbart svar visar terminaltrace nu **PARSE FAILURE** och **RAW MODEL RESPONSE**.
- Raw model response kompakteras/trunkeras enligt befintliga compaction-regler.
- Lade till grundläggande secret redaction för API-key-liknande strängar och bearer tokens.
- Stärkte experimentellt action protocol med striktare no-prose- och one-ACTION-block-instruktioner.
- Verifierade med live OpenRouter-körning att parse failures nu syns tydligt och är lättare att felsöka.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 257 passed.

#### Begränsning / nästa steg

- Förbättra parser-robusthet för vanliga LLM-formateringsmisstag.

### 2026-06-01 - Experimental LLM action parsing robustness

#### Vad som implementerades

- Förbättrade action parser-robusthet för vanliga LLM-formateringsvariationer.
- Parser tolererar nu inline parameter-misstag, t.ex.:
  - `ACTION: bash command: pytest demo_project`
  - `ACTION: read_file path: demo_project/calculator.py`
- Parser stödjer även split ACTION-rader, t.ex.:
  - `ACTION:`
  - `list_project_files`
- Lade till tester i `tests/test_protocol.py`.
- Stärkte protocol-text för att avråda från inline-parametrar och kräva korrekt ACTION-format.
- Direkt `partial_edit` och subagents förblir blockerade i experimentellt LLM-läge.
- Bash safety och `allowed_actions`-kontroller försvagades inte.
- Live OpenRouter-körning nådde flödet:
  `list_project_files` → `bash pytest demo_project` → `read_file demo_project/calculator.py` → `propose_edit` → `finish`.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 268 passed.

#### Begränsning / nästa steg

- Förbättra finish-hantering när modellen utelämnar en användbar FINAL-sammanfattning.

### 2026-06-01 - Experimental finish fallback handling

#### Vad som implementerades

- Stärkte experimentellt ACTION protocol så `ACTION: finish` ska inkludera `FINAL`.
- Lade till säker fallback-final response när modellen returnerar en tom eller värdelös finish, t.ex. endast `ACTION: finish`.
- Bevarade korrekta modell-FINAL-sammanfattningar när de finns.
- Safety checks försvagades inte.
- Direkt `partial_edit` från experimentellt LLM-läge förblir blockerad.
- Subagents förblir inaktiverade i experimentellt LLM-läge.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 272 passed.

#### Begränsning / nästa steg

- Fortsätt förbättra action-format-robusthet och trace-grounding.

### 2026-06-01 - Guard against false propose_edit claims

#### Vad som implementerades

- Lade till truthfulness guard för experimentella finish-sammanfattningar.
- Om `FINAL` hävdar att en proposed edit skickades in, granskades, risk-klassificerades, applicerades eller inte applicerades, men ingen `ACTION: propose_edit` förekom i körningen, ersätts svaret med en sanningsenlig fallback.
- Guard ändrar endast final text; den kör inte verktyg, skapar inte edits och applicerar inte filer.
- Faktiska `propose_edit`-flöden accepteras fortfarande när `ACTION: propose_edit` kördes.
- Stärkte protocol-text så modellen inte får hitta på reviewer-/risk-/apply-status.

#### Produktnytta

- Slutsvar är mer trace-grounded och kan inte hävda actions som inte skedde.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 275 passed.

#### Begränsning / nästa steg

- Fortsätt förbättra trace-grounding för testresultat och filinläsning före `propose_edit`.

### 2026-06-01 - Trace-grounded experimental LLM workflow

#### Vad som implementerades

- Lade till striktare trace-grounding för experimentellt LLM-läge.
- Modellen får inte hävda att tester failade/passerade eller nämna pytest-resultat om inte `ACTION: bash` faktiskt kördes och gav testoutput.
- `ACTION: propose_edit` blockeras i experimentellt läge om målfilen inte först lästs med `ACTION: read_file` i samma körning.
- Blocket ger en observation som säger åt modellen att läsa filen först; ingen auto-edit eller auto-apply.
- Lade till fallback för final-sammanfattningar som hävdar testresultat utan bash-action.
- Verifierade med live OpenRouter/OpenAI-kompatibla smoke tests:
  `personal-dev-assistant run-agent "Inspect demo_project, run pytest, and propose a fix for the failing test" --llm`
- Observerat korrekt trace:
  `list_project_files` → `bash pytest demo_project` → `read_file demo_project/calculator.py` → `propose_edit` → `finish`
- Verifierade även `--apply-proposed-edits`-vägen som applicerar low-risk reviewed edit via `partial_edit`.
- Återställde `demo_project/calculator.py` efter apply smoke test så demon förblir repeterbar.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 280 passed.

#### Begränsning / nästa steg

- Experimentellt LLM-läge är fortfarande valfritt och mindre deterministiskt än chat/demo; primär demo förblir deterministisk.

### 2026-06-01 - Interactive Assistant v.2 session workflow

#### Vad som implementerades

- Refaktorerade interaktivt läge från en enda `interactive.py` till paketet `interactive/`:
  - `assistant.py`
  - `parsing.py`
  - `review.py`
  - `session.py`
  - `__init__.py`
- Förbättrade `personal-dev-assistant chat` till Interactive Assistant v.2.
- Lade till stateful `InteractiveSession` med spårning av:
  - `current_file_path`
  - `current_file_content`
  - `last_review_summary`
  - `pending_edit`
  - `last_test_result`
  - `context_summary`
  - `action_history`
- Lade till deterministisk multi-agent-style review:
  - code reviewer
  - test reasoning agent
  - fix planner
- `review it` delegerar till dessa deterministiska subagents; main assistant kombinerar output.
- `fix it` skapar pending proposed edit och mini diff, men modifierar inte filer.
- `apply` ändrar filer endast efter explicit användarkommando och använder befintliga `partial_edit` safety path.
- `reject` rensar pending edit utan att ändra filer.
- `run tests` använder säkert bash-kommando `pytest demo_project` för demo_project.
- `show token usage` visar deterministisk lokal/session budget-estimat.
- `compact context` bevarar viktig session state och trimmar action history.
- Lade till natural commands som `show current file`, `review this file`, `fix it`, `apply`, `reject`, `compact context`.
- Verifierade v.2 demo-flöde:
  `open demo_project/calculator.py` → `review it` → `fix it` → `apply` → `run tests` → `show token usage` → `compact context` → `exit`
- Demon applicerade `return a - b` → `return a + b`, `pytest demo_project` passerade, därefter återställdes `demo_project/calculator.py`.

#### Produktnytta

- Deterministisk chat är nu den primära produktlika demo-vägen med session state, subagents, säkra proposed edits, användargodkännande, token monitoring och context compaction.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 294 passed.

#### Begränsning / nästa steg

- v.2 review är fortfarande deterministisk och demo-pattern-fokuserad, inte en fullständig general Claude Code-klon.

### 2026-06-02 - Interactive Assistant v.2.1 (LLM intents + slash-apply)

#### Vad som implementerades

- Lade till valfri LLM intent parsing för chat:
  `personal-dev-assistant chat --llm-intents`
- Deterministisk parser förblir standard och första pass; primär demo-väg utan API-nyckel.
- LLM intent parsing används endast för att klassificera tvetydig naturlig text till tillåtna interna kommandon (`help`, `list`, `read`, `current`, `review`, `fix`, `reject`, `test`, `tokens`, `compact`, `exit`, `unknown`).
- LLM kör inga tools direkt, genererar inga godtyckliga bash-kommandon och skriver inga filer — alla åtgärder går via befintliga säkra handlers i `InteractiveAssistant`.
- Känslig filändring kräver explicit slash-kommando: `/apply`.
- Vanligt `apply` visar endast säkerhetspåminnelse: `Applying edits requires explicit /apply.`
- LLM-klassificerat `apply` blockeras; vaga bekräftelser (`yes`, `ok`, `sure`, `do it`, `go ahead`, `don't apply this`) kan inte applicera pending edits.
- Säkerhetsprincip dokumenterad: intent recognition ≠ action authorization.
- Uppdaterat demo-flöde: `open` → `review it` → `fix it` → `/apply` → `run tests` → `show token usage` → `compact context` → `exit`.

#### Produktnytta

- Mer naturlig inmatning i chat utan att tumma på deterministisk verktygskörning eller explicit användargodkännande vid filändring.

#### Tester

- Kördes: `./.venv/bin/python -m pytest tests`
- Resultat: 322 passed.

#### Begränsning / nästa steg

- LLM intent parsing kräver API-nyckel när den används; standarddemo förblir deterministisk utan `--llm-intents`.

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
