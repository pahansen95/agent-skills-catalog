# Roles

> Lossless reference. Read as a companion to [`README.md`](README.md).

Four roles appear in this specification. Any person or agent executing
RCA occupies one or more of them. A single actor often occupies multiple
roles concurrently; the roles are distinct functions, not distinct
entities.

## Investigator

The principal driving the RCA. Owns the question being asked, the scope
of the investigation, and the decision to start, halt, or stop. Human or
agent. In most RCAs the investigator is the person who observed the
defect and wants it explained.

## Orchestrator

The agent doing prediction and verification. Reads the output of each
stage, decides the next action, owns the trace document. Where the
investigator is a human, the orchestrator is often an agent the human
drives. Where the investigator is an agent (a skill invoking this
specification), investigator and orchestrator are the same actor.

The orchestrator does not delegate thinking. It delegates reading.

## Delegate

A sub-agent, coroutine worker, or tool invoked by the orchestrator to
perform bounded, mechanical work — reading source files, extracting
quotes, running commands, producing reports. Delegates are optional;
small RCAs do not need them. Large RCAs use delegates to parallelize
reading and to protect the orchestrator's context window from large
source dumps.

Delegates do not decide what to investigate next. They receive a task
and report back. Interpretation of their reports is the orchestrator's
job.

## Arbitrator-authors

Not a role in the RCA process — a reference. The authors of normative
specifications (ISA references, protocol standards, RFCs) are absent
from the investigation but present via their documents. The
specifications themselves are arbitrators: they adjudicate whether
participant behavior is correct.

Do not treat the code or the arbitrator as speaking for each other.
The code shows what happens; the arbitrator shows what *should* happen.
Divergence between them is one of the most informative findings an RCA
can produce.

## Role ownership table

| Function | Owner |
|---|---|
| Frame the question, set scope | Investigator |
| Stop/halt on direction-changing evidence | Investigator |
| Scaffold the trace document | Orchestrator |
| Write predictions before each phase | Orchestrator |
| Read source and produce findings | Delegate (if used), else Orchestrator |
| Verify cited provenance | Orchestrator — never delegated |
| Decide next phase, merge/split phases | Orchestrator |
| Declare the explanation complete | Investigator |
| Design the control experiment | Orchestrator |
| Judge whether control experiment passed | Orchestrator + Investigator |
