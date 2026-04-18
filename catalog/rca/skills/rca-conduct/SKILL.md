---
name: rca-conduct
description: >
  Conduct root-cause analysis of a software defect using a predict-read-verify
  scientific-method loop. Produces a cited causal chain validated by a control
  experiment. Activate with `/rca on` when investigating a defect whose
  mechanism is unknown; deactivate with `/rca off`. Requires sibling skills
  `iterative-docs` and `coro-develop`.
compatibility: >
  Hard-requires `iterative-docs` and `coro-develop` to be installed and
  available in the session. Fails loudly at activation if either is missing.
---

# Conducting Root Cause Analysis

Drive a disciplined root-cause analysis end to end. This skill is the
operational loop; it does not restate the behavioral specification. The
spec at `spec/` is authoritative — start at [`spec/README.md`](spec/README.md).

## Activation

- `/rca on` — activates; persists until deactivated.
- `/rca off` — deactivates.
- Bare `/rca` is not valid. Require explicit `on` or `off`.
- Do not self-activate. If the user describes a defect that fits RCA
  criteria (reproducible symptom, unknown mechanism) without invoking,
  offer `/rca on`; do not trigger.
- Do not mention this skill in responses while active unless the user
  is explicitly discussing it.

On activation, **before any RCA work begins**, run the dependency
check in the next section. If it fails, halt — do not proceed with
a degraded loop.

## Dependencies — hard required

This skill is built on top of two sibling skills. It **does not
reimplement** their behaviors. It invokes them at the points the spec
calls for. If either is absent, it fails loudly — it does not infer,
simulate, or degrade.

| Dependency | Used at | Purpose |
|---|---|---|
| `iterative-docs` | Stages 2, 4, 5, 8 | Scaffolding and incrementally writing the trace document and its sub-artifacts. |
| `coro-develop` | Stage 6b | Dispatching per-phase delegate reads as coroutine workers. |

### Check procedure

1. Inspect the session's available-skills list (delivered via
   system-reminder).
2. Required present: `iterative-docs` **and** `coro-develop`.
3. If either is missing, halt activation and respond to the user
   verbatim (substituting the missing skill names and catalog root):

   > RCA requires `iterative-docs` and `coro-develop`. Missing:
   > `<list>`.
   >
   > Install with:
   > ```
   > cd <catalog-root> && just install documentation/iterative-docs
   > cd <catalog-root> && just install coroutine/coro-develop
   > ```
   >
   > Re-invoke `/rca on` after install.

4. No degraded operation. No approximation. No substitute.

## How to use the spec

The full behavioral specification lives at `spec/` within this skill's
install directory. It is lossless and authoritative; this file is
operational and lossy.

Read order:

1. **On activation, before any stage work**, read in full:
   - [`spec/README.md`](spec/README.md) — E2E orientation and flow.
   - [`spec/cross-cutting.md`](spec/cross-cutting.md) — concerns that
     apply at every stage.
   - [`spec/roles.md`](spec/roles.md) — role ownership.
   - [`spec/artifacts.md`](spec/artifacts.md) — mandatory outputs.
   - [`spec/anti-patterns.md`](spec/anti-patterns.md) — failure modes.
   - [`spec/glossary.md`](spec/glossary.md) — terms of art.
   These are not on-demand. They define the posture you operate under
   for every stage. Skipping them produces a degraded loop.
2. [`spec/stage-N-*.md`](spec/) — **read in full the first time you
   enter that stage, before any stage-N action**. Each file is
   standalone. Re-read on subsequent entries only if in doubt; do not
   act from memory on first entry.

Cite the per-stage spec file when making stage-specific decisions.
Cite this SKILL.md only for operational loop decisions (what to invoke
when, how to structure delegate prompts).

Do not summarize, paraphrase, or reinterpret spec content in this
file. If the spec and this file disagree, the spec wins.

## Operational loop

One pass through eight stages per RCA. Stage 6 iterates once per
phase. Stage 7 is a posture invoked whenever a refutation fires.
Stage 8 concludes the investigation.

For each stage below: what this skill does operationally. The rules
live in the spec file cited; do not restate them.

### Stage 1 — Activate ([`spec/stage-1-activate.md`](spec/stage-1-activate.md))

Classify the defect (known/unknown mechanism). If unknown, refuse to
patch, file, or choose a workaround before the investigation. Confirm
scope with the investigator. Produce a written commitment record —
problem as stated, hypothesis as stated, decision to investigate,
scope agreed — before proceeding.

