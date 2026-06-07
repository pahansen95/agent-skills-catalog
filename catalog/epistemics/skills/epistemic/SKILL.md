---
name: epistemic
description: Make a document's factual claims traceable — find each claim's support, optionally test that it holds, and record the attribution. Never let a claim pass silently unsupported. Use when output makes factual claims that must be sourced.
metadata:
  version: "0.1.0"
---

# Epistemics

A workflow that makes factual claims traceable. For each claim it finds the
supporting source, optionally tests that the source bears the claim, and records
the attribution. Its one hard rule: no claim passes silently unsupported —
every claim ends in an explicit status.

## Inputs and output

- **In:** the *claims* (in a document), a *source pool* with an authority
  ranking (the consult order), and the settings below.
- **Out:** every claim resolved to an explicit **status**:
  - **Sourced** — support found, attribution recorded.
  - **Claim** — asserted on the author's own authority, *visibly flagged* as
    unsourced.
  - **Gap** — support unknown, and the absence *explicitly admitted*.
- **Failure:** none intrinsic. Claim and Gap are valid, deliberate outcomes, not
  errors.

## Model

- **Claim** — a statement that asserts something checkable.
- **Source** — a referenceable origin of support, ranked by **authority** (the
  consult order; e.g. primary > secondary > derived).
- **Binding** — a link from a claim to the source that supports it.
- **Reference** — a rendered attribution of a binding: a marker plus a collected
  entry.

## Procedure

For each claim:

1. **Establish.** Consult sources in authority order; the first that bears the
   claim becomes its binding. Stop there — lower sources aren't consulted once
   support is found.
2. **Test** *(optional, see Verification setting)*. Read the source directly and
   confirm it bears the claim. If the source is silent, ambiguous, or contradicts
   it, drop the binding and treat the claim as unsupported.
3. **Record.**
   - **Bound →** cite it: place a marker at the claim, collect a de-duplicated
     entry in the chosen style.
   - **Unbound →** fall back *explicitly*: **Claim** if the author may assert it
     on their own authority (flag it visibly as unsourced), otherwise **Gap**
     (state plainly that support is unknown).
4. **Never skip.** A claim left with no explicit status is the single failure
   this workflow exists to prevent.

## Settings

| Setting | Default | Adjust when |
|---|---|---|
| Consult order | Domain-defined authority ranking | A use has its own hierarchy |
| Verification | Off | Single-read, or adversarial (try to refute), when support must be confirmed not trusted |
| Author-authority | On (enables the Claim fallback) | Disallow to force Sourced-or-Gap only |
| Citation style | Footnote (marker + Sources section) | The document needs inline or endnote |
| De-duplication | On (one entry per source) | Rarely off |

## Invariants

1. Every claim ends in exactly one status: Sourced, Claim, or Gap.
2. A Claim result is always *visibly marked* as unsourced — never disguised as
   sourced.
3. With Verification on, support that does not hold is dropped, not recorded.
4. Every rendered marker resolves to exactly one collected entry; one source
   yields one entry.

## Non-goals

This workflow handles the provenance of claims, not their generation. It does not
decide *what* to assert, write the surrounding prose, or judge style. It takes
the claims as given and makes them traceable.

## Note

This skill is in development (version `0.y.z`). It unifies what may later split
back into separate establish / test / record skills if usage warrants; for now
the three are steps and a setting in one workflow.
