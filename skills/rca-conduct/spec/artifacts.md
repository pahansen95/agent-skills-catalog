# Artifacts

> Lossless reference. Read as a companion to [`README.md`](README.md).

An RCA conducted under this specification produces four artifacts. All
four are mandatory; their formats are flexible but their content is not.

## Trace document

The primary output. A living markdown document updated section by
section as phases execute. Structure:

- **Header.** Purpose, scope, observed symptom, manifestation /
  non-manifestation tables.
- **Source index.** Participants table (codebase → path → revision).
- **Arbitrator index.** Arbitrators table (spec → path → phases
  governed).
- **Glossary** (optional but recommended for substantial RCAs).
- **Phase index.** Phase list table with status column.
- **One section per phase.** Each with `Prediction`, `Findings`,
  `Review`, `Open questions` subsections.
- **Refutation log.** Entries keyed to the phase that produced each
  refutation.
- **Conclusions.** Populated at end. States the surviving causal chain
  and the scope of the conclusion.

Every non-trivial claim in this document cites a primary source per
the provenance rules.

## Open-questions register

A cross-phase table of questions raised but not answered in the phase
where they appeared. Columns: question, phase raised, phase answered
(if any), status (open / answered / closed-as-out-of-scope).

The register is not aspirational. Closed questions stay in the
register marked closed; open questions stay visible. The investigator
can use the register to decide whether the RCA is truly complete or
whether any unresolved question is load-bearing for the conclusion.

## Control experiment record

The output of [Stage 8](stage-8-validate.md). Contains:

- Experiment design (written before execution).
- Raw observations (logs, command outputs).
- Predicted-vs-observed comparison table.
- Conclusion with explicit scope.

The record is independently reproducible. Anyone with the recorded
environment and commands can re-run the experiment and get the same
outcome. If they cannot, the record is incomplete.

## Conclusions section of the trace document

A concise restatement of the surviving causal chain, cited back to the
phases that established each link. Includes:

- The mechanism, stated once, in plain language.
- The proposed fix (if any), with location.
- The scope of the claim — which environments, versions, and
  configurations it covers.
- Outstanding uncertainties — what the experiment did not test, which
  open questions remain.

These four artifacts together are the deliverable. Any RCA output
missing one of them is incomplete under this specification.
