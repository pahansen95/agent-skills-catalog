# RCA — Specification

> High-order overview of the Root Cause Analysis behavioral
> specification. Lossy by design; the lossless per-stage references
> are in the sibling files. Read this first for orientation, then
> open the relevant stage file when you need the full rules.

## Purpose & Scope

This specification defines a disciplined approach to Root Cause
Analysis. RCA here means **source-level investigation of a specific
observed defect**: the defect has a reproducible symptom in a known
system, and the investigation's output is a causal chain —
observation to mechanism — with every non-trivial claim cited to a
primary source. A proposed fix is a byproduct; the goal is the
explanation.

The specification is written for two audiences: a human developer
conducting RCA manually, and an agent orchestrator applying this
as a skill. Both operate under the same rules.

**In scope.** Eight stages and a set of cross-cutting concerns. The
stages run roughly in order; the concerns apply throughout.

**Out of scope.** Handoff of the RCA's output to external systems
(upstream trackers, bug-report repositories, downstream teams). This
specification ends when the causal explanation is complete and
validated. Archival is a separate concern and a separate skill.

## Philosophy

RCA as defined here produces a **causal explanation with provenance**,
not a working system. The output is scientific — a claim about why a
defect occurs, supported by evidence anyone can independently verify.

A fix is a byproduct. If the explanation is correct and complete, the
fix falls out of it naturally; if no fix falls out, the explanation is
not complete. This is the test for whether you have done RCA or
something that resembles it.

The discipline is scientific method applied to a software system:
observe, hypothesize, predict, test, refute or confirm, iterate, then
validate with a control experiment the investigation itself cannot
produce.

Three claims shape everything else:

1. **Hypotheses are disposable; the trace is not.** A good RCA
   discards multiple hypotheses along the way. The record of that
   disposal — what was tried, what refuted it, what survived — is the
   artifact of value. The final hypothesis without the refutations is
   a guess; the final hypothesis plus the refutations is a conclusion.

2. **Provenance is the boundary between investigation and gossip.**
   Any claim without a source citation is not part of the RCA — it is
   commentary. An investigation whose claims are not independently
   verifiable is indistinguishable from confident invention.

3. **The orchestrator thinks; delegates read.** Prediction and
   verification are cognitive work; the investigator cannot outsource
   them and still call the result their RCA. Reading source code,
   running commands, extracting quotes — these are mechanical.
   Delegate them freely. Do not delegate the reasoning that decides
   what to read next or whether what was read confirms what was
   predicted.

If any of these three claims fails for your investigation, you are
producing something adjacent to RCA, not RCA.

## Dependencies

This specification is operationalized through two sibling skills in
the catalog. Skills applying this spec **declare these as hard
dependencies**:

| Dependency | Used for |
|---|---|
| `iterative-docs` | Writing the trace document — a long, structured, incremental artifact that grows section by section. |
| `coro-develop` | Dispatching phase delegates (Stage 6b) as coroutine workers when the orchestrator parallelizes or protects its context. |

A skill implementing this specification **must not** reimplement the
behaviors those skills encode. It must check for their availability
at activation and fail loudly if either is missing. Silent fallback
to approximations is a spec violation.

## Roles

Four roles appear. One actor often occupies several; the roles are
distinct functions, not distinct entities.

- **Investigator** — principal driving the RCA. Owns the question,
  scope, and start/halt/stop decisions.
- **Orchestrator** — agent doing prediction and verification. Owns
  the trace document and the per-phase loop. May be the same actor
  as the investigator.
- **Delegate** — sub-agent or tool that reads bounded source material
  on the orchestrator's behalf. Optional.
- **Arbitrator-authors** — authors of normative specifications. Not a
  role in the process; present via their documents.

Full ownership table and descriptions: [`roles.md`](roles.md).

## Cross-cutting concerns

These apply to every stage. Read them before the stages — they are
preconditions, not appendices.

- **Provenance discipline.** Every non-trivial claim cites a primary
  source. Uncited claims are commentary, not evidence.
- **Prediction vs reading.** The orchestrator predicts and verifies;
  delegates read. Never inverted.
- **Halting on direction-changing evidence.** Refutations that
  invalidate load-bearing assumptions escalate to the investigator
  before the next phase.
- **Stop condition.** The RCA ends when the investigator's question
  is answered. Not before. Not after.
- **Compute budget awareness.** Track delegate cost at phase
  boundaries; do not let it override correctness.
- **Refutation as progress.** A refuted hypothesis is information.
  Preserve it in the trace; update the model; continue.

Lossless reference: [`cross-cutting.md`](cross-cutting.md).

## End-to-end flow

The eight stages run roughly in sequence. Stages 1–5 are executed
once per RCA; Stage 6 runs once per phase; Stage 7 is an ongoing
posture invoked whenever a refutation fires; Stage 8 concludes the
investigation.

