# Stage 1 — Activate

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: this is the entry point. Next: [Stage 2](stage-2-observe.md).

**Purpose.** Decide whether to conduct an RCA at all, and refuse to act
on the stated hypothesis until the causal chain is understood.

**When this stage applies.** Every defect presented with a stated cause
or proposed fix that has not been independently verified. Skip this
stage only when the cost of acting on a wrong hypothesis is provably
lower than the cost of investigating — which is rare for non-trivial
defects.

**What to do.**

1. Read the stated problem. Identify: the symptom, the stated
   hypothesis (if any), the proposed fix (if any), prior attempts
   (if any).
2. Classify the defect. Three categories:
   - *Known mechanism, known fix.* No RCA needed. Apply and move on.
   - *Known mechanism, no fix yet.* Engineering problem, not RCA.
   - *Unknown mechanism.* RCA applies.
3. For the third category, refuse to patch, file, or choose a
   workaround. Surface the refusal to the investigator explicitly:
   "We will figure this out before we touch it."
4. Confirm the investigator accepts the refusal and the investigation
   scope. If they do not, either the RCA does not happen or the scope
   changes.

**What to produce.** A short written record in the trace document or
the investigator-facing channel: *problem as stated, hypothesis as
stated, decision to investigate, scope of investigation.* This is the
commitment point. Everything downstream references it.

**What to avoid.**

- Acting on the stated hypothesis while claiming to investigate it.
  The investigation must be capable of refuting the stated hypothesis.
  If you have already shipped the fix the stated hypothesis implies,
  the investigation is performative.
- Framing the refusal as blocking the investigator. It is the opposite:
  the refusal protects them from wasted iteration on a wrong fix.
- Skipping this stage because "the cause is obvious." The cause was
  obvious in every prior RCA that turned out to be wrong.

**Example.** The kexec RCA was activated from a session in which a
prior-prior session had left a stated hypothesis: *"Secondary CPUs fail
to come online under QEMU+HVF because old-kernel WFE-parks them via
`IPI_CPU_STOP`; QEMU sees them as `PSCI_ON` and returns `ALREADY_ON`
when the new kernel calls `PSCI_CPU_ON`."* The stated workaround was
`maxcpus=1`. The investigator's goal was to fix the bug rather than
live with the workaround. The orchestrator refused to pursue a fix
consistent with the stated hypothesis (the natural move: patch QEMU's
`ALREADY_ON` handling) and instead declared that the mechanism needed
verification first. The investigator accepted. The investigation
subsequently refuted the stated hypothesis entirely.
