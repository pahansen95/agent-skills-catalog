---
name: coro-develop
description: >
  Drive a stateful coroutine worker session turn-by-turn. Use when orchestrating
  a multi-turn implementation phase: creating a worker session, sending instructions,
  interpreting YIELD signals, enforcing quality gates, and deciding next actions.
  Activate with /coro-develop.
compatibility: Requires Python 3.13 (pyenv), uv, just, and the claude CLI in PATH
---

Drive a coroutine worker session: one turn at a time, one decision at a time.

Read [protocol.md](./protocol.md) for the complete YIELD signal vocabulary
and wire protocol before proceeding.

## Tools

All tools are exposed via the `coro` alias at `scripts/coro`. Symlink or add
it to your PATH. Run `coro setup` once before first use.

| Command | Usage | When to use |
|---|---|---|
| `setup` | `coro setup` | Once — creates venv, sets Python version |
| `create` | `coro create <name>` | Start a new worker session (sends preamble only; auto-pushes onto CURRENT) |
| `send` | `coro send [<name>] <<< "<msg>"` | Send a message (bare form targets CURRENT top) |
| `status` | `coro status [<name>]` | Check last YIELD signal + in-flight send state |
| `turns` | `coro turns [<name>]` | List all turns with cost summary |
| `log` | `coro log [<name>] [turn]` | Inspect raw stream-json for a turn |
| `use` | `coro use <name>` | Push a session onto the CURRENT stack |
| `pop` | `coro pop` | Pop the top of the CURRENT stack |
| `list-sessions` | `coro list-sessions` | Show the CURRENT stack, top to bottom |
| `new-phase` | `coro new-phase <slug>` | Scaffold `.cache/TODO/phase-<slug>.md` + kickoff from templates |
| `hold` | `coro hold [<name>] [<reason>]` | Mark session as awaiting human input; writes `.cache/sessions/<name>.hold` |
| `unhold` | `coro unhold [<name>]` | Clear hold sentinel on session |

**Bare-name dispatch**: `send`, `status`, `turns`, and `log` resolve to the
top of the CURRENT stack (`.cache/sessions/CURRENT`) when no name is given.
`coro create <name>` auto-pushes; `coro use <name>` pushes an existing
session; `coro pop` returns to the previous one. Explicit `<name>` always
wins and works regardless of stack state.

**Concurrency**: `coro send` holds an exclusive file lock
(`.cache/sessions/<name>.lock`) for the duration of the call. A second
concurrent `coro send <same-name>` dies immediately with a clear error.
`coro status` reports `sending: yes` while a send is in flight.

Stdin is the message for `send`. Use heredoc for multi-line:

```bash
coro send phase-1 << 'EOF'
Phase 1 scope is in .cache/TODO/phase-1.md
Review the project and report back.
EOF
```

Single-line:
```bash
coro send phase-1 <<< "CONTINUE"
```

Environment variables (set before invoking):
- `CORO_MODEL` — Claude model slug (default: `sonnet`)
- `CORO_PROJECT` — project root path (default: auto-discovered from cwd)
- `CORO_ADD_DIRS` — colon-separated extra `--add-dir` paths passed to claude
- `CORO_EFFORT` — effort level passed to claude (`low`, `medium`, `high`, `xhigh`, `max`); omit for claude's default

## Session flow

### 1. Create the session

`coro create <name>` sends the protocol preamble (loaded from `protocol.md`
with `/salience on` prepended). Send turn 1 separately via `coro send`:

```bash
coro create phase-1                                      # preamble (turn 0)
coro send phase-1 < .cache/TODO/phase-1-kickoff.md      # turn 1
```

Capture the session UUID from stderr — stored automatically in
`.cache/sessions/<name>.uuid`.

**Deprecated**: `coro create <name> < file` (preamble + turn 1 in one
invocation) still works but emits a deprecation warning to stderr. Migrate
callers to the two-step form; the inline-send path will be removed in a
future iteration.

### 2. Orient the worker

Send the phase scope and ask for an orientation report before any work begins:

```bash
coro send phase-N << 'EOF'
Phase N of a multi-phase plan. Scope is in .cache/TODO/phase-N.md
Review the project to gain your bearings. Report back what you find.
EOF
```

Wait for `YIELD: DONE | ...` before proceeding.

### 3. Request architecture proposal

Before any implementation, the worker must propose and cite vendor sources:

```bash
coro send phase-N << 'EOF'
Propose how you'll architect this phase — what you'll build, where, why &
how. Cite specific vendor source files and line numbers for non-obvious
implementation details. Do not BEGIN until architecture is approved.
EOF
```

Review the proposal. If vendor citations are absent or thin, send:

```bash
coro send phase-N << 'EOF'
Before BEGIN: read the relevant vendor source files directly and cite
specific file paths, function names, and line numbers.
EOF
```

### 4. Apply pre-BEGIN adjustments

If the proposal has deviations or issues, send them before BEGIN:

```bash
coro send phase-N << 'EOF'
Three adjustments before BEGIN:
1. <adjustment with rationale>
2. <adjustment with rationale>
3. <adjustment with rationale>

Architecture approved. BEGIN
EOF
```

