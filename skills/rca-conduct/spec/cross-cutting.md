# Cross-cutting concerns

> Lossless reference. Read as a companion to [`README.md`](README.md).

These concerns apply to every stage. Read them before the stages; they
are preconditions, not appendices.

## Provenance discipline

Every non-trivial claim in the RCA cites a primary source. Citations are
specific enough that a reader can locate the cited material without
further search.

Required citation forms:

- **Source code:** `file:line-range` or `file:function-name`. Prefer
  line ranges for snippets longer than one line; a single line is
  acceptable when you quote the line.
- **Specifications:** `<spec-id> § <section>` and page number when the
  source is a PDF. If the spec is versioned, include the version.
- **Disassembly:** address + instruction mnemonic + symbol name.
- **Logs and serial output:** file path + line number, plus a timestamp
  or sequence marker.

A claim without a citation is not part of the RCA. It may appear in the
trace document as *investigator commentary* if explicitly marked as
such, but it carries no evidentiary weight and does not support
conclusions.

Citations are checked, not trusted. The orchestrator verifies at least
the load-bearing citations directly — opens the cited file, reads the
cited lines, confirms the claim matches. Verification happens after the
claim is made, before the claim propagates into later phases. See
[Stage 6](stage-6-phase-loop.md) for the mechanism.

## Prediction vs reading — who does what

The orchestrator predicts. The orchestrator verifies. The orchestrator
does not read unbounded source.

The orchestrator writes, in user-visible text before any reading occurs
for a phase, the expected causal chain — function names, call order,
return values, state transitions. The prediction is falsifiable: if it
is vague enough that any finding could be said to match, it is not a
prediction.

The delegate (coroutine, sub-agent, or the orchestrator itself acting in
a reader capacity) then performs the reading: locating source files,
extracting snippets, assembling the actual causal chain with citations,
and producing a findings document that flags divergences from the
prediction explicitly.

The orchestrator receives the findings, verifies the load-bearing
citations, and updates the working model.

The separation is not a productivity optimization. It is a bias
discipline. Readers who know what they expect to find tend to find it;
predictors who have not yet read the source are not yet biased by it.

## Halting on direction-changing evidence

When a phase surfaces evidence that would invalidate a load-bearing
assumption of the investigation — a refuted mechanism, a reclassified
failure mode, a new candidate bug location — the orchestrator halts
before the next phase and escalates to the investigator.

Halt means: finish writing the current phase's findings, do not dispatch
the next phase's delegate, present the divergence to the investigator
with the data that produced it.

The investigator decides whether to:

- **Continue** with a revised model. Usually correct; the phases were
  decomposed from the code path, which the refutation typically does
  not change (only interpretation does).
- **Re-scope.** Expand or contract the phase list if the refutation
  reshapes the failure's surface.
- **Abort.** The defect was not what was thought; a new RCA begins.

The orchestrator does not make this decision unilaterally. Small
divergences — citation corrections, tightening of a phase boundary, a
predicted function name being slightly different — are resolved inline
without a halt. Direction-changing divergences are not.

## Stop condition — question answered, not system fully understood

The RCA ends when the investigator's original question is answered to
their satisfaction. It does not end when every subsystem touched has
been fully characterized.

Concretely: the investigation stops when the causal chain from symptom
to mechanism is complete, every claim along the chain is cited, and a
control experiment has confirmed the mechanism's predictive power. Open
questions that are not on that chain remain open — recorded in the
open-questions register, not investigated further.

Stopping is the orchestrator's suggestion; the investigator ratifies.
If the orchestrator believes the explanation is complete and the
investigator disagrees, surface the gap and continue.

Do not stop *before* completeness because the investigation is long.
Do not continue *past* completeness because the investigation is
interesting. Neither effort-based nor curiosity-based stop criteria
apply.

## Compute budget awareness

Delegating reading to agents has a non-trivial per-turn cost. The
orchestrator tracks cost when a budget is relevant and reports it at
phase boundaries. A phase that costs more than expected is a signal —
possibly of an overbroad prompt, possibly of genuinely deep source
material.

Cost awareness does not override correctness. If a phase requires deep
investigation to produce cited findings, the investigation is done
deeply regardless of cost. The discipline is visibility: the
investigator can see what the RCA costs and redirect if needed.

## Refutation as progress

A hypothesis refuted by a phase is a positive outcome. The investigation
has eliminated a candidate and narrowed the search space. The trace
document preserves the refuted hypothesis, the phase that refuted it,
and the revised model.

Treat refutations as expected events, not failures. Do not delete
refuted hypotheses from the trace — they are the evidence that the
surviving hypothesis was selected on merit. An RCA that never refutes
anything is either solving a trivial problem or selection-biased.
