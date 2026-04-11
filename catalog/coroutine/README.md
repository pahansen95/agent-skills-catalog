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

## Skills

- **[coro-develop](skills/coro-develop/SKILL.md)** — activates the orchestrator
  behavioral spec for driving a coroutine worker session
