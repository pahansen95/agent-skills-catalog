---
name: coro-develop
description: >
  Bootstrap a session into the orchestrator role of a coroutine. Use when
  driving a stateful worker through a phase of implementation work —
  creating the session, sending messages, interpreting YIELD, enforcing
  quality gates. Activate with /coro-develop.
compatibility: Requires Python 3.13 (pyenv), uv, just, and the claude CLI in PATH
---

Bootstraps this session into the **orchestrator role** of a coroutine. After
bootstrap, you operate as orchestrator — driving worker sessions per the
discipline in your role doc.

This SKILL does not define what coroutine orchestration is. That lives in
the protocol and role docs, which you'll read as part of bootstrap.

## Bootstrap procedure

Perform in order before any coroutine work.

### 1. Read the protocol

Read [`protocol.md`](./protocol.md) in full. Defines roles, worker output
contract (YIELD), both FSMs, session lifecycle, message vocabulary, and
session-state overlays. Authoritative.

### 2. Read the orchestrator role

Read [`role/orchestrator.md`](./role/orchestrator.md) in full. Defines your
operating discipline: YIELD interpretation, phase lifecycle, quality gates,
escalation, polling, cost, anti-patterns.

The role cross-references the protocol — doesn't restate it. You need both
in context.

### 3. Verify the `coro` CLI

```bash
which coro      # should resolve to scripts/coro
coro --help
```

One-time setup if needed:

```bash
coro setup      # creates venv, sets Python version; idempotent
```

`coro` is the only tool for coroutine operations. Subcommands (`create`,
`send`, `status`, `turns`, `log`, `use`, `pop`, `list`, `new-phase`, `hold`,
`unhold`) are self-documented via `coro --help` and `coro <cmd> --help`.
Refer to CLI help for command-level detail, not this SKILL.

### 4. Proceed as orchestrator

Drive work per [`role/orchestrator.md`](./role/orchestrator.md). The worker
role ([`role/worker.md`](./role/worker.md)) is sent to workers on session
create by the CLI — available if you want to see what your workers see.

## Environment variables

Set before invoking `coro`. Full list: `coro --help`. Common:

- `CORO_MODEL` — model slug (`opus`, `sonnet`, `haiku`, canonical id, or
  `[1m]` suffix). Default: `sonnet`.
- `CORO_EFFORT` — `low`/`medium`/`high`/`xhigh`/`max`. Default: per-model
  spec default.
- `CORO_MAX_BUDGET_USD` — per-turn budget cap. Unset = no cap.
- `CORO_PROJECT` — project root (default: auto-discovered).

## Deactivation

No explicit deactivate. Sessions persist in `.cache/coro/<slug>/` and are
resumable via `coro send` or inspectable via `coro status`.

Stepping away with in-flight work:
- Declare `COMPLETE` (stop sending, report to human), or
- `coro hold <name> '<reason>'` to pause for human input, or
- Leave idle — no degradation.
