# Safety Policy

Personal Dev Assistant must treat local commands and file edits as potentially risky. The first VG implementation should prefer small, obvious actions and ask for confirmation when risk is unclear.

## Blocked bash commands

Commands must be blocked when they can destroy data, bypass safety checks, or modify hidden/internal project state.

Blocked examples:

- `rm -rf`, `rm -r`, `rm -f`
- `sudo`
- `chmod -R`, `chown -R`
- `mkfs`, `dd`, `mount`, `umount`
- `git reset --hard`
- `git clean`
- `git checkout --`
- `git push --force`
- `curl ... | sh`
- `wget ... | sh`
- commands that write directly into blocked paths

The checker should match command intent, not only exact strings. For example, `rm -rf ./demo_project` is blocked even if spacing or path syntax differs.

## Risky commands requiring confirmation

These commands may be valid in a coding workflow but should require explicit user confirmation before execution:

- `pip install`, `python -m pip install`
- `npm install`, `pnpm install`, `yarn install`
- `git commit`
- `git push`
- `git merge`
- `git rebase`
- commands that create, overwrite, or move many files
- commands that run scripts from the repository, such as `python scripts/name.py`, when the script behavior has not been inspected

For the demo, the assistant should avoid commands that require confirmation unless they are necessary.

## Allowed safe commands

These commands are generally safe when run inside the project directory:

- `pwd`
- `ls`
- `find`-like project listing implemented internally by the app
- `pytest`
- `python -m pytest`
- `python --version`
- `python -m compileall` for allowed source paths

Even safe commands must still respect timeouts and output limits.

## Blocked paths

Tools must not read, edit, or execute commands targeting these paths:

- `.env`
- `.env.*` except `.env.example`
- `.git/`
- `.venv/`
- `venv/`
- `env/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.cache/`
- `dist/`
- `build/`

The assistant may mention these paths in explanations, but tool operations should reject them.

## Partial edit safety rules

Partial edits must follow these rules:

- Edit only text files in allowed project paths.
- Require an exact `old_text` match before replacing.
- Reject edits when `old_text` appears more than once.
- Keep edits small and focused on the user's requested task.
- Do not edit secrets, virtual environments, caches, git internals, generated artifacts, or binary files.
- Prefer one clear replacement over broad search-and-replace.
- Summarize the intended edit before applying it when the change is not trivial.
- Run relevant tests after edits when a test command is available.

For the demo, the expected safe edit is a single-line fix in `demo_project/calculator.py`.

## Interactive Assistant chat: slash-apply and intent safety

In `personal-dev-assistant chat` (Interactive Assistant v.2.1):

- **Intent recognition is not action authorization.** Classifying user text (deterministically or via optional `--llm-intents`) only selects an internal command name. It does not grant permission to modify files.
- **File changes require explicit `/apply`.** The slash command is the authorization step after a pending edit exists. Plain `apply` shows a reminder only and does not write to disk.
- **LLM-classified `apply` is blocked** with a safe message. Vague confirmations (`yes`, `ok`, `sure`, `do it`, `go ahead`, `don't apply this`) must not apply edits, even when `--llm-intents` is enabled.
- **`fix` is non-destructive** — it creates a pending proposed edit through `propose_edit` validation; **`reject`** clears pending state without writes.
- **Optional `--llm-intents`** may only map ambiguous natural language to allowed commands (`help`, `list`, `read`, `current`, `review`, `fix`, `reject`, `test`, `tokens`, `compact`, `exit`, `unknown`). The LLM must not execute tools, invent bash commands, or write files. All actions still pass through existing safe handlers and the same `partial_edit` rules.
- **Deterministic parsing remains the default** and first pass; it is the primary demo path without an API key.

## Proposed edit safety rules (experimental LLM mode)

In experimental LLM mode, the model may use `ACTION: propose_edit` instead of calling `partial_edit` directly.

Default behavior is **non-destructive**:

- Proposals are validated with the same path and text rules as `partial_edit`.
- Files are **not modified** unless the user runs with `--apply-proposed-edits`.
- When applying is enabled, the system still routes through `partial_edit` — no raw writes or bypass.
- A deterministic **reviewer gate** classifies each proposal as low, medium, or high risk.
- Only **low** and **medium** risk proposals can be applied, even with `--apply-proposed-edits`; **high** risk proposals are never auto-applied.

Invalid proposals (missing fields, blocked paths, empty `OLD_TEXT`, duplicate matches, no-op edits) are rejected with a clear observation. Malformed `propose_edit` responses stop the agent safely.
