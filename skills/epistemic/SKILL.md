---
name: epistemic
description: Make factual claims traceable to examined support or an explicit unsupported status. Use when an output's factual claims must be sourced.
metadata:
  version: "0.1.0"
---

# Epistemics

Make every checkable factual assertion traceable. A completed claim has exactly
one status:

- **Sourced:** examined material supports it, and the attribution is recorded.
- **Claim:** the author asserts it on their own authority, visibly labeled as
  unsourced.
- **Gap:** support is unknown, and that absence is stated plainly.

Claim and Gap are deliberate unsupported outcomes. A claim that was missed or
left unprocessed has no status and is a workflow failure.

## Workflow

Inputs are the document's claims, a source pool, an authority-ordered consult
list, and the settings below.

For every claim:

1. **Support.** Consult sources in authority order. Examine enough relevant
   material to determine whether a source actually bears the claim. Bind the
   first supporting source, then stop; if none supports it, leave it unbound.
2. **Assess.** If verification is enabled, apply its additional scrutiny. Drop
   a binding if the source is silent, ambiguous, or contradictory. Verification
   Off skips this extra pass; it never permits a citation to material that was
   not examined in the Support step.
3. **Cite or label.** For a bound claim, place a marker and collect its source
   entry in the requested citation style. For an unbound claim, use Claim only
   when author-authority is enabled and the author may assert it; otherwise use
   Gap.
4. **Check coverage.** Confirm every factual claim has one status and every
   citation marker resolves to one collected entry.

Use a binding only for the claim the source supports; proximity or topical
relevance is insufficient.

## Settings

| Setting | Default | Adjust when |
|---|---|---|
| Consult order | Domain-defined authority ranking | A use has its own hierarchy |
| Verification | Off | Use direct-source or adversarial review when the initial support check needs more scrutiny |
| Author-authority | On (enables the Claim fallback) | Disallow to force Sourced-or-Gap only |
| Citation style | Footnote (marker + Sources section) | The document needs inline or endnote |
| De-duplication | On (one entry per source) | Rarely off |

## Non-goals

Handle claim provenance only. Do not decide what to assert, write the surrounding
prose, or impose a research or approval workflow beyond the caller's request.
This `0.y.z` workflow is in development; support, assessment, and citation may
split into separate skills if use warrants.
