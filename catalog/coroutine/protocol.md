# Coroutine Protocol

The wire-level specification for orchestrator ↔ worker communication.

## Roles

**Orchestrator** — the primary agent session. Drives the worker. Interprets
results. Decides next action. Escalates to the human when blocked on decisions
only they can make.

**Worker** — a dedicated agent session scoped to one phase of work. Implements,
tests, and reports. Has no awareness of other phases or the broader project.

## Worker output contract

Every worker response ends with a YIELD signal as its last line:

```
YIELD: <STATUS> | <summary>
```

### Status values

The following YIELD statuses are what the worker may emit while in the WORKING
state. Each emission triggers a transition in the Worker FSM (see below) and a
corresponding response from the orchestrator.

| Status | Meaning | Orchestrator action |
|---|---|---|
| `DONE` | Work complete or ready for next instruction | Send next instruction or declare phase complete |
| `BLOCKED` | Cannot proceed — needs a decision | Read summary, decide, send `DECIDE: <answer>` |
| `FAILED` | Something broke — details in summary | Read error, send `FIX: <description>` or escalate |
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

The worker operates as a mechanical state machine. States reflect runtime
observables (message received, YIELD emitted), not semantic intent.

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

The orchestrator maintains one FSM instance per managed worker session. States
reflect what the orchestrator observes and what action it is taking.

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

Overlays are out-of-band session state managed by the orchestrator. They do
not affect the worker's YIELD vocabulary or FSM. Workers have no awareness
of overlays; they are purely an orchestrator-side mechanism.

### Hold sentinel

**File**: `.cache/sessions/<name>.hold`

**Format**: first line is the optional reason string (may be empty); second
line is an ISO-8601 UTC timestamp written at hold time (useful for diagnosing
stale holds).

**Who writes it**: the orchestrator, via `coro hold <name> [<reason>]`.
**Who reads it**: `coro status` (non-destructively) and `coro send` (clears
it before acquiring the send lock).

- `coro hold` writes idempotently (overwrites if already held).
- `coro unhold` removes the sentinel; no error if absent.
- `coro send` auto-clears the sentinel before the send lock is acquired and
  emits a stderr note: `note: cleared hold on session '<name>' (reason: ...)`.
- `coro status` surfaces hold state on a `hold:` line in its output block.

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

**CREATE** — first invocation. Orchestrator sends the protocol preamble
(this file, loaded by the tool at runtime) then the phase scope and initial
instruction. Session UUID is captured and stored for resume.

**YIELD loop** — each subsequent turn: orchestrator reads YIELD signal,
decides next message, sends via `--resume <uuid>`.

**COMPLETE** — orchestrator declares phase done when all success criteria met.

## Orchestrator turn logic

```
output = send(session, message)
signal = parse_yield(output)   # last line: "YIELD: STATUS | summary"

match signal.status:
  DONE    → send next instruction OR declare phase complete
  BLOCKED → formulate decision → send "DECIDE: <answer>"
            if human input needed: run "coro hold <name> '<reason>'" and stop
  FAILED  → diagnose → send "FIX: <description>" OR escalate to human
  RUNNING → send "CONTINUE"
  CHECK   → inspect artifact → send "VERIFY: <result>"
```

Human escalation: surface to the human when BLOCKED on questions requiring
their input (credentials, design decisions, infrastructure access).

## Session storage

```
<project>/.cache/sessions/<name>.uuid    # session UUID
<project>/.cache/sessions/<name>.meta   # model used
<project>/.cache/sessions/<name>.hold   # hold sentinel (orchestrator-only)
<project>/.cache/turns/<name>-NNN.jsonl # raw stream-json per turn
```

Project root is discovered by walking up from cwd until `.cache/sessions/`
is found.
