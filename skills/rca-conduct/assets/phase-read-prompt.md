# Phase read prompt

Copy this template into the phase's `coro-develop` TODO. Replace every angle-
bracketed field and remove unused list items.

```markdown
Phase <number> — <action name>

Scope: <start handoff> → <end handoff>. Stay within these boundaries.
This task is limited to source reading and explicitly authorized inspection.
Do not edit source files, implement a fix, change the test environment, or
perform other mutations.

Participant sources:
- <path, files or symbols>: <why they are in scope>

Arbitrators:
- <specification and version>: <applicable sections>

Prediction (copied verbatim from the trace; do not modify):
<prediction>

Verification questions:
1. <specific question answerable from a cited primary source>

Return one Markdown report with:

## Findings
A numbered list. Cite every non-trivial claim as `path:line-range`,
`path:function`, specification identifier/version/section/page, disassembly
address/mnemonic/symbol, or log path/line/sequence as applicable.

## Divergences from prediction
List every mismatch explicitly, including apparently minor differences. Say
`None found` when the findings match.

## Open questions for later phases
Tag each question `raised in phase <N>; likely answered in phase <M>`. Say
`None` when there are no open questions.

Do not choose the next phase, revise the prediction, or infer the preferred
conclusion. End with `YIELD: DONE | <one-line summary>`.
```
