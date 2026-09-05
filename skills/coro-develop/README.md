# Coroutine

A coroutine is a stateful, resumable agent session driven turn-by-turn by an
orchestrator. The orchestrator sends instructions; the worker executes and
yields control back with a structured signal. The cycle repeats until the
phase is complete.

This is not a general-purpose automation pattern — it is specifically for
driving long-running implementation work across multiple agent turns where:

- The work is too large for a single context window
- The orchestrator must review and approve before the worker proceeds
- Quality gates (vendor citations, architecture proposals) must be enforced
  between phases

## Wire protocol

See [protocol.md](protocol.md) for the complete YIELD signal vocabulary,
message types, and turn structure.

## Skill

[`SKILL.md`](SKILL.md) activates the orchestrator behavioral spec for driving
a coroutine worker session. The authoritative protocol and role documents are
kept with it so the skill is self-contained.

## Setup and testing

From this repository's root, create the coroutine runtime environment with:

```sh
skills/coro-develop/scripts/setup
```

This requires Python 3.13 and `uv`. The generated
`skills/coro-develop/scripts/.venv/` is ignored. For local test development,
install the test dependencies into that environment and run the suite:

```sh
uv pip install --python skills/coro-develop/scripts/.venv/bin/python pytest hypothesis
skills/coro-develop/scripts/.venv/bin/python -m pytest skills/coro-develop/tests
```
