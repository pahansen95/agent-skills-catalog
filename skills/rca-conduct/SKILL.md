---
name: rca-conduct
description: >
  Conduct a source-level root-cause analysis of a reproducible software defect
  whose mechanism is unknown. Uses pre-reading predictions, cited primary-source
  findings, preserved refutations, and controlled validation. Activate only with
  `/rca on`; deactivate with `/rca off`. Requires `iterative-docs` and
  `coro-develop`.
compatibility: >
  Hard-requires `iterative-docs` and `coro-develop` to be available in the same
  session. Fails loudly at activation if either is missing.
---

# Conduct Root-Cause Analysis

Explain a specific observed software defect from symptom to mechanism. The
deliverable is an auditable causal chain, not a production fix.

## Activation and dependencies

- `/rca on` activates this workflow. `/rca off` deactivates it. A bare `/rca`
  is invalid.
- Never self-activate. If an unknown defect would benefit from this workflow,
  offer `/rca on` and wait for the user to invoke it.
- On activation, confirm that `iterative-docs` and `coro-develop` are both
  available in the session. If either is missing, name the missing dependency,
  halt activation, and ask the user to make it available. Do not approximate,
  substitute, or claim that the catalog installs or discovers it.
- The dependencies remain required even when a phase is small enough to read
  locally. Use `iterative-docs` to maintain the trace. Use `coro-develop` when
  bounded phase reading merits a coroutine worker; local reading does not
  require agent fanout.

Classify the defect before starting. A known mechanism with a known fix needs
implementation, and a known mechanism without a fix needs engineering; neither
needs RCA. Continue only when the mechanism is unknown and the symptom is
specific enough to investigate. Record the user's question, stated hypothesis,
decision to investigate, and scope. Ask for scope only when the user has not
already supplied or authorized it.

## Invariants

These rules define a valid RCA:

- Write each phase's falsifiable prediction in the trace before opening new
  sources for that phase. Never rewrite it after reading. Ground it in
  observations, prior findings, already-known participant behavior, and
  arbitrators; label unsupported expectations as uncertain or innate.
- Cite every non-trivial finding to a primary source. Verify every load-bearing
  citation directly before using the claim downstream. This verification stays
  with the orchestrator.
- Preserve each refuted hypothesis, its evidence, the revised model, and its
  propagation through later reasoning.
- Stop before the next phase when evidence changes the investigation's
  direction. Present the evidence and revised options to the user, then follow
  their existing or newly stated scope decision.
- Validate the surviving mechanism against observation with a predesigned
  falsification that includes at least one unchanged control. A source-only
  explanation is incomplete.
- Stop when the user's question is answered and the completion criteria below
  hold. Leave unrelated open questions recorded rather than pursuing them.

## Workflow

The workflow has eight stages; phase work is sequential because later
predictions depend on earlier findings. Read only the relevant section of
[`references/workflow.md`](references/workflow.md) before performing that
stage:

1. [Activate and frame](references/workflow.md#1-activate-and-frame): separate
   observations from the entering hypothesis and establish scope.
2. [Articulate observations](references/workflow.md#2-articulate-observations):
   capture exact symptoms, manifestation and non-manifestation conditions, and
   known unknowns.
3. [Build substrate](references/workflow.md#3-build-substrate-when-needed): add
   only the architectural model needed to interpret the failure.
4. [Assemble sources](references/workflow.md#4-assemble-sources): distinguish
   executing participant code from normative arbitrators and pin both.
5. [Decompose](references/workflow.md#5-decompose-the-causal-chain): split the
   runtime causal chain at natural handoffs and identify the prime suspect.
6. [Investigate each phase](references/workflow.md#6-investigate-each-phase):
   predict, read, check the report, verify citations, update the model, and
   carry questions forward.
7. [Handle refutations](references/workflow.md#7-handle-refutations): preserve
   contradictions and obtain direction at material changes.
8. [Validate](references/workflow.md#8-validate-with-a-control): design and run
   an authorized controlled experiment, compare predicted and observed results,
   and state the supported scope.

When delegating a phase read, copy and fill
[`assets/phase-read-prompt.md`](assets/phase-read-prompt.md), then follow
`coro-develop` for worker lifecycle. The prediction and verification decisions
remain with the orchestrator. Read
[`references/qemu-hvf-kexec-example.md`](references/qemu-hvf-kexec-example.md)
only when a concrete end-to-end illustration would help; it is a historical
account, not evidence for another RCA.

## Trace and completion

Store the trace at an existing user-specified or project-standard location. If
none exists, ask where it belongs before creating it. Do not alter project
policy or contributor documentation merely to record that convention.

The trace contains:

- scope, exact observations, substrate if needed, and source indices;
- a phase index and, for each phase, immutable prediction, cited findings,
  orchestrator review, and open questions;
- an open-questions register and preserved refutation log;
- the control design, raw observations, predicted-versus-observed comparison,
  and conclusions.

The RCA completes only when the controlled falsification matches its written
predictions, every non-trivial evidentiary claim has provenance, every
load-bearing citation was directly verified, the open questions are current,
and the user ratifies that the original question is answered. Report the
surviving causal chain once in plain language, any proposed fix and location,
the tested environment and versions, and remaining uncertainty.

Do not apply a production fix, deploy, file externally, archive, or generalize
beyond the validated scope as part of this workflow. Stage 8 may use an
existing or user-provided intervention in an authorized, controlled test
environment; that permission does not authorize arbitrary source edits or a
production change.
