---
name: coro-develop
description: >
  Drive a persistent Claude coordinator across turns, with bounded delegated
  workers when authorized. Use for work needing proposals, asynchronous execution,
  evidence-based checkpoints, corrections or recovery.
metadata:
  version: "2.0.0"
---

# Coroutine Development

The primary owns phase intent and acceptance. A persistent Claude coroutine
coordinates approved work across turns; its worker pool executes bounded jobs.
A coordinator can finish a response while its jobs remain active.

Before use, read [protocol.md](protocol.md) and
[role/orchestrator.md](role/orchestrator.md), then run `scripts/coro --help`.
The CLI loads [role/coordinator.md](role/coordinator.md) for new coordinator
sessions. Existing sessions without role metadata remain workers; explicit
worker sessions use [role/worker.md](role/worker.md).

Bind the situation through the [phase template](templates/phase.md): objective,
context, work units, method, role/model settings, checks and delegated authority.
The [kickoff](templates/phase-kickoff.md) requests orientation and a concrete plan.
The [job template](templates/job.md) supplies a leaf worker or reviewer contract.
Templates provide slots; the task supplies its own methods, skills and evidence.

```text
bind -> orient and plan -> review -> BEGIN
-> execute and observe -> inspect evidence -> correct or accept
```

Independent workers and reviewers require authorization. Within an approved plan,
Claude may advance dependencies and bounded repairs without an extra primary
message for every job. Reserved checkpoints and scope changes return to primary.
The primary alone declares COMPLETE after required work and checks pass.

## Runtime

Requires Deno 2.9.6 or newer and a working Claude CLI connection.

`scripts/coro` uses its own Deno configuration and the selected project root.
Session transport, event logs and job observations live under `.cache/coro/`;
phase outputs live at the paths assigned by the plan. Connection settings are
explicit runtime configuration, described by CLI help and
[connection instructions](transport.md). No permission bypass is
added by the skill.

A hold blocks new primary submissions; it does not pause a running Workflow.
Releasing a hold is explicit. User stop
requires cancellation and observed termination before replacement work starts.
Transport interruption preserves evidence; unknown job activity is not permission
to retry. See the protocol for recovery and acceptance boundaries.

## Validation

```sh
deno task --config deno.json fmt
deno task --config deno.json check
deno task --config deno.json lint
deno task --config deno.json test
```

Fixture tests establish transport and bookkeeping behavior. A supported Claude
connection must also be checked with a bounded live coordinator/pool probe before
relying on its asynchronous lifecycle in a new environment.
