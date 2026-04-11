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
| `create` | `coro create <name>` | Start a new worker session (sends preamble) |
| `send` | `coro send <name> <<< "<msg>"` | Send a message to an existing session |
| `status` | `coro status <name>` | Check the last YIELD signal |
| `turns` | `coro turns <name>` | List all turns with cost summary |
| `log` | `coro log <name> [turn]` | Inspect raw stream-json for a turn |

Stdin is the message for `send` and `create`. Use heredoc for multi-line:

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

## Session flow

### 1. Create the session

`coro create <name>` sends the protocol preamble (loaded from `protocol.md`
with `/salience on` prepended). If stdin has content, it's sent as turn 1 immediately after.

```bash
# Create only (preamble turn)
coro create phase-1

# Create + seed with initial context
coro create phase-1 < .cache/TODO/phase-1.md
```

Capture the session UUID from stderr output — it's stored automatically in
`.cache/sessions/<name>.uuid`.

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
- `BLOCKED` → read summary, resolve, send `DECIDE: <answer>`
- `FAILED` → diagnose, send `FIX: <description>`
- `RUNNING` → send `CONTINUE`
- `CHECK` → inspect the artifact, send `VERIFY: <result>`

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
