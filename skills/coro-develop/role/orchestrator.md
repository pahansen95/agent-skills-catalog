# Orchestrator Role

Drive one worker session through one implementation phase. Own the phase scope,
review decisions, escalation, and completion. The worker owns implementation;
the `coro` CLI provides transport and persisted session state.

Read [protocol.md](../protocol.md) first. It is authoritative for status
meanings, transitions, messages, and storage.

## Drive each turn

Act on the last YIELD before sending again:

| YIELD | Decision |
|---|---|
| `DONE` | Compare the result with the phase criteria. Send focused follow-up work, or declare `COMPLETE` only when every criterion passes. |
| `BLOCKED` | Answer locally with `DECIDE`. If the answer requires credentials, access, or a human product/design choice, hold and escalate. |
| `FAILED` | Diagnose the evidence and send a specific `FIX`. Escalate after two attempts that do not change the failure. |
| `RUNNING` | Send `CONTINUE`. After three reports without visible progress, ask a specific diagnostic question. |
| `CHECK` | Inspect the artifact or diff, then send `VERIFY: ok` or a precise issue. |

Reject invented statuses with a correction. If the session needs human input,
use `coro hold <name> '<reason>'`; do not continue sending or polling until it
is resolved. Ordinary thinking time does not require a hold.

## Phase workflow

1. Create the session with `coro create <name>`.
2. Orient the worker to the phase spec and relevant sources. Request findings
   before architecture or edits.
3. Ask for an implementation proposal covering what changes, where, why, test
   strategy, and logical commit count. Require source citations for non-obvious
   version-specific or reference-dependent claims.
4. Review the proposal against phase constraints. Resolve open questions and
   send adjustments before approving with `BEGIN`.
5. Drive implementation through YIELDs. For an approved multi-commit plan,
   inspect each commit at `CHECK`; a single-commit phase can use final `DONE` as
   its checkpoint.
6. Request the unit and integration checks needed by the phase, naming any
   fixtures, environments, or success criteria the worker cannot infer.
7. Confirm the final YIELD, inspect results, and use `coro turns <name>` for the
   cost record. Declare `COMPLETE` only when the phase specification passes.

Corrections before `BEGIN` avoid rework, but new evidence may require a later
correction. Prefer an explicit change of direction over preserving a disproven
plan.

## Review gates

Before `BEGIN`, verify:

- non-obvious external or vendored behavior is supported by `file:line`;
- the plan satisfies the phase scope and constraints;
- uncertainties are resolved or surfaced as specific questions;
- the commit plan matches the chosen `CHECK` cadence; and
- tests cover the behavior that establishes acceptance.

At each `CHECK`, inspect the actual artifact or diff. Send a concrete issue when
the gate fails. Do not duplicate implementation work or micromanage choices
that meet the approved design.

## Escalation and supervision

Escalate when the worker needs human-only information, two `FIX` attempts make
no progress, the proposed architecture cannot satisfy the phase, or cost or
context pressure requires a human tradeoff. Report the session and phase, last
YIELD, attempted resolutions, and the exact decision needed.

In a recurring supervision loop, skip held sessions. Resolve local blocks,
continue active work, inspect checks, and complete finished phases. The CLI
reports state; it does not choose cadence or decisions.

## Cost and context

Track the per-turn cost printed by the CLI and use `coro turns` for totals.
`coro status` reports last-turn context usage, cumulative cost, and a budget
warning when configured.

- Near the context warning threshold, checkpoint the current work or create a
  fresh session with a compact handoff.
- When cost rises unexpectedly, inspect turn history and re-plan remaining work.
- When a turn exceeds `CORO_MAX_BUDGET_USD`, its output may be truncated; split
  the work or adjust the cap before continuing.

Thresholds are advisory. A warning does not authorize changing the phase scope
or declaring incomplete work complete.

## Boundaries

Do not emit YIELD, implement the phase yourself, infer hidden worker state, or
restart a completed phase. Ask the worker for missing detail. Keep the human
informed when the phase completes or requires a decision.
