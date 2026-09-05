# Glossary

> Lossless reference. Read as a companion to [`README.md`](README.md).

Terms defined by this specification.

| Term | Definition |
|---|---|
| **Arbitrator** | A normative specification that adjudicates whether participant behavior is correct. Not subject to investigation; a reference. |
| **Control matrix** | The observational design of Stage 8: a set of runs across one or more varied factors, including at least one unchanged control, producing data points that the surviving hypothesis must predict. |
| **Delegate** | A sub-agent, coroutine worker, or tool invoked by the orchestrator to perform bounded, mechanical reading. Does not decide what to investigate next. |
| **Divergence** | A difference between a phase's prediction (written before reading) and its findings (produced by reading). Divergences are flagged explicitly by the delegate and examined by the orchestrator. |
| **Finding** | A claim produced by a phase about the actual behavior of participant code or the actual mandate of an arbitrator. Must cite a primary source. |
| **Investigator** | The principal driving the RCA. Owns the question, the scope, and the decisions to start, halt, and stop. |
| **Orchestrator** | The agent performing prediction and verification. Owns the trace document and the per-phase loop. May be the same actor as the investigator. |
| **Participant** | A codebase that executes during the failure. Subject of investigation — its behavior is what the RCA explains. |
| **Phase** | A bounded segment of the investigation that follows the causal chain of the failure, from one natural handoff to the next. Produces a prediction, findings, review, and open questions. |
| **Prediction** | A falsifiable statement of expected causal chain, written by the orchestrator before any source is read for a phase. Recorded in the trace document. |
| **Provenance** | The citation of a primary source — `file:line` or `§:page` — for a non-trivial claim. Required for every finding. |
| **Refutation** | A phase's findings that contradict a working hypothesis. Recorded in the trace, propagated into the revised model, escalated to the investigator. |
| **Substrate** | The architectural mental model required to read the trace. Built in Stage 3 when absent. Not a deliverable; a prerequisite. |
| **Trace document** | The primary output: a living markdown document containing the scope, source indices, glossary, phase index, per-phase sections, refutation log, and conclusions. |
