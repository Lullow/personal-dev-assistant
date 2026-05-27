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
