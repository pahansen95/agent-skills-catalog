---
name: iterative-docs
description: Build a long document from a revisable outline, drafting and reviewing one coherent unit at a time. Use for specs, plans, guides, or other documents whose quality benefits from incremental writing.
metadata:
  version: "2.0"
---

# Iterative Document Writing

Turn a brief into a coherent finished document through decomposition, serial
drafting, and whole-document review. Preserve any caller-supplied structure,
register, sourcing rules, or other constraints.

## Behaviors

The workflow uses two replaceable behaviors:

- **Draft:** given a unit's heading, the brief, and the document so far, produce
  its prose. By default, write clear prose that fulfills the heading.
- **Review:** given the newly drafted unit and the document so far, report
  problems. By default, check that it follows prior units, fulfills the outline
  and introduction, and uses consistent terminology and conventions.

A caller may replace or wrap either behavior to add voice, sourcing, citation,
fact-checking, or specialized review. The workflow relies on the behavior's
contract rather than a particular provider; wrapped behaviors can therefore
compose without becoming hard dependencies.

## Workflow

1. **Outline.** From the brief and any mandated structure, create an ordered
   outline sized into coherent units. Write the title and a real introduction or
   overview now: it must state the thesis and shape of the document rather than
   stand in as a placeholder. Stabilize enough structure to begin, while treating
   non-mandated parts of the outline as revisable.
2. **Track.** Record pending, active, and completed units with an available task
   tracker or a simple checklist. Keep exactly one active unit.
3. **Fill serially.** For the next pending unit:
   - Revisit the outline when drafting reveals a missing, misplaced, split, or
     redundant unit. Preserve externally fixed structure and realign the tracker
     after any allowed revision.
   - Run Draft, then Review. Resolve every review finding before marking the unit
     complete. If the unit cannot be made coherent after an allowed outline
     revision, report the failure rather than accepting it.
   - Continue with the next unit in the same turn when time and context allow.
     Pause only for an actual caller checkpoint, required input, or execution
     boundary; one-unit-at-a-time describes work order, not turn cadence.
4. **Finalize.** Review the complete document. Reconcile the introduction with
   the body, repair transitions, and make terminology and formatting consistent.
   Finish with no pending outline placeholders.

## Settings and completion

- **Granularity:** one section per unit by default; group or divide sections when
  that yields coherent drafting units.
- **Outline revision:** enabled unless the caller supplies a fixed structure.

Success means the introduction is substantive, each unit has passed Review,
every planned unit is filled, and the final pass leaves the whole coherent. The
workflow fails if it cannot form a coherent structure or complete a unit after
permitted revision.