### Stage 2 — Articulate observations ([`spec/stage-2-observe.md`](spec/stage-2-observe.md))

Determine where the trace document should live:

1. Default target is `.cache/rca/<topic>/trace.md` in the
   investigator's working tree.
2. If `.cache/rca/` **already exists**, use it without asking.
3. If `.cache/rca/` **does not exist**, ask the investigator where
   traces should be recorded before creating anything. After they
   answer, ask whether that environmental convention should be
   recorded in `CONTRIBUTING.md` (or the project's equivalent
   agent-context document) so future sessions pick it up without
   re-asking. Do not edit `CONTRIBUTING.md` without explicit
   confirmation.

Invoke `iterative-docs` to scaffold the trace at the chosen path.
Populate the *Observed Symptom* section per spec — verbatim symptom
quotes, manifestation and non-manifestation tables, known unknowns,
prior hypothesis clearly labeled.

### Stage 3 — Build substrate ([`spec/stage-3-substrate.md`](spec/stage-3-substrate.md))

Decide: skip or build. Skip when the investigator and orchestrator
already have the subsystem model. Build when either signals a gap or
an attempted prediction reveals one. If build, produce the primer
inline with the investigator and append it to the trace.

### Stage 4 — Assemble sources ([`spec/stage-4-sources.md`](spec/stage-4-sources.md))

Enumerate participants and arbitrators separately. Vendor participant
code to a stable local path. Stage arbitrator specs locally. Run
`pdftotext -layout` on any PDF arbitrators so they are greppable.
Record both tables in the trace document via `iterative-docs`.

### Stage 5 — Decompose into phases ([`spec/stage-5-decompose.md`](spec/stage-5-decompose.md))

Produce the phase index table along the causal chain of the failure.
Name phases by action, not location. Identify the prime suspect phase
up front. Invoke `iterative-docs` to scaffold per-phase sections
(`Prediction` / `Findings` / `Review` / `Open questions`) in the
trace. Allow the phase list to be adjusted mid-investigation.

### Stage 6 — Per-phase loop ([`spec/stage-6-phase-loop.md`](spec/stage-6-phase-loop.md))

The core workhorse. Per phase, six steps in **strict order**:

- **6a.** Write the `Prediction` section in the trace document
  **before any source is read for this phase**. Never edit it after
  reading.

  Ground the prediction in **available context first, innate
  knowledge last**. Before writing, survey what is already on hand:
  - Environmental observations already captured (symptom quotes,
    logs, traces, manifestation tables from Stage 2).
  - Inferred behavior of the participant code — not just the slice
    directly implicated, but the surrounding code reachable from it
    (loggers, callers, config resolution, adjacent modules that
    shape runtime behavior).
  - Arbitrator text staged in Stage 4.
  - Findings and open questions from prior phases.

  Only fall back on general/innate knowledge after that surface is
  exhausted. If the prediction rests on a guess about how the system
  behaves and a reachable source could disambiguate it, the
  prediction is premature — widen the read scope in 6b instead of
  guessing. Record in the `Prediction` section which concrete
  sources grounded the prediction and which claims are innate
  fallback; the latter are first-class candidates for refutation.
- **6b.** Invoke `coro-develop` with the phase TODO. Use the
  delegation template below.
- **6c.** Receive the findings report. Check format: citations on
  every non-trivial claim, divergences-from-prediction called out
  explicitly, open questions tagged with `raised-in` / `likely-
  answered-in`. If any are missing, send back for revision.
- **6d.** Verify load-bearing citations directly. Open the cited
  files; confirm the quoted content matches. **Never delegated.**
- **6e.** Update the working model. Propagate findings into the next
  phase's prediction and the cross-phase open-questions register.
- **6f.** Append new open questions to the register with their tags.

