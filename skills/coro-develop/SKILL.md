---
name: coro-develop
description: >
  Drive a stateful, resumable worker through a phase of implementation work.
  Use when work needs multiple worker turns with explicit review, quality
  gates, or escalation between turns. Activate with /coro-develop.
compatibility: Requires the claude CLI on PATH. Python 3.13 and uv are required to run scripts/setup.
---

# Coroutine Development

Act as the orchestrator for one or more coroutine workers. Each worker owns one
implementation phase and returns control after every turn.

All paths below are relative to this skill's directory. Before starting:

1. Read [protocol.md](protocol.md), the authority for messages, state
   transitions, lifecycle, and session storage.
2. Read [role/orchestrator.md](role/orchestrator.md), your decision and review
   discipline.
3. If `scripts/.venv/bin/python` is absent, follow **Runtime setup** below.
   Then run `scripts/coro --help` and use `scripts/coro <subcommand>` to create
   or resume sessions. The CLI is not installed on `PATH`.

The CLI loads [role/worker.md](role/worker.md) directly into each worker; that
file is intentionally self-contained. `coro new-phase` uses the files in
`templates/` to scaffold a phase specification and kickoff prompt.

## Runtime setup

When the runtime is absent, run `scripts/setup`. It creates `scripts/.venv/`
using the Python version in `scripts/.python-version`. For local test
development:

```sh
uv pip install --python scripts/.venv/bin/python pytest hypothesis
scripts/.venv/bin/python -m pytest tests
```

Use `scripts/coro --help` for commands and environment variables rather than
copying that interface here.

## Ending or pausing work

Sessions persist in `<project>/.cache/coro/` and remain resumable. Declare a
phase `COMPLETE` only after its success criteria pass. A worker's `DONE` means
that turn is finished; it does not by itself complete the phase.

When human input is required, run `coro hold <name> '<reason>'` and report the
specific decision needed. Otherwise an unfinished session may remain idle and
be resumed later.
