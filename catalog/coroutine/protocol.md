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
<project>/.cache/turns/<name>-NNN.jsonl # raw stream-json per turn
```

Project root is discovered by walking up from cwd until `.cache/sessions/`
is found.