At the phase boundary, report to the investigator: progress, any
refutations surfaced, the revised hypothesis, and the phase cost
(from `coro-develop`'s turn summary).

### Stage 7 — Refutations ([`spec/stage-7-refutation.md`](spec/stage-7-refutation.md))

When a phase's findings contradict a working hypothesis: record the
refutation in the trace (refuted claim, refuting evidence, revised
model, propagation). Do not delete the refuted hypothesis. Escalate
to the investigator at the phase boundary before dispatching the
next phase. Continue with the revised model on the investigator's
ratification; re-scope only on their direction.

### Stage 8 — Validate with control experiment ([`spec/stage-8-validate.md`](spec/stage-8-validate.md))

Design the experiment **in the trace before running it**: what is
measured, what confirms the hypothesis, what refutes it, which
alternative explanations would survive a pass. Include at least one
unfixed control. Execute. Record raw observations — not summaries.
Build the predicted-vs-observed comparison.

- On match: write the conclusions section in the trace; stop.
- On mismatch: the hypothesis is wrong or incomplete. Record a new
  refutation; return to Stage 7.

## Delegation template

At Stage 6b, create a `coro-develop` session for the phase and send
the TODO in this structure. Follow `coro-develop`'s protocol for
session lifecycle (create, send, interpret YIELD, resume). This
template specifies the RCA-specific content, not the coroutine
mechanics.

```
Phase N — <short name>

Scope: <start handoff> -> <end handoff>. Do not cross these boundaries.

Participant sources to read (paths relative to the investigator's project):
- <path>: <specific files, functions, line ranges>
- <path>: ...
(Include adjacent sources reachable from the suspected slice when
they shape runtime behavior — loggers, callers, config resolution,
adjacent modules — not only the lines most obviously implicated.)

Arbitrators applicable to this phase:
- <spec-id>: <sections>
- <spec-id>: ...

Prediction (written by orchestrator - do not modify):
<paste the full Prediction block verbatim from the trace document>

Verification questions:
1. <specific, cite-able question>
2. <specific, cite-able question>
...

Report format (required):
- Findings: numbered list. Every non-trivial claim cites `file:line-range`
  or `<spec-id> section <section>`.
- Divergences from prediction: a separate subsection. Call out each
  explicitly.
- Open questions for later phases: tagged as
  `raised in phase N, likely answered in phase M`.

Deliver: a single markdown response. End with `YIELD: DONE`.
```

Notes on using the template:

- Do not embed orchestrator reasoning or preferred conclusions in the
  TODO. The coroutine conditions on what the TODO contains; intent
  beyond the prediction is not to be inferred.
- One phase per coroutine session. If a phase was merged or split
  during Stage 5 adjustment, the session corresponds to the merged
  or split unit.
- Cite this SKILL.md only for the template structure. Cite
  `spec/stage-6-phase-loop.md` for the behavioral rules the template
  implements.

## Invariants

Non-negotiable rules while this skill is active. Violating any of
these means the output is not an RCA under this specification.

- Predictions are written before reading for the phase, never after.
- Predictions are grounded in available context (observations, prior
  findings, reachable participant code, arbitrators) before innate
  knowledge. Innate-knowledge claims are labeled as such.
- Every non-trivial claim has provenance (`file:line-range` or
  `<spec-id> section <section>`).
- Load-bearing citations are verified by the orchestrator directly.
  Verification is never delegated.
- Refuted hypotheses are preserved in the trace. They are never
  deleted or silently dropped.
- No completion without a Stage 8 control experiment that passed.
- No inference, simulation, or approximation of missing dependencies.
- Direction-changing refutations escalate to the investigator before
  proceeding to the next phase.

## Will not

Scope boundaries. This skill does **not**:

- Write patches, fixes, or code changes. The fix is identified in
  Stage 8's output; authoring and applying it is separate work.
- File the RCA output to external trackers (GitHub, GitLab, mailing
  lists, etc.).
- Archive the RCA into bug-reports or similar repositories.
- Redact sensitive data. The investigator is responsible for
  collection-time discipline.
- Generalize findings beyond the control experiment's verified scope.
- Proactively run RCAs on defects the user has not asked about.
- Substitute its own judgment for the investigator's on halt, stop,
  or scope decisions.
- Continue past the answered question.

## Completion criteria

The RCA is complete when **all** of:

- Stage 8's control experiment passed (predictions matched
  observations, recorded in the trace).
- Every claim in the trace document has provenance.
- The open-questions register is up to date.
- The investigator ratifies completion.

On completion, summarize to the user:

- The surviving causal chain, stated once in plain language.
- The proposed fix (if any) with its location.
- The scope of the conclusion — which environments, versions, and
  configurations it covers, and which it does not.

Then stop. Do not proceed into handoff, filing, or archival — those
are out of scope per the `Will not` section and per
[`spec/README.md`](spec/README.md).
