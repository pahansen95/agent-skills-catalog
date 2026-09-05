# Coroutine Protocol

This document is authoritative for the messages, state transitions, lifecycle,
and persisted session state shared by the coroutine CLI and its actors.

## Roles

- The **orchestrator** owns phase intent, sends instructions, interprets worker
  signals, applies gates, and decides when to escalate or complete the phase.
  Its operating discipline is in [role/orchestrator.md](role/orchestrator.md).
- The **worker** implements one phase in a dedicated session. The CLI loads only
  [role/worker.md](role/worker.md), so that document contains the worker's full
  contract without exposing orchestration or storage details.

## Messages

Every ordinary worker response ends with this as its last line:

```text
YIELD: <STATUS> | <summary>
```

The summary must be short and actionable. The five statuses and corresponding
orchestrator actions are:

| Status | Worker meaning | Orchestrator action |
|---|---|---|
| `DONE` | The last instruction is finished; ready for another | Send the next instruction, or complete the phase if every success criterion passes |
| `BLOCKED` | A decision or missing information prevents progress | Send `DECIDE: <answer>`, or hold and escalate |
| `FAILED` | A concrete failure needs direction | Send `FIX: <description>`, or hold and escalate |
| `RUNNING` | Work remains and can continue next turn | Send `CONTINUE` |
| `CHECK` | A gated artifact is ready for inspection | Inspect it and send `VERIFY: ok` or `VERIFY: <issue>` |

`DONE` is a worker-turn result. `COMPLETE` is the orchestrator's terminal phase
decision; the two are not interchangeable.

The orchestrator may also send `BEGIN` to start approved implementation and
`ABORT` to cancel the phase. Other messages may give free-form scope,
questions, or corrections.

## State transitions

Worker states describe observable message boundaries:

| From | Event | To |
|---|---|---|
| `IDLE` | Receive the first instruction | `WORKING` |
| `WORKING` | Emit `DONE`, `BLOCKED`, `FAILED`, or `RUNNING` | `AWAITING` |
| `WORKING` | Emit `CHECK` | `CHECKPOINT` |
| `AWAITING` | Receive a non-`ABORT` message | `WORKING` |
| `CHECKPOINT` | Receive `VERIFY` | `WORKING` |
| `AWAITING` or `CHECKPOINT` | Receive `ABORT` | `HALTED` |
| `WORKING` | Receive `ABORT` | Finish the current generation, then `HALTED` |

The orchestrator observes corresponding phase states:

| From | Event | To |
|---|---|---|
| none | `coro create` succeeds | `SPAWNED` |
| `SPAWNED` or `IDLE` | Send an instruction | `RUNNING` |
| `RUNNING` | Receive `DONE` | `IDLE` |
| `RUNNING` | Receive `BLOCKED` or `FAILED` | `RESOLVING` |
| `RUNNING` | Receive `RUNNING` | `RUNNING` |
| `RUNNING` | Receive `CHECK` | `VERIFYING` |
| `RESOLVING` | Send `DECIDE` or `FIX` | `RUNNING` |
| `VERIFYING` | Send `VERIFY` | `RUNNING` |
| Any nonterminal state | Run `coro hold` | `ESCALATED` |
| `ESCALATED` | Run `coro send` | `RUNNING` (the CLI clears the hold) |
| `ESCALATED` | Run `coro unhold` | Prior state |
| `IDLE` | Success criteria pass and orchestrator declares completion | `COMPLETE` |
| Any nonterminal state | Send `ABORT` | `ABORTED` |

`COMPLETE`, `ABORTED`, and worker `HALTED` are terminal. No file persists the
orchestrator FSM; it is derived from the last YIELD and any hold sentinel.

## Session lifecycle

`CREATE -> YIELD loop -> COMPLETE or ABORTED`

During create, the CLI generates a `<name>_<unix-seconds>` slug, persists the
Claude session UUID before spawning Claude, sends the worker preamble, waits for
its acknowledgment, and pushes the slug onto `CURRENT`. Each later `coro send`
resumes the UUID, records the event stream, and surfaces the final YIELD. The
CLI reports state but never chooses the next message or marks a phase complete.

## Session storage

The slug is canonical session identity; the user-supplied name is a label.
Unless `CORO_PROJECT` is set, the CLI discovers the project by walking upward
from the current directory until it finds `.cache/coro/`, falling back to the
current directory when none exists. Per-session state lives under
`<project>/.cache/coro/<slug>/`; workers neither see nor modify it.

| Path | Contract |
|---|---|
| `uuid` | Stable Claude session identifier |
| `meta` | Session metadata, including the model used at create time |
| `turns/NNN.jsonl` | Raw events for a turn, written progressively |
| `hold` | Optional reason on line 1 and ISO-8601 UTC timestamp on line 2 |
| `lock` | Persistent file whose active fcntl lock prevents concurrent sends |
| `.cache/coro/CURRENT` | Newline-delimited stack of slugs; its final line is the top |

`coro hold` writes the sentinel idempotently. `coro unhold` removes it without
error when absent. `coro status` reports holds and active sends without changing
them. `coro send` clears a hold before acquiring the exclusive send lock and
reports that action. `create` and `use` push onto `CURRENT`; `pop` removes and
returns its top; `list` displays the stack top first. Bare `send`, `status`, `turns`, and
`log` use the top slug, while an explicit session argument wins.

Commands resolve a session argument in this order:

1. Use an exact slug whose session directory and `uuid` file exist.
2. Match the name portion before the final `_<digits>` suffix.
3. Fail when there are zero matches or multiple matches; ambiguity is never
   resolved by recency or current state.

Authoritative output such as creation, status headers, turn listings, and log
paths uses the slug. Conversational output may use an unambiguous name.
