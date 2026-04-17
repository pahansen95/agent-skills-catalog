# Stage 7 — Refutations as progress

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 6](stage-6-phase-loop.md). Next: [Stage 8](stage-8-validate.md).

**Purpose.** Establish the posture toward refuted hypotheses: they are
information, not failures. The investigation's trajectory is the
sequence of candidates eliminated plus the surviving candidate. The
survival is only meaningful because the eliminations were thorough.

**When this stage applies.** Every RCA will produce at least one
refutation if it is non-trivial. This "stage" is less a step and more
an ongoing posture — it applies at every phase boundary where a
refutation fires. Invoke its rules whenever a phase's findings
contradict a working hypothesis.

**What to do.**

1. Recognize the refutation. A phase's findings contradict a claim
   the earlier investigation was building on. Name the contradiction
   explicitly — "Phase N refutes Hypothesis H which was established
   in Phase M."
2. Do not delete the refuted hypothesis. Mark it refuted in the trace
   document, link to the phase that refuted it, and leave it in place.
3. Update the working model. Propagate the refutation into the next
   phase's prediction. If the refuted hypothesis was the basis for
   later phases' decomposition, reconsider the decomposition
   ([Stage 5](stage-5-decompose.md) rule: phases can be adjusted).
4. Escalate to the investigator at the phase boundary. Direction-
   changing refutations are not resolved by the orchestrator
   unilaterally (per cross-cutting concern: halt on direction-changing
   evidence). Present the refutation, present the updated model,
   present the options for continuing, and wait for the investigator's
   decision.
5. Continue. Unless the investigator re-scopes or aborts, the trace
   proceeds with the revised model. The code path under investigation
   has not changed; only the interpretation has.

**What to produce.** A refutation entry in the trace document, keyed
to the phase that produced it. Format:

- **Refuted claim.** The hypothesis being retired, verbatim or
  paraphrased with a pointer to its original statement.
- **Refuting evidence.** The citation that produced the refutation
  (from the phase's findings).
- **Revised model.** What now replaces the refuted claim.
- **Propagation.** What earlier conclusions depended on the refuted
  claim and need revisiting.

**What to avoid.**

- Silently dropping a refuted hypothesis. The trace must show what was
  tried; hiding refutations turns the RCA into an authored narrative
  rather than a record.
- Treating the refutation as a setback. The investigation has made
  progress — it has eliminated a candidate that was absorbing
  attention. Continue with that attention redirected.
- Restarting the investigation from scratch. The phases were derived
  from the code path, not the hypothesis. Usually only interpretation
  changes; the decomposition stands.
- Suppressing the user-facing report of the refutation. The
  investigator must see the direction change; otherwise they cannot
  ratify or redirect.

**Example.** The kexec investigation hit two direction-changing
refutations, both preserved in the trace and both productive.

**Refutation 1 (Phase 2).** The entering hypothesis claimed
`smp_send_stop()` drove `IPI_CPU_STOP` into secondaries, parking them
in `cpu_park_loop()` with WFE/WFI and DAIF masked, after which QEMU
saw them as `PSCI_ON` and returned `ALREADY_ON` to the new kernel's
`PSCI_CPU_ON`.

Phase 2's delegate surfaced: *arm64 `machine_shutdown()` on the kexec
path calls `smp_shutdown_nonboot_cpus(reboot_cpu)`, not `smp_send_stop()`.
The latter is reserved for `machine_halt/power_off/restart`. The former
drives secondaries through the CPU hotplug offline state machine,
whose final arm64 step invokes `cpu_psci_cpu_die()` → `psci_ops.cpu_off()`
— a real `PSCI_CPU_OFF` HVC per secondary.*

The refutation eliminated the WFE-park mechanism entirely. The
`ALREADY_ON` hypothesis was no longer consistent with the code: if
secondaries legitimately reach `PSCI_OFF` state before kexec, they are
not `PSCI_ON` when the new kernel calls `CPU_ON`. The orchestrator
escalated to the investigator, updated the observed-symptom section's
"prior hypothesis" entry to mark it refuted, and proposed four new
candidate hypotheses for the actual mechanism. The investigator
accepted the continuation. The trace continued with the revised model.

**Refutation 2 (Phase 6).** A working hypothesis built after
Refutation 1 proposed that the async `arm_set_cpu_off_async_work`
queue-drain in QEMU's CPU_OFF handler was the race: if the work had
not run before the new kernel's `CPU_ON` arrived, `power_state` would
still be `PSCI_ON` and the caller would see `ALREADY_ON`.

Phase 6's reading of the HVF vCPU loop showed the work reliably drains
before the vCPU halts for the self-targeting CPU_OFF case. The race
hypothesis was refuted. Four new candidate hypotheses replaced it,
including the one that eventually survived: the separate `vcpu_dirty`
flag not being set after the reset-and-PC-write in the CPU_ON async
work.

Both refutations were recorded in the trace as first-class findings,
not hidden. The final RCA document shows the reader the path from
"hypothesis said X, evidence refuted it, revised model said Y" several
times before reaching the bug. A reader auditing the RCA can
reconstruct why the surviving hypothesis was selected — because the
alternatives were eliminated, not because it was the first thing
guessed.
