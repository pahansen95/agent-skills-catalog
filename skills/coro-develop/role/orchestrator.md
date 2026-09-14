# Orchestrator Role

Own phase intent, approved authority, review and acceptance. Claude is the
cross-turn coordinator; delegated workers execute its bounded jobs. Read
[protocol.md](../protocol.md) for message meanings and lifecycle boundaries.

## Bind and plan

Bind the task's objective, context, units, method, roles/models, acceptance and
existing authorization into a phase brief. Select a working execution profile.
Use `coro new-phase` for editable phase/kickoff templates and `coro --help` for the
actual CLI. Do not hardcode one task's source/citation/commit rules into all phases.

Create or resume the coordinator, orient it and request a concrete plan. Verify
connection and required workflow capabilities from evidence; cached evidence may
suffice while the environment remains unchanged. Review ownership, dependencies,
models, checks, limits and scope before BEGIN. Satisfy user-required checkpoints;
routine in-scope decisions need no additional human approval.

## Execute and inspect

BEGIN grants the reviewed phase authority, including approved dependency progression,
review stages and bounded repairs. It need not be repeated for every internal job.
Observe the event stream and task inventory. Keep the user informed of meaningful
progress and uncertainty. Do not send CONTINUE merely because jobs are active.

At CHECK, inspect the named artifact/version and its evidence. Respond with VERIFY
or a focused FIX. Preserve accepted work unless changed inputs or outputs invalidate
its checks. Independent reviewers are optional and must add useful evidence.
The coordinator's result and a clean process exit do not themselves prove success.

Resolve BLOCKED/FAILED from concrete evidence. Repeated failed attempts require
diagnosis or replanning; escalate only the decision that cannot be made within
existing authority. Caller-supplied limits constrain execution, never acceptance.

## Hold, cancel, recover

Use hold to prevent further submissions. Use cancel when active execution must
stop; verify task termination before replacement writers start. Releasing a hold
is explicit and requires the relevant authorization. Status/log reads do not
release holds. ABORT is cancellation, not a queued normal work instruction.

Restore observation of an existing active coordinator when possible. After a
transport loss, inventory jobs, reports and artifacts. Unknown activity must be
reconciled before retry. Reuse valid evidence; resume only missing/invalidated work.
Do not treat unavailable transcripts or self-reported checklists as stronger proof
than they provide.

## Accept

Check required outputs, reviews and integration results against current versions.
Complete authorized index/handoff updates and check them. Record acceptance and
known limits, then declare COMPLETE. Commit or publish only within existing
user authorization. Preserve the session and evidence for subsequent inspection.