### Stage 1 — Activate

Decide whether to conduct an RCA at all. Refuse to act on the stated
hypothesis until the causal chain is understood. Surface the refusal
to the investigator and confirm scope.

**Goes to:** [`stage-1-activate.md`](stage-1-activate.md).

### Stage 2 — Articulate observations

Produce a precise, hypothesis-free statement of the symptom and the
conditions under which it does and does not manifest. The
non-manifestation conditions are often the most discriminating
evidence in the investigation.

**Goes to:** [`stage-2-observe.md`](stage-2-observe.md).

### Stage 3 — Build substrate mental model

If the investigator lacks the architectural model needed to read the
trace, build it bottom-up before the first phase that needs it.
Anchor every concept introduced to the defect. Skip when the model
is already in hand.

**Goes to:** [`stage-3-substrate.md`](stage-3-substrate.md).

### Stage 4 — Assemble sources

Identify participants (code that executes during the failure) and
arbitrators (specs that adjudicate correctness). Vendor them locally.
Record both in a table. Keep the distinction sharp: code does not
specify; specs do not execute.

**Goes to:** [`stage-4-sources.md`](stage-4-sources.md).

### Stage 5 — Decompose into phases

Partition the investigation into a sequence of bounded, citeable
subproblems along the causal chain. Boundaries sit at natural
handoffs — syscall returns, traps, branches to new context. Name
phases by action, not location. Allow merging and splitting as
evidence accumulates.

**Goes to:** [`stage-5-decompose.md`](stage-5-decompose.md).

### Stage 6 — Per-phase loop

The core workhorse, run once per phase:

```
predict → delegate read → receive findings →
verify provenance → update model → carry questions
```

The prediction is written in user-visible text before reading begins
and is not retroactively edited. Provenance is verified by the
orchestrator, never delegated. Divergences from prediction are
flagged explicitly.

**Goes to:** [`stage-6-phase-loop.md`](stage-6-phase-loop.md).

### Stage 7 — Refutations as progress

Whenever a phase's findings contradict a working hypothesis, record
the refutation in the trace, propagate the revised model, and
escalate to the investigator. Do not delete the refuted hypothesis;
do not restart the investigation. The code path is unchanged; only
interpretation is.

**Goes to:** [`stage-7-refutation.md`](stage-7-refutation.md).

### Stage 8 — Validate with a control experiment

Design the experiment before running it, with explicit predictions
and at least one control. Execute. Compare observations to
predictions. If they match, the hypothesis survives; if not, return
to Stage 7. The experiment is the external falsification the trace
alone cannot produce.

**Goes to:** [`stage-8-validate.md`](stage-8-validate.md).

## Artifacts

An RCA produces four mandatory artifacts:

| Artifact | Role |
|---|---|
| Trace document | Primary output: scope, sources, phase index, per-phase sections, refutation log, conclusions. |
| Open-questions register | Cross-phase table of unresolved questions with status. |
| Control experiment record | Stage 8 output: design, observations, predicted-vs-observed table, conclusion with scope. |
| Conclusions section | Concise restatement of the surviving causal chain, cited back to phases. |

Lossless reference: [`artifacts.md`](artifacts.md).

## Anti-patterns

Twenty-plus enumerated failure modes, each tied to a stage or
cross-cutting concern that would have prevented it. Examples:
performative investigation, uncited claims, trusting delegate
reports without verification, designing the experiment after running
it, continuing past the answered question.

Lossless reference: [`anti-patterns.md`](anti-patterns.md).

## Glossary

Terms defined by this specification: *Investigator, Orchestrator,
Delegate, Arbitrator, Participant, Phase, Prediction, Finding,
Divergence, Refutation, Substrate, Control matrix, Provenance,
Trace document.*

Lossless reference: [`glossary.md`](glossary.md).

## Worked example

All stage examples are extracted from a single real investigation: a
multi-vCPU kexec failure under QEMU+HVF on Apple Silicon. Symptom was
`"CPU N: failed to come online"`; actual root cause was a missing
`vcpu_dirty = true` in QEMU's `arm_set_cpu_on_async_work`; fix was
one line; validation was a 2×2 control matrix across build paths and
patch states.

Summary and stage-by-stage example index: [`worked-example.md`](worked-example.md).

## How to read this specification

- **First encounter.** Read this README end-to-end. You have the arc
  of RCA, the roles, the concerns, the eight stages in outline, and
  the dependency posture.
- **Executing a specific stage.** Open that stage's file directly.
  It is lossless on its own terms; you do not need to re-read the
  rest of the spec to apply it.
- **Resolving a question about a concern.** Open
  [`cross-cutting.md`](cross-cutting.md); all six concerns are there.
- **Citing the spec from a skill or document.** Cite the
  per-stage file — it is the authoritative source. This README is a
  lossy overview and may omit details.
