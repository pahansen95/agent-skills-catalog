# Coroutine Protocol

## Actors and authority

The primary owns the phase brief, approval, checkpoints and acceptance. The Claude
coordinator owns planning, dispatch and aggregation within that approval. A worker
owns one job and its evidence; a reviewer owns findings without editing the reviewed
output. Further delegation is allowed only where the approved plan says so.

BEGIN approves a concrete plan and its bounded execution authority. Dependencies,
review stages and repairs inside that authority need no additional BEGIN per job.
Changes to scope, models, write ownership or a reserved checkpoint return to primary.
A worker result, a coordinator response, an idle pool and phase acceptance are
separate events.

## Messages and turn boundaries

Ordinary coordinator responses end with one final line:

```text
YIELD: <DONE | BLOCKED | FAILED | RUNNING | CHECK> | <actionable summary>
```

| Signal | Meaning | Primary action |
|---|---|---|
| DONE | This instruction ended. | Inspect outstanding work before giving another instruction or accepting. |
| RUNNING | Work remains; name active jobs or explain the next required turn. | Observe active jobs; CONTINUE only when coordination needs another turn. |
| CHECK | A named plan or output version awaits inspection. | VERIFY the artifact and its evidence. |
| BLOCKED | A decision or required capability is missing. | DECIDE locally or hold and ask for the specific missing authority/input. |
| FAILED | Execution failed; evidence and remaining activity are identified. | Diagnose and FIX within scope, or escalate. |

Primary messages are free-form instructions plus BEGIN, CONTINUE, FIX, DECIDE,
VERIFY and ABORT. FIX can authorize a bounded repair within the approved phase.
VERIFY approves or rejects the identified checkpoint; an approved plan begins
with BEGIN. ABORT cancels the phase; it is not an ordinary queued work message.
STATUS is not a YIELD signal. Leaf jobs can return structured results instead of
an additional conversational YIELD.

## Independent lifecycles

```text
coordinator turn: idle -> responding -> idle
job attempt:     submitted -> running -> completed | failed | cancelled | unknown
phase:           planning -> approved/working -> checkpoint or held -> accepted | aborted
```

A responding coordinator may have active jobs; an idle coordinator may also have
active jobs. RUNNING never implies automatic resubmission. Observation and
cancellation must remain available during execution. A new controller instruction
is serialized against other controller instructions, not against the lifetime of
its worker pool.

Workflow may expose one aggregate runtime task rather than every leaf job.
Only observed task IDs enter the runtime pool; leaf results remain phase evidence.
The runtime records observed task lifecycle separately from the primary's phase
judgment. `completed` means that execution returned, not that an artifact is
correct. A partial report is not a checkpoint. Missing termination evidence leaves
an interrupted job `unknown`, not successful or safely retryable.

## Jobs, attempts and evidence

A phase binds objective, inputs/revisions, work units/dependencies, worker method,
role models/efforts, ownership, checks and authority. Each job receives only the
context and permissions it needs. One writer owns each mutable output at a time;
parallel work requires disjoint ownership or suitable isolation.

Each dispatch has a stable attempt ID, its approved request and exact workflow
script when applicable. These are recorded before execution and never overwritten.
A retry gets a new attempt; it links its predecessor and reuses accepted evidence
only where inputs and outputs remain valid.

A job result identifies its job/attempt, input revisions, output paths and versions,
checks with coverage and evidence, findings, and unresolved limitations. A reviewer
names the output version it inspected. The coordinator aggregates missing and
failed jobs explicitly. The primary records acceptance against those versions;
a changed dependency can invalidate unchanged downstream files.

Workflow tools supply execution. The CLI records tasks and attempts; it does not
invent a second scheduler or decide whether source claims/tests prove acceptance.

## Persistence and transport

Sessions use `<name>_<unix-seconds>` slugs and stable logical UUIDs. Bare commands
select the top of CURRENT; an explicit slug or unambiguous name takes precedence.
Session storage is runtime-owned; leaf workers do not manipulate it.

```text
.cache/coro/
  CURRENT
  <slug>/
    uuid, meta                # identity, role and connection settings
    turns/NNN.jsonl            # observed Claude events
    requests/NNN.json          # submitted primary instruction
    hold                      # explicit hold reason and timestamp
    lock, service.lock        # worker send / coordinator lifetime ownership
    service.json              # local frontend endpoint while active
    connection.json           # child PID and last observed connection state
    pool.json                 # observed task lifecycle
    attempts/<id>/            # immutable request/script and result references
```

New sessions use the coordinator role. Legacy metadata without a role means worker;
resumption never silently changes that role. Legacy worker sends retain the
foreground request/response connection. Coordinator sessions use an open streaming
Claude process behind a local frontend. The frontend accepts bounded submissions
and exposes progress while jobs run.

Native Claude persistence can resume conversation state. With native persistence
disabled, the skill restores a logical session from its recorded requests and
visible responses; files and approved phase context remain authoritative. It does
not claim restoration of hidden model state or interrupted workers.

## Holds, stop and recovery

`hold` prevents new work submissions until explicit `unhold`; it does not by itself
kill active work or pause its internal dependency progression. When a hold requires
active work to stop, cancel and observe
termination as well. A rejected send does not clear a hold.

Cancellation uses the transport's control channel, not a second overlapping Claude
process. A receipt alone is insufficient when child-task termination remains
unknown. Shutdown records unresolved activity; a lost connection cannot convert
that activity to cancelled by assumption.

```text
on interruption:
  restore observation of a still-active service when possible
  inventory runtime tasks and persisted evidence
  confirm termination before overlapping replacement work
  reconcile unknown jobs with runtime/source evidence
  retry only unfinished or invalidated work under approved authority

on completion:
  primary checks required outputs, reviews and integration evidence
  perform authorized finishing updates and check their effects
  record acceptance and limits; declare COMPLETE
```

No COMPLETE command automatically judges evidence. Holds, primary decisions and
artifact acceptance are intentionally distinct from runtime task state. User stop
prevents further dispatch until the user resumes.
