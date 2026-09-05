---
name: iterative-docs
description: Build a long document incrementally — decompose into a structure, then fill it one unit at a time while holding the whole coherent. Designed to compose with other skills through replaceable behaviors, not dependencies. Use for specs, plans, guides, or any document long enough that one pass degrades quality.
metadata:
  version: "2.0"
---

# Iterative Document Writing

A skill is a workflow: it takes inputs, produces an output, and may fail instead. This workflow takes a brief and produces a finished document, working against a structure it builds up as it goes.

It owns exactly three responsibilities: **decomposition** (turn a goal into an ordered structure), **iteration** (fill one unit at a time), and **coherence** (every unit fits the whole). Everything else — prose register, sourcing, citation, fact-checking, when to pause for a human — is *not its concern*. Those compose in as replaceable behaviors (below); this workflow never names the skills that provide them.

## Inputs and output

- **In:** a *brief* (what to build — the goal, the audience, any source material) and a set of *settings* (the tunables below).
- **Out:** a finished document — or a failure, if no coherent structure can be formed, or a unit cannot be filled coherently even after revising the outline.

## The structure it builds

A document is a title, an **overview**, and an ordered list of **sections**. The overview is the thesis and the shape of the whole — written for real at the start, never a placeholder; it is the contract the body must satisfy. Each section is either **pending** (a placeholder heading) or **filled** (written prose).

## Two kinds of parameter

The distinction is the whole point of the design:

- **Settings** are *values*: what to build and how finely. Changing them tunes the run.
- **Behaviors** are *replaceable parts*: how prose gets drafted, and how a filled section gets judged. The workflow is defined against the **contract** each behavior must meet — not against any particular skill that meets it. So any skill satisfying the contract composes in, and this workflow stays unaware it exists.

## The two replaceable behaviors

The workflow delegates two behaviors. It ships a default for each — and those defaults are the *only* behavior it owns:

1. **Draft** — *given a section's heading and the document so far, produce its prose.* The default writes plain prose that satisfies the heading. The workflow guarantees only that the prose exists and fits — **not** its register, its sourcing, or its citations.
2. **Review** — *given a freshly filled section, return the problems to fix (none means accept).* The default checks the three things this skill is responsible for:
   - **Coherence** — does it follow from the sections before it?
   - **Completeness** — does it deliver what its heading and the overview promised?
   - **Consistency** — same terminology, structure, and conventions as the rest?

**Composition is wrapping, not coupling.** Another skill plugs in by providing its own version of a behavior — usually by *wrapping* the default so effects stack. A voice skill wraps Draft: it calls the inner drafter, then re-registers the prose. A sourcing skill wraps Review: it runs the inner checks, then adds "any claim not traceable to a source." The workflow runs identically underneath; it only ever sees "a Draft" and "a Review." The rich, emergent workflow from a real session is just this one workflow called with wrapped behaviors.

## The procedure

Run the phases in order; the fill phase repeats once per unit.

1. **Decompose.** Write the real overview. List every section as a pending placeholder heading. Stabilize this skeleton before filling — if a user is in the loop, a natural point to confirm direction.
2. **Track.** Create one task per section (`TaskCreate`); the task list is the cursor for which unit is active and what remains. Advance each task `pending → in_progress → completed` with `TaskUpdate`.
3. **Fill, one unit at a time.** For the next pending unit:
   - Mark its task `in_progress`.
   - **Revise if needed.** The outline is a hypothesis. If drafting this unit reveals the structure is wrong — two sections are one, ordering is backwards, a section is missing — fix the skeleton and realign the tasks instead of forcing prose into a flawed shape.
   - **Draft** the unit (size it to one coherent idea, not a line count).
   - **Review** the unit; resolve every finding before advancing. If a unit cannot be made coherent even after outline revision, the run fails rather than shipping an incoherent section.
   - Mark its task `completed`.
   - You need not re-read a section to confirm a write landed — the write tools fail loudly if they don't apply. Re-read only to judge coherence across what is now on the page.
4. **Finalize.** Pass over the whole: the overview still matches the body (revise it if the body diverged), transitions read in order, terminology and formatting are uniform end to end.

**Resumability.** The fill phase advances exactly one unit per turn. A caller may drive it unit by unit and interleave its own concerns — a checkpoint, a human review — between units. That orchestration is the *caller's* composition; this workflow does not own cadence.

## Settings

| Setting | Default | Adjust when |
|---|---|---|
| Granularity | One section per task | Very large docs → group into parts; short docs → finer sections |
| Unit size | One coherent idea (~50–150 lines) | A gauge only — never pad to hit it, never split a whole idea to stay under it |
| Outline revisable | Yes (enables in-loop revision) | Turn off only when a fixed structure is externally mandated |

## Invariants

Hold these throughout; breaking one is the failure it names.

1. The overview is real before any section is filled — never a stub.
2. Exactly one unit is in progress at a time — no parallel half-finished units.
3. A unit is complete only after review returns no problems — coherence is never deferred.
4. The count of pending units only decreases, except during an outline revision — the one sanctioned reshuffle.
5. On success, no pending placeholder remains — the structure is fully filled.

## Non-goals

This workflow does **not** one-shot a document, manage prose register, verify facts, attach citations, or decide when to pause for a human. Each is a separate skill, composed through the Draft or Review behavior, or by the caller driving the fill phase. Keeping them out is what makes this one independent and testable on its own.

## In one line

> Draft the structure first; fill it one coherent unit at a time; keep the whole consistent — and let other skills supply voice, sourcing, and review by replacing the drafting and review behaviors.
