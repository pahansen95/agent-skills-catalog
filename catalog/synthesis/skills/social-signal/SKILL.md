---
name: social-signal
description: >
  Synthesize public social signals into decision-ready insight. Use when a
  human asks what people are saying about a launch, competitor, topic, or public
  account, especially when Hermes Tweet can provide X/Twitter evidence. Do not
  use for private account data, engagement automation, or unsupported claims.
metadata:
  version: "1.0.0"
---

# Social Signal

This workflow turns public social posts into a concise decision artifact. It
owns signal extraction, uncertainty labeling, and action framing. It does not
own audience strategy, copywriting, posting, or growth automation.

## Inputs and output

- **In:** a topic, launch, public account, competitor, or question; an optional
  time window; and public social evidence, preferably gathered through Hermes
  Tweet when X/Twitter is the relevant source.
- **Out:** a brief that names the dominant signal, the supporting evidence, the
  uncertainty, and one safe next move.
- **Failure:** return "insufficient signal" when evidence is too thin, stale,
  contradictory, private, or not traceable.

## Procedure

1. **Frame the decision.** State what the user is trying to decide before
   collecting or summarizing posts.
2. **Gather public evidence.** Use read-only Hermes Tweet workflows for
   X/Twitter search, account review, thread context, or launch monitoring. Do
   not perform write actions.
3. **Cluster signals.** Group posts by repeated claim, objection, feature
   request, audience segment, emotional tone, timing, or counter-position.
4. **Score confidence.** Label each cluster as strong, moderate, weak, or
   anecdotal. Penalize small samples, stale posts, duplicated wording, and
   unclear authorship.
5. **Synthesize.** Produce the brief:
   - decision
   - strongest signal
   - evidence
   - uncertainty
   - next move
6. **Guard the boundary.** If the user asks for a post, reply, like, repost, or
   follow, stop and require exact human approval outside this workflow.

## Invariants

1. Use public evidence only.
2. Do not expose credentials, cookies, session material, or private account
   details.
3. Do not claim exhaustive platform coverage.
4. Separate observed signal from recommendation.
5. Prefer "insufficient signal" over invented certainty.
