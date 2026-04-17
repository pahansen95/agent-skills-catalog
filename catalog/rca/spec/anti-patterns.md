# Anti-patterns

> Lossless reference. Read as a companion to [`README.md`](README.md).

Common failure modes, each tied to a stage or cross-cutting concern
that would have prevented them.

| Anti-pattern | Why it fails | What to do instead |
|---|---|---|
| **Acting on the stated hypothesis while claiming to investigate.** | Investigation becomes performative; the "fix" ships before the mechanism is verified. | Stage 1: refuse to patch until the mechanism is understood. |
| **Paraphrasing the symptom.** | Exact error strings carry diagnostic information (timeouts, error codes, specific log lines) that paraphrases lose. | Stage 2: quote verbatim. |
| **Skipping the non-manifestation list.** | The most discriminating evidence — which environments *don't* fail — is absent. Investigations without it over-explore. | Stage 2: produce the non-manifestation table. |
| **Reading source before writing predictions.** | Reader bias. Whatever the code says will seem to match whatever you expected. | Stage 6a: write the prediction in full, committed to the trace, before any source is read for the phase. |
| **Uncited claims.** | The investigation cannot be audited; conclusions rest on assertion. | Cross-cutting: every non-trivial claim cites `file:line` or `§:page`. |
| **Trusting delegate reports without verification.** | Delegate output drifts from source — summaries, elisions, quiet inventions. The orchestrator does not catch this without checking. | Stage 6d: spot-check load-bearing citations against the cited sources directly. |
| **Delegating reasoning to the delegate.** | Synthesis offloaded to a sub-agent produces shallow analysis divorced from the RCA's arc. | Cross-cutting: orchestrator thinks; delegate reads. Delegates do not choose what to investigate next. |
| **Silently deleting refuted hypotheses.** | The trace becomes a narrative, not a record. The survivor appears selected without basis. | Stage 7: record refutations; keep them in the trace; link to the phase that refuted them. |
| **Restarting the investigation after a refutation.** | Phases were decomposed from the code path, not the hypothesis. Restarting usually throws away still-valid phase structure. | Stage 7: continue with revised interpretation; let the decomposition stand unless the refutation reshapes the failure's surface. |
| **Decomposing by source tree instead of causal chain.** | Phase list matches codebase layout but not runtime order; findings don't stitch at handoffs. | Stage 5: follow code path, not source tree; choose phase boundaries at syscall returns, trap entries, branches to new context. |
| **Too many thin phases.** | Context overhead per phase exceeds the phase's findings; delegates return reports longer than their subject. | Stage 5: merge thin adjacent phases. |
| **Too few coarse phases.** | Phase is too broad to produce citeable predictions; findings are narrative. | Stage 5: split at the first natural handoff. |
| **Declaring victory without a control experiment.** | A self-consistent trace can still be wrong; external falsification is the only check. | Stage 8: design and run an experiment with a control. |
| **Designing the experiment after running it.** | Predictions match by construction — they were written with the outcome in hand. | Stage 8: write the experiment design before execution, including predictions. |
| **Testing only the fixed case.** | Cannot distinguish "fix works" from "symptom was latent." | Stage 8: include unfixed controls. |
| **Continuing past the answered question.** | Investigation sprawls into adjacent subsystems that were never in scope. | Cross-cutting stop condition: stop when the investigator's question is answered. |
| **Stopping before completeness because the investigation is long.** | Concluding on a partial mechanism produces fixes that don't hold. | Cross-cutting stop condition: investigation ends at completeness, not at effort expended. |
| **Confusing arbitrator with participant.** | Code and spec speak past each other; a spec violation becomes invisible because the spec was treated as "the code." | Stage 4: separate the tables; maintain the distinction throughout. |
| **Skipping substrate.** | Citations land correctly on code the investigator cannot interpret; phase findings become noise. | Stage 3: build substrate before the phase that needs it, not after. |
| **Treating cost awareness as an override of correctness.** | Phases are cut short to save budget; the resulting explanation is incomplete. | Cross-cutting: track cost for visibility; do not let it truncate phases that need depth. |
