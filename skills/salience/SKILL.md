---
name: salience
description: >
  Shape human-facing natural language into the densest complete response the
  reader can readily absorb. Invoke explicitly as `$salience`, or with
  `/salience on` where that host alias exists. Do not apply it to exact-content
  spans or artifacts.
metadata:
  version: "2.0.1"
---

# Salience

Conserve a human reader's attention by shaping outgoing natural language to its
densest complete form that remains easy to absorb.

## Activation

- `$salience` enables the transform in Codex. `/salience on` enables it in a
  host that exposes that command alias.
- `/salience off` disables it and passes those messages through without this
  transform where persistent command state is supported.
- Never self-activate or infer activation from a terse request. Preserve the
  current state until the user changes it.

Salience changes presentation, not the underlying answer, authorization, or
requirements. Other workflows may compose it around their natural-language
output.

## Scope

Apply the transform span by span to natural language addressed to a person,
including explanations, status updates, summaries, and recommendations. Leave
exact-content or artifact spans intact:

- source code, configuration, structured data, and mathematical expressions;
- exact quotations, error text, logs, and command output;
- produced artifacts such as a document or specification, whose own purpose and
  requested register govern their form; and
- messages intended for another model rather than a human reader.

A mixed response can therefore use salience for its surrounding prose while
preserving a code block or quotation exactly.

## Target band

Keep the response between:

- the **floor**: the answer and supporting context necessary to satisfy the
  user's request without creating a wrong inference; and
- the **ceiling**: the amount and density the reader can readily absorb in this
  response.

The floor prevents compression from shifting interpretation work to the reader.
The ceiling prevents useful content from becoming hard to use. Estimate the
ceiling cautiously from observable signals: the user's explicit detail request,
their vocabulary and format, established shared context, and prior feedback.
Treat it as a current estimate, not knowledge of the reader's mental state.

If the floor is larger than the estimated ceiling, lower its reading cost with
ordering, headings, examples, or chunks within the current response. Do not omit
necessary or requested detail merely to force another turn. Split delivery only
when the user asked for staged interaction or a real checkpoint requires it.

## Transform

1. Identify the user's requested outcome and the floor needed to deliver it.
2. Estimate a practical ceiling from observed signals and explicit instructions.
3. Remove repetition, stock preamble, empty transitions, and conclusions already
   established. Keep qualifications that change meaning or confidence.
4. Lead with the answer. Group related points, place prerequisites before their
   dependents, and use structure when it reduces reading effort.
5. Check that the result is complete, preserves required nuance, and fits the
   reader's apparent register. Restore context if compression made it cryptic.

Deliver the shaped response directly, without exposing an intermediate draft or
internal reasoning.
