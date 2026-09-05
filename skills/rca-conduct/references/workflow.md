# RCA workflow reference

`SKILL.md` owns activation, global invariants, completion, and authorization
boundaries. This reference owns stage procedure. Read the operating model when
roles or terms are unclear, then read a stage section immediately before using
that stage.

## Operating model

The **investigator** owns the question, scope, start, halt, and stop decisions.
The **orchestrator** owns predictions, the trace, synthesis, direct provenance
checks, phase boundaries, and experiment design. A **delegate** is an optional
bounded reader: it can locate source, run authorized inspection commands,
extract evidence, and report, but it does not choose the next question or judge
whether a hypothesis survived. One actor may fill several roles.

A **participant** is code that executes during the failure. An **arbitrator** is
a normative specification that says what participant behavior should be; a
reference implementation may serve as comparison evidence when labeled
accurately. Participant code shows what happened and does not define what is
correct. Arbitrators define requirements and do not show what executed.

A **phase** is a bounded runtime segment between natural handoffs. Its
**prediction** is a falsifiable expected causal chain written before new source
reading. A **finding** is a primary-source-backed claim from the read. A
**divergence** is a mismatch between prediction and finding. A **refutation**
retires a working claim while preserving how and why it was retired.

Use citations that let another reader locate the evidence directly:

- source: `path:line-range` or `path:function`;
- specification: identifier, version, section, and PDF page when relevant;
- disassembly: address, mnemonic, and symbol;
- logs: path, line, and timestamp or sequence marker.

Explicitly labeled investigator commentary can remain uncited, but it carries
no evidentiary weight and cannot support a conclusion.

## 1. Activate and frame

Extract the exact symptom, entering hypothesis, proposed intervention, and
prior attempts. Classify the work:

| State | Next work |
|---|---|
| Mechanism and fix known | implementation |
| Mechanism known, fix unknown | engineering |
| Mechanism unknown | RCA |

For RCA, keep the proposed production change outside the investigation. The
investigation must remain capable of refuting the entering hypothesis. Establish
the failure surface and scope with the user, honoring scope already stated or
authorized. Record the original question, hypothesis, RCA decision, and scope
as the trace's commitment record.

## 2. Articulate observations

Use `iterative-docs` to scaffold the trace. Use the user's stated location
first. Otherwise follow an established project convention; when
`.cache/rca/` already exists and no more specific convention applies, place the
trace at `.cache/rca/<topic>/trace.md`. Ask where to put it only when neither a
user choice nor a project convention exists.

Create an **Observed symptom** section containing:

- exact error strings, logs, serial output, exit codes, timestamps, and sequence
  markers without paraphrase;
- a table of environments, versions, configuration, and code paths where the
  symptom manifests;
- a corresponding non-manifestation table, including working controls and
  known workarounds;
- gaps in the observation record;
- the prior hypothesis, clearly separated from observations and attributed to
  where it came from.

Do not treat an inferred cause as an observation. Non-manifestation conditions
are first-class evidence because they often discriminate among mechanisms.

## 3. Build substrate when needed

Skip this stage when the investigator and orchestrator can already interpret
the relevant architecture. Build substrate when either identifies a gap or
cannot make a meaningful prediction because the system relationships are
unclear.

Name the gap, then explain from the lowest relevant abstraction upward. Include
only concepts that affect the defect. Append a short primer to the trace so a
reviewer can reconstruct the model used during the investigation. Resume as
soon as the next prediction is intelligible; the primer is a prerequisite, not
a general tutorial.

## 4. Assemble sources

Create two indices before phase reading:

| Participant field | Meaning |
|---|---|
| codebase | executing source tree |
| role | contribution to the observed path |
| local path | stable path available to every reader |
| revision | exact tag, commit, or other version |

| Arbitrator field | Meaning |
|---|---|
| specification | identifier and title |
| version | exact governing version |
| local path | canonical or staged copy |
| applicability | phases or behavior it governs |

Pin participant source to the investigated revision and stage arbitrators at
stable, read-only locations. Record provenance for fetched material. Convert
PDF arbitrators with `pdftotext -layout` so exact passages remain searchable
while retaining the PDF for page citations. Confirm file and symbol search work
for large trees. Do not silently change source revisions between phases.

## 5. Decompose the causal chain

