# Coroutine Protocol

The full design specification: two actors, their state machines, the messages
they exchange, and the supporting machinery (session storage, overlays).

Authoritative. When a role doc, the SKILL, or the CLI references protocol
behavior, the definitions live here.

## Architecture

Three layers:

| Layer | What it is | Where it lives |
|---|---|---|
| **Specification** | The protocol — what the system is | This document |
| **Operating discipline** | How each actor behaves within the spec | [role/orchestrator.md](role/orchestrator.md), [role/worker.md](role/worker.md) |
| **Bootstrap** | How to enter a role in a given session | `skills/coro-develop/SKILL.md` |

Each layer depends only on layers above it. Protocol stands alone. Role docs
depend on protocol. SKILL depends on both.

## Roles

Two actors with asymmetric relationships to this document.

**Orchestrator** — primary agent session. Reads this spec in full. Drives
the worker, interprets YIELD, decides next action, escalates to human.
Discipline in [role/orchestrator.md](role/orchestrator.md).

**Worker** — dedicated session scoped to one phase. Does **not** read this
spec; reads a self-contained role doc ([role/worker.md](role/worker.md))
distilling the worker's slice. Implements, tests, reports. No awareness of
other phases, orchestration state, or the project.

The asymmetry is deliberate: the orchestrator drives the state machine from
outside, the worker only honors its output contract and transitions.

## Worker output contract

Every worker response ends with a YIELD signal as its last line:

```
YIELD: <STATUS> | <summary>
```

### Status values

Statuses the worker may emit while in `WORKING`. Each emission triggers a
Worker FSM transition (below) and an orchestrator response.

| Status | Meaning | Orchestrator action |
|---|---|---|
| `DONE` | Work complete or ready for next instruction | Send next instruction or declare phase complete |
| `BLOCKED` | Cannot proceed — needs a decision | Decide, send `DECIDE: <answer>` |
| `FAILED` | Something broke — details in summary | Send `FIX: <description>` or escalate |
| `RUNNING` | Work in progress, will continue | Send `CONTINUE` |
| `CHECK` | Asks orchestrator to verify an artifact | Inspect, send `VERIFY: <result>` |

### Examples

```
YIELD: DONE | cargo test passes, GPT written to loop device, gdisk -l validates
YIELD: BLOCKED | need decision: 1K or 4K block size for ext4?
YIELD: FAILED | crc32c mismatch on superblock — computed 0x1234 expected 0x5678
YIELD: RUNNING | implementing block group descriptor table, ~50% complete
YIELD: CHECK | please verify loop device mounts correctly at /mnt/test
```

## Worker FSM

Mechanical state machine. States reflect runtime observables (messages
received, YIELDs emitted), not semantic intent.

### States

| State | Description |
|---|---|
| `IDLE` | Preamble accepted; awaiting first orchestrator message |
| `WORKING` | Orchestrator message received; processing (message-received → YIELD-emitted) |
| `AWAITING` | Non-CHECK YIELD emitted; awaiting next orchestrator message |
| `CHECKPOINT` | `CHECK` YIELD emitted; awaiting `VERIFY` |
| `HALTED` | Terminal — `ABORT` received or session ended |

### Transitions

| From | Event | To | Notes |
|---|---|---|---|
| `IDLE` | `RECV:` any orchestrator message | `WORKING` | first turn |
| `WORKING` | `EMIT: DONE / BLOCKED / FAILED / RUNNING` | `AWAITING` | non-CHECK YIELD |
| `WORKING` | `EMIT: CHECK` | `CHECKPOINT` | per-commit checkpoint |
| `AWAITING` | `RECV:` any non-ABORT message | `WORKING` | resume |
| `CHECKPOINT` | `RECV: VERIFY` | `WORKING` | proceed after inspection |
| `AWAITING` | `RECV: ABORT` | `HALTED` | terminal |
| `CHECKPOINT` | `RECV: ABORT` | `HALTED` | terminal |
| `WORKING` | `RECV: ABORT` | _(deferred)_ | ABORT honored at end of current turn, not mid-generation |

### Diagram

```
          +---------+
          |  IDLE   |
          +----+----+
               | RECV: any
               v
          +---------+  <-------------------------------+
          | WORKING |                                  |
          +----+----+                                  |
               |                                       |
       +-------+-------+                               |
       |               |                               |
       | EMIT:         | EMIT: CHECK                   |
       | DONE/BLOCKED/ |                               |
       | FAILED/       v                               |
       | RUNNING  +------------+                       |
       |          | CHECKPOINT | RECV: VERIFY ---------+
       |          +-----+------+
       v                | RECV: ABORT
  +----------+          |
  | AWAITING |          v
  +----+-----+     +--------+
       |            | HALTED |
       | RECV: any  +--------+
       | non-ABORT       ^
       |                 |
       | RECV: ABORT ----+
       v
  (back to WORKING via arc above)

  Note: RECV: ABORT while WORKING is deferred — honored at turn end.
```

