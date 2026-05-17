# Requirements

## 1. Overview

This document maps each required VG assignment feature to a concrete feature in Personal Dev Assistant and explains how it will be demonstrated.

The goal is to keep the project focused and realistic for a course project while still showing the required AI-agent concepts clearly: multi-agent coordination, context handling, safe tool use, command execution, partial file editing, configuration, and a repeatable demo.

## 2. Requirements checklist

| Requirement | Project feature | How it will be demonstrated | Status |
| --- | --- | --- | --- |
| Multi-agent system: main agent can start sub-agents and use their results | A main agent coordinates the workflow and can call specialized sub-agents for planning, exploration, coding, and review/safety. | In the demo, the main agent asks an explorer-style sub-agent to inspect files, uses the result to decide the next step, and can ask a reviewer/safety step to check risky actions before continuing. | Planned |
| Advanced context engineering: long tool outputs or sub-agent outputs are summarized before being added to active context | A context manager keeps active context short by summarizing long command output, file content, and sub-agent responses. | When tests or file inspections produce longer output, the assistant stores or forwards a short summary instead of adding the full raw output to the next prompt. | Planned |
| Token/cost monitoring: real-time tracking, warnings and hard-cap | A token monitor tracks approximate token usage and cost during a session, warns near the configured budget, and stops execution at a hard cap. | The demo or a scripted run will show current budget usage, a warning threshold, and the behavior when a hard cap would be reached. | Planned |
| Protection against harmful tool calls: safety checker for risky bash commands | A safety checker reviews bash commands before execution and blocks or asks for approval for risky operations. | Safe commands such as listing files and running tests are allowed, while destructive commands are rejected or require explicit confirmation. | Planned |
| Bash command execution | A bash tool can run approved commands in the local project directory. | The assistant runs `pytest` in the demo project to reproduce and later verify the failing test. | Planned |
| Partial file editing | A file editing tool can make small, focused changes instead of rewriting large files. | The assistant changes only the incorrect line in `demo_project/calculator.py` from subtraction to addition. | Planned |
| Packaged/easy setup: Docker or clear setup instructions | The project will include clear setup instructions, and Docker may be added if it improves reproducibility. | A user can follow the setup guide to install dependencies, configure environment variables, and run the demo locally. | Planned |
| Config file for configuration | Runtime options such as model name, token budget, approval settings, and max tool output length are configurable. | The demo can be run with a small config file or documented config values that control model and safety behavior. | Planned |
| Secrets through environment variables | Secrets such as API keys are read from environment variables and documented in `.env.example`. | The setup instructions show how to set `OPENAI_API_KEY` or another provider key without committing secrets to the repository. | Partly present |
| Baseline ASSN-2 behavior: the agent decides whether to continue with more tool calls or yield back to the user | The main agent loop decides after each step whether to call another tool/sub-agent or return a final answer to the user. | In the demo, the assistant continues from inspection to test execution to file edit to verification, then stops and summarizes when the task is complete. | Planned |

## 3. Scope boundaries

The first VG version will stay intentionally small.

- It will not be a full Claude Code replacement.
- It will not support every programming language deeply.
- It will not automatically edit huge codebases.
- It will not try to solve large refactors or complex architecture changes.
- It will focus on a small, reliable demo first.

## 4. Demo proof

The demo will use a small Python project with a failing test. The project is intentionally simple so the assistant can show the complete workflow without unnecessary complexity.

The assistant should:

1. Inspect the demo project files.
2. Run the tests and observe the failing result.
3. Identify that `add(a, b)` returns the wrong value.
4. Make a partial file edit in `demo_project/calculator.py`.
5. Run the tests again.
6. Summarize what it changed, why it changed it, and whether the verification passed.

This demo proves the core behavior required for the VG assignment: controlled tool use, local project inspection, bash execution, partial editing, context summarization, and a clear final explanation to the user.