Trace the runtime path from the first relevant event to the observed outcome.
Split at natural handoffs such as syscall returns, traps, transfers to another
execution context, and exits into error handling. A phase may cross repositories
and one repository may span several phases. Name phases by actions rather than
directories.

Identify the prime suspect before phase reading, using it to allocate attention
without skipping earlier constraints. For a multi-step defect, create a phase
index with number, action, boundary or applicability, and status. Under each
phase scaffold `Prediction`, `Findings`, `Review`, and `Open questions`.

Treat the decomposition as revisable. Merge adjacent phases whose handoff adds
more overhead than clarity. Split a phase when evidence reveals another natural
handoff. A single atomic lookup may be represented as one phase.

## 6. Investigate each phase

Run these steps in order for one phase at a time.

### Predict

Before opening new sources for the phase, write an immutable, user-visible
prediction. Use concrete symbols, call order, arguments, return values, state
transitions, applicable arbitrator expectations, and known gaps. Base it on the
recorded observations, previous verified findings, and material already in
context. Do not inspect a new file or passage to improve the prediction; turn
that uncertainty into a verification question. Label innate or unsupported
expectations so the read can challenge them.

### Read

Define a bounded handoff-to-handoff scope, participant files and symbols,
applicable arbitrator sections, and citeable verification questions. Include
adjacent callers, logging, configuration resolution, and state-management code
when they shape the behavior under study.

For a bounded local read, the orchestrator may switch into the reader role and
produce the same report directly. For a delegated read, fill
[`../assets/phase-read-prompt.md`](../assets/phase-read-prompt.md) and use
`coro-develop` for its lifecycle. One coroutine session normally owns one phase;
when phases have been formally merged, one session may cover the merged unit.

### Check and verify

The findings report must contain cited findings, explicit divergences from the
prediction, and later-phase questions tagged with where they arose and where
they are likely answered. Revise an incomplete report before using it.

The orchestrator then opens each primary source supporting a load-bearing
claim and confirms that the cited material entails the claim. Bug location,
failure mode, control-flow decisions, and conclusions are load-bearing. Record
the verification in `Review`; correct or reject claims that exceed their source.

### Update

Update the working model and later predictions only from verified findings.
Carry questions into an open-questions register with question, phase raised,
likely answering phase, actual answering phase, and status (`open`, `answered`,
or `closed as out of scope`). Keep closed questions visible.

At the phase boundary, report progress, divergences or refutations, the revised
hypothesis, and coroutine cost when one was used. A phase that rules out a
candidate is a useful result even when it finds no positive mechanism.

## 7. Handle refutations

When findings contradict a working claim:

1. Name the refuted claim and where it entered the trace.
2. Cite the refuting evidence.
3. Preserve the original claim and mark it refuted.
4. State the revised model and identify later reasoning that must change.
5. Reconsider phase boundaries only when the new model changes the runtime
   surface; otherwise continue along the existing code path.

For a direction-changing refutation, finish and verify the current phase, then
stop before dispatching the next. Present the evidence, revised model, and
continue, rescope, or abort consequences to the user. The user owns that choice.
If they already authorized a choice under conditions that clearly cover this
result, apply it without asking them to repeat the decision; otherwise wait for
direction.

Small corrections that do not change scope, candidate location, or a
load-bearing mechanism can be resolved in the normal phase review.

## 8. Validate with a control

Before executing, write an experiment or equivalent falsification that states:

- the surviving mechanism and intervention under test;
- measured signals and raw-output capture locations;
- results that would support or refute the mechanism;
- at least one unchanged control under the same inputs and environment;
- varied axes needed to isolate confounders;
- alternative explanations that would survive a matching result.

Use only an intervention already present or supplied by the user, and only in
an environment where the user has authorized the controlled test. When there is
no proposed intervention, use an equivalent observational falsification such as
a regression test; validation cannot be omitted.

Run the unchanged control close enough to the intervention run to expose drift.
Preserve commands, environment, versions, and raw outputs. Compare every
prediction with its observation in a table. A match means the hypothesis
survived this test, not that it is universally proven. A mismatch creates a new
refutation and returns the work to Stage 7.

When the test matches, write conclusions that cite the phases establishing
each causal link and state the exact environments, versions, and configurations
covered. Record untested variants and alternative explanations as uncertainty,
then apply the completion criteria in `SKILL.md`.