### 5. Drive the implementation loop

Send `BEGIN` when ready. Then interpret each YIELD:

```bash
coro send phase-N <<< "BEGIN"
```

After each YIELD, decide:

- `DONE` → send next instruction or declare phase complete
- `BLOCKED` → read summary, resolve, send `DECIDE: <answer>`; if human input needed: `coro hold <name> '<reason>'` and stop polling
- `FAILED` → diagnose, send `FIX: <description>`
- `RUNNING` → send `CONTINUE`
- `CHECK` → inspect the artifact, send `VERIFY: <result>`

### Multi-commit phase discipline

When a phase will produce more than one logical commit, the worker MUST emit
`YIELD: CHECK | <commit summary>` after each commit. The orchestrator inspects
the diff and replies `VERIFY: ok` (or `VERIFY: <issue>`) before the worker
proceeds to the next commit.

Why: combining multiple commits in a single turn inflates context and cost
(Phase E of the Views refactor cost $24 in one turn for exactly this reason).
Per-commit checkpoints keep turn cost predictable and make scope creep visible
immediately.

Single-commit phases (most protocol additions, doc-only changes) need not
checkpoint — the final `YIELD: DONE` is the checkpoint.

The orchestrator should require a commit-count estimate during architecture
review and use it to decide whether to enforce per-commit CHECK gates
pre-BEGIN.

### Polling discipline

When driving a coroutine via recurring checks (cron, loop skill, etc.):

- If `coro status` reports `hold: yes`, **skip the tick entirely**. No log
  read, no turn. Resume by sending the next message (`coro send` auto-clears
  the hold sentinel).
- If the last YIELD is `BLOCKED` with a summary the orchestrator can resolve
  (e.g., "need decision on X" where X is a local/technical call), read the
  turn and send `DECIDE:`.
- If the last YIELD is `BLOCKED` with a summary requiring human input
  (credentials, design decision, infrastructure access), run
  `coro hold <name> '<reason>'` and stop polling. Report the blockage to the
  human. Resume is always explicit: `coro send <name>` auto-clears the hold.

The skill reports state; it does not enforce polling cadence. The discipline
is yours to apply.

### Scaffolding new phases

`coro new-phase <slug>` creates `.cache/TODO/phase-<slug>.md` and
`.cache/TODO/phase-<slug>-kickoff.md` from the shipped templates. Fill in
the placeholder sections, then proceed with `coro create` + `coro send`.
Use `--force` to overwrite existing files.

### 6. Integration tests

After unit tests pass, instruct the worker to run integration tests in the
appropriate runtime environment. Specify what tools are available, where VMs
are, and what success looks like.

### 7. Declare complete

When all success criteria from the phase TODO are met:

```bash
coro status phase-N   # confirm last YIELD is DONE
coro turns phase-N    # review cost summary
```

## Quality gates

These must be enforced before `BEGIN` on every phase:

**Vendor citations** — the worker must cite specific file paths and line
numbers from vendored source projects for all non-obvious implementation
details. Architecture proposals that reason from memory are not acceptable.

**Architecture review** — the orchestrator (you) must read and approve the
proposal before sending BEGIN. Check for: correctness against vendor source,
deviations from the phase spec, open questions that need decisions.

**Pre-BEGIN adjustments** — any corrections, decisions, or clarifications must
be sent before BEGIN, not after implementation has started.

## Human escalation

Escalate to the human when:
- BLOCKED on a question requiring their credentials, access, or design decision
- FAILED after two FIX attempts with no progress
- The worker's architecture fundamentally diverges from the project's design

State clearly: what the worker is blocked on, what you've tried, what decision
the human needs to make.

## Cost tracking

After each turn, report:
- Turn cost (from `[coroutine] turn=N cost=$X.XXXX` in stderr)
- Phase total (sum of all turns)
- Session total across all phases

Use `coro turns <name>` for a full cost breakdown per turn.

### Telemetry & thresholds

`coro status` reports per-session telemetry:

- `tokens:` — total context tokens consumed in the most recent turn (sum of
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`).
  Watch this number; nearing the model's context window means exhaustion is
  imminent and the worker should be rolled over.
- `cost:` — cumulative cost across all turns in the session.

Warnings fire to stderr when:
- Last-turn total context tokens exceed 80% of the model's context window
  (override: `CORO_TOKEN_WARN_RATIO` for fraction, or `CORO_TOKEN_WARN` for
  absolute count).
- Cumulative cost exceeds `CORO_COST_WARN` (default $25.00).

Model context windows are looked up by `CORO_MODEL` slug:
opus = 1M tokens, sonnet = 200k, haiku = 200k. Unknown models fall back to
200k with a one-line note.

The thresholds are advisory — the orchestrator decides whether to checkpoint,
rollover, or proceed.

When the token warning fires, consider:
- Sending a `YIELD: CHECK` before the next implementation turn.
- Spawning a fresh session and seeding it with a compressed handoff.

When the cost warning fires, consider:
- Reviewing recent turns via `coro turns <name>` for runaway cost.
- Pausing to re-plan if remaining work doesn't justify the spend.
