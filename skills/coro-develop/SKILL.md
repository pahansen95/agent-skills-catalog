---
name: coro-develop
description: >
  Drive a stateful, resumable worker through a phase of implementation work.
  Use when work needs multiple worker turns with explicit review, quality
  gates, or escalation between turns. Activate with /coro-develop.
compatibility: Requires Deno 2.9.6 or newer and the claude CLI on PATH.
metadata:
  version: "1.0.0"
---

# Coroutine Development

Act as the orchestrator for one or more coroutine workers. Each worker owns one
implementation phase and returns control after every turn.

All paths below are relative to this skill's directory. Before starting:

1. Read [protocol.md](protocol.md), the authority for messages, state
   transitions, lifecycle, and session storage.
2. Read [role/orchestrator.md](role/orchestrator.md), your decision and review
   discipline.
3. Run `scripts/coro --help` and use `scripts/coro <subcommand>` to create
   or resume sessions. The CLI is not installed on `PATH`.

The CLI loads [role/worker.md](role/worker.md) directly into each worker; that
file is intentionally self-contained. `coro new-phase` uses the files in
`templates/` to scaffold a phase specification and kickoff prompt.

## Runtime and testing

Install Deno 2.9.6 or newer. The launcher uses the skill-local Deno
configuration, grants filesystem, environment, and `claude` execution
permissions, and preserves the caller's working directory. For local testing:

```sh
deno task --config deno.json fmt
deno task --config deno.json check
deno task --config deno.json lint
deno task --config deno.json test
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