## Orchestrator FSM

One FSM instance per managed worker session. States reflect what the
orchestrator observes and the action it's taking.

### States

| State | Description |
|---|---|
| `SPAWNED` | `coro create` issued; preamble accepted by worker |
| `RUNNING` | Orchestrator has sent a message; worker is in WORKING |
| `IDLE` | Observed `DONE`; orchestrator deciding next action |
| `RESOLVING` | Observed `BLOCKED` or `FAILED`; orchestrator determining response |
| `VERIFYING` | Observed `CHECK`; orchestrator inspecting artifact |
| `ESCALATED` | Human input required; polling suspended |
| `COMPLETE` | Phase shipped; session terminal |
| `ABORTED` | Terminal — orchestrator sent `ABORT` |

### Transitions

| From | Event | To | Notes |
|---|---|---|---|
| _(none)_ | `coro create` succeeds | `SPAWNED` | initial state |
| `SPAWNED` | `SEND:` orient/kickoff message | `RUNNING` | first turn |
| `RUNNING` | `RECV: DONE` | `IDLE` | worker awaiting next instruction |
| `RUNNING` | `RECV: BLOCKED` | `RESOLVING` | needs decision |
| `RUNNING` | `RECV: FAILED` | `RESOLVING` | needs fix |
| `RUNNING` | `RECV: RUNNING` | `RUNNING` | send `CONTINUE`, stay in RUNNING |
| `RUNNING` | `RECV: CHECK` | `VERIFYING` | inspect artifact |
| `IDLE` | `SEND:` next instruction | `RUNNING` | continue phase |
| `IDLE` | declare complete | `COMPLETE` | phase ship; terminal |
| `RESOLVING` | `SEND: DECIDE / FIX` | `RUNNING` | resolved locally |
| `RESOLVING` | `coro hold <name> [<reason>]` | `ESCALATED` | orchestrator determines human input needed; stops polling |
| `IDLE` | `coro hold <name> [<reason>]` | `ESCALATED` | any non-terminal state can transition to ESCALATED via orchestrator action |
| `VERIFYING` | `SEND: VERIFY` | `RUNNING` | proceed |
| `ESCALATED` | `coro send <name> ...` | `RUNNING` | send auto-clears hold sentinel |
| `ESCALATED` | `coro unhold <name>` | _(prior state)_ | explicit unhold without sending |
| any | `SEND: ABORT` | `ABORTED` | terminal |

### Diagram

```
  coro create
      |
      v
  +----------+
  | SPAWNED  |
  +----+-----+
       | SEND: kickoff
       v
  +-----------------------------------------------------------+
  |                        RUNNING                            |
  +---+----------+----------+----------+--------------------+-+
      |          |          |          |
   RECV:      RECV:      RECV:      RECV:
   DONE      BLOCKED    FAILED     CHECK
      |          |          |          |
      v          v          v          v
  +------+  +-----------+  +-----------+
  | IDLE |  | RESOLVING |  | VERIFYING |
  +--+---+  +-----+-----+  +-----+-----+
     |            |               |
     | SEND:      | SEND:         | SEND:
     | instr.     | DECIDE/FIX    | VERIFY
     |            |               |
     +------------+---------------+
                  |
                  v
             (back to RUNNING)

  IDLE or RESOLVING --[coro hold <name>]--> +----------+
                                            | ESCALATED|
  coro send <name> (auto-clears hold) ----> +----+-----+
                                                 |
                             (back to RUNNING) <-+
  coro unhold <name> ---------> (prior state)

  +----------+   +----------+
  | COMPLETE |   | ABORTED  |   <- terminal states
  +----------+   +----------+
  IDLE→declare   any→SEND:ABORT
```

## Session-state overlays

Out-of-band session state. The CLI maintains these on behalf of the
orchestrator; they don't affect the worker's YIELD vocabulary or FSM.
Workers have no awareness — purely orchestrator-side machinery.

Semantics of each overlay file listed in §Session storage below.

### Hold sentinel

**File**: `.cache/coro/<slug>/hold`

**Format**: line 1 is the optional reason string (may be empty); line 2 is
an ISO-8601 UTC timestamp written at hold time (diagnoses stale holds).

**Writer**: orchestrator via `coro hold <name-or-slug> [<reason>]`.
**Readers**: `coro status` (non-destructive), `coro send` (clears before
acquiring the send lock).

- `coro hold` writes idempotently.
- `coro unhold` removes; no error if absent.
- `coro send` auto-clears before acquiring the lock; stderr: `note: cleared
  hold on session '<slug>' (reason: ...)`.
- `coro status` surfaces state on a `hold:` line.

### Send lock

**File**: `.cache/coro/<slug>/lock`

Fcntl exclusive lock for the duration of `coro send`. A concurrent second
send to the same slug fails immediately. `coro status` reports
`sending: yes` via a non-blocking shared-lock probe.

