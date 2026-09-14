# Claude connection and evidence

Coordinator sessions keep one Claude stream open behind a local authenticated
frontend. `create` and `send` return submission acknowledgments; `status` reports
the current response, last automatic completion report and observed tasks. These acknowledgments are not YIELD or
artifact acceptance. Use `log` to inspect full events, including automatic task
notifications. Logs group events by the primary turn active when they arrive.

```sh
export CORO_PROJECT=/path/to/project
export CORO_CLAUDE=/path/to/working/claude
export CORO_MODEL=claude-fable-5-1
export CORO_EFFORT=high
# Optional: bind permissions needed by the approved phase.
export CORO_ALLOWED_TOOLS='["Read","Write","Skill","Workflow"]'
/path/to/scripts/coro create phase
/path/to/scripts/coro status phase
/path/to/scripts/coro send phase < kickoff.md
/path/to/scripts/coro log phase
```

Send after the previous primary response ends. Workers may remain active. Correct
missing/malformed YIELD with a focused message; never infer acceptance from it.
The frontend denies interactive permission requests. The configured Claude
permissions and caller environment otherwise apply; tool patterns are permission
grants, not a replacement for file ownership in the approved plan.

Connection settings are saved at creation. Model aliases `fable`/`best`, `opus`,
`sonnet` and `haiku` resolve to pinned IDs for new coordinators. Capability baselines
live in `scripts/models.ts`; observed runtime limits take precedence. `cost` values
there are local warning thresholds, not token prices. Process budget caps restart
with a new process; they are not cumulative phase budgets.

`CORO_PERSISTENCE=native` is the default. Reconnection uses Claude's saved session.
Use `journal` where native transcript storage is unavailable: after restart, prior
requests and visible responses are supplied as history. Neither mode restores
interrupted workers. A live connection keeps full cross-turn context in either mode. Native recovery
requires a transcript available to the configured Claude connection; a successful
live turn alone does not prove it exists. A missing native transcript is an error,
never an automatic fallback. After shutdown and task reconciliation, select the
fallback explicitly:

```sh
coro persistence phase journal
coro unhold phase
coro send phase < recovery-instruction.md
```

```sh
coro hold phase review-required       # blocks primary submissions; active Workflow continues
coro cancel phase                     # interrupts controller/pool and sets a hold
coro cancel phase runtime-task-id     # stops that observed task; does not hold the phase
coro shutdown phase                   # cancels, closes Claude and stops the frontend
coro jobs phase
coro unhold phase                     # only after the relevant decision/resume authority
```

Cancellation receipts and task termination are reported separately. If the host
or Claude process dies, inspect `connection.json`, `pool.json`, logs and artifacts.
A still-live child prevents automatic replacement. Stop the frontend before
reconciling unknown tasks; use actual termination evidence, not an absent report.

```sh
coro reconcile phase task-id cancelled 'termination evidence reference'
coro unhold phase
coro send phase < recovery-instruction.md
```

Create attempt evidence before dispatch. The primary owns runtime records; the
coordinator can supply immutable phase-side scripts and reports for import.

```json
{
  "id": "draft-a1",
  "request": "/path/to/approved-request.md",
  "script": "/path/to/workflow.js",
  "inputs": ["/path/to/source.ts"],
  "outputs": ["/path/to/draft.md"],
  "checks": ["review assertions against the input"]
}
```

```sh
coro attempt phase < attempt.json
# Dispatch the saved script, or verify identical bytes before dispatching its source.
coro attempt-seal phase draft-a1 < result-evidence.json
coro attempt-check phase draft-a1
coro attempts phase
```

Request/script copies and their hashes are recorded once per ID. Sealing records
current output hashes and supplied result evidence once. Checks compare request,
script, input and output bytes; they do not execute check descriptions or judge
correctness. A changed dependency invalidates reuse even if output bytes match.
Retries get new IDs and can name `previous`. Callers supply task/result references
in evidence; the frontend does not automatically associate Workflow tasks with
attempts. Unknown/incomplete records remain visible.

Legacy sessions without role metadata keep foreground worker behavior.
`CORO_ROLE=worker` explicitly creates that form. It has no async control service;
its sends still use the saved Claude UUID. Holds now require explicit unhold for
both roles. No implicit permission bypass or communication skill is injected.
