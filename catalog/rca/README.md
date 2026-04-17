# Root Cause Analysis (RCA)

A disciplined approach to investigating a specific observed software
defect at the source level. The output is a causal chain — from
symptom to mechanism — with every non-trivial claim cited to a primary
source, validated by a control experiment designed before the fix is
applied.

RCA here is scientific method applied to a software system: observe
precisely, predict in writing, read sources, verify citations, refute
or confirm, iterate. Hypotheses are disposable; the trace is not. A
refuted hypothesis is information, not a setback.

## Specification

[`spec/README.md`](spec/README.md) is the authoritative entry into
the behavioral specification. It provides a lossy overview and the
end-to-end flow; the sibling files under [`spec/`](spec/) are
lossless per-stage references.

| File | Role |
|---|---|
| [`spec/README.md`](spec/README.md) | Overview + E2E flow |
| [`spec/roles.md`](spec/roles.md) | Investigator / Orchestrator / Delegate / Arbitrator |
| [`spec/cross-cutting.md`](spec/cross-cutting.md) | Concerns applied at every stage |
| [`spec/stage-1-activate.md`](spec/stage-1-activate.md) … [`spec/stage-8-validate.md`](spec/stage-8-validate.md) | One file per stage, lossless |
| [`spec/artifacts.md`](spec/artifacts.md) | Mandatory RCA outputs |
| [`spec/anti-patterns.md`](spec/anti-patterns.md) | Failure modes and their fixes |
| [`spec/glossary.md`](spec/glossary.md) | Terms defined by the spec |
| [`spec/worked-example.md`](spec/worked-example.md) | Worked example summary and index |

## Skills

| Skill | Description |
|---|---|
| [rca-conduct](skills/rca-conduct/SKILL.md) | Drives an RCA end to end; activates via `/rca on`. |

## Dependencies

Skills in this domain build on two other catalog skills and expect
them to be installed alongside:

- `documentation/iterative-docs` — for writing the trace document.
- `coroutine/coro-develop` — for dispatching per-phase delegate reads.

Skills in this domain do not reimplement either. They fail loudly if
either is absent.