The file persists between sends; only its fcntl state matters.

### CURRENT stack

**File**: `.cache/coro/CURRENT`

Newline-delimited stack of **slugs** (top-to-bottom). Supports bare-slug
dispatch: `coro send` / `status` / `turns` / `log` resolve to the top when
no argument is given. Explicit `<name-or-slug>` always wins.

- `coro create <name>` auto-pushes the generated slug.
- `coro use <name-or-slug>` pushes an existing session's slug (resolving
  ambiguity per §Name resolution).
- `coro pop` removes and returns the top slug.
- `coro list` prints the stack, one slug per line.

## Orchestrator messages

| Message | Meaning |
|---|---|
| `BEGIN` | Start the assigned work |
| `CONTINUE` | Keep going from where you left off |
| `FIX: <description>` | Fix the described problem |
| `DECIDE: <answer>` | Answer to a BLOCKED question |
| `VERIFY: <result>` | Result of a CHECK request |
| `ABORT` | Stop — phase is cancelled |

## Session lifecycle

```
CREATE → [YIELD loop] → COMPLETE
```

**CREATE** — CLI generates the session slug (`<name>_<unix-seconds>`),
establishes and persists the claude session UUID, sends the worker role
doc + phase scope + initial instruction. Worker acknowledges, enters
`IDLE`. The slug is returned to the caller and pushed onto `CURRENT`.
(The orchestrator is separately initialized at skill activation, having
already read this spec and its role doc.)

**YIELD loop** — each turn: worker emits YIELD, orchestrator reads it,
decides the next message, sends. CLI resumes with `--resume <uuid>`.

**COMPLETE** — orchestrator declares done when success criteria met.
Orchestrator-side state; no CLI action marks it.

## Orchestrator turn logic

**Agent behavior, not tool behavior.** The CLI parses YIELD and surfaces it,
but does not decide what to send. That is the orchestrator's reasoning:

```
output = coro send <name> <<< <message>
signal = parse_yield(output)   # last line: "YIELD: STATUS | summary"

match signal.status:
  DONE    → send next instruction OR declare phase complete
  BLOCKED → formulate decision → send "DECIDE: <answer>"
            if human input needed: run "coro hold <name> '<reason>'" and stop
  FAILED  → diagnose → send "FIX: <description>" OR escalate to human
  RUNNING → send "CONTINUE"
  CHECK   → inspect artifact → send "VERIFY: <result>"
```

Full discipline — escalation, quality gates, cost responses — lives in
[role/orchestrator.md](role/orchestrator.md).

Escalate to human when `BLOCKED` requires their input (credentials, design
decisions, infrastructure access).

## Session storage

Sessions are resources. The **slug** is the identity; the **name** is a
human-readable label.

- **slug** = `<name>_<unix-seconds>`, generated by the CLI at `coro create`.
  Canonical. Appears on disk, in `CURRENT`, in meta, and in diagnostic
  output.
- **name** = user-supplied label. Resolved to a slug at command time.

All state lives under a per-session directory keyed by slug:

```
<project>/.cache/coro/<slug>/
```

CLI owns the layout; workers don't touch it. Project root is discovered by
walking up from cwd until `.cache/coro/` is found.

### Shared bookkeeping

Core identity and history. Required for any session.

| Path | Purpose |
|---|---|
| `.cache/coro/<slug>/uuid` | Stable claude session identifier, persisted before claude spawns |
| `.cache/coro/<slug>/meta` | Session metadata — model slug used at create time |
| `.cache/coro/<slug>/turns/NNN.jsonl` | Raw stream-json events per turn, written progressively |

### Orchestrator-side overlays

Orchestrator state / CLI affordances. Workers have no awareness.

| Path | Purpose |
|---|---|
| `.cache/coro/<slug>/hold` | Hold sentinel — session paused awaiting human input |
| `.cache/coro/<slug>/lock` | Fcntl exclusive lock during `coro send` — prevents concurrent sends |
| `.cache/coro/CURRENT` | Stack of **slugs** for bare-slug dispatch |

### Name resolution

Commands that take a session argument accept either a slug or a name.
Resolution rules, applied in order:

1. **Exact slug match** (directory `.cache/coro/<arg>/` exists) → use it.
2. **Name match** — find slugs where the `<name>` part (everything before
   the final `_<digits>`) equals the argument:
   - Zero matches → error (`no session matches '<name>'`).
   - One match → use it.
   - Multiple matches → **error, fail fast**. List the candidate slugs.
     Caller must specify a slug.

Ambiguity is never resolved silently — not by recency, not by "current"
state. The user disambiguates explicitly.

### Display convention

- Authoritative output (create announcement, `status` header, `turns`
  listings, log paths) shows the slug.
- Conversational output (progress lines, `list` rows, error messages) may
  show the name when unambiguous. When ambiguous, show the slug.
