# Stage 6 — Per-phase loop

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 5](stage-5-decompose.md). Next: [Stage 7](stage-7-refutation.md).

**Purpose.** Execute one phase of the investigation. This stage is
invoked once per phase and forms the core of the RCA.

**When this stage applies.** Every phase produced by [Stage 5](stage-5-decompose.md),
run in sequence. Parallel execution of phases is possible in principle
but not recommended — later phases' predictions depend on earlier phases'
findings.

**What to do.** The loop has six steps. Do them in order. Do not skip.

## 6a — Predict

Before any source is read for the phase, the orchestrator writes down
the expected causal chain. The prediction is user-visible, recorded in
the trace document under the phase's `Prediction` heading, and
falsifiable. It names:

- Specific symbols (function names, variable names, macros).
- Expected call order.
- Expected arguments and return values at each call.
- Expected state transitions.
- Which arbitrators apply to this phase and what they mandate.
- Known gaps in the prediction — things the reading is expected to
  fill in.

A prediction that cannot be wrong is not a prediction. If you find
yourself writing "the code does whatever it does here," replace it
with what you *believe* it does and flag the belief as uncertain.

## 6b — Delegate the read

The orchestrator dispatches a delegate with:

- The prediction (so the delegate can flag divergences directly).
- The list of source files to consult, scoped to this phase.
- The list of arbitrators applicable to this phase.
- A strict report format: findings with `file:line-range` citations
  for every non-trivial claim, divergences-from-prediction as a
  separate subsection, open-questions-for-later-phases as a third
  subsection.

If the orchestrator is the reader (no separate delegate), it performs
the same reading under the same discipline.

## 6c — Receive findings

The delegate returns a structured report. The orchestrator reads it
and checks:

- Each claim has a citation.
- Divergences from the prediction are explicitly called out.
- Open questions are tagged with raised-in / likely-answered-in
  pointers.

If the report is missing these, send it back for revision before
moving on.

## 6d — Verify provenance

The orchestrator independently opens the cited files and checks the
load-bearing citations. Load-bearing means: claims the investigation
will build later phases on. A rough prioritization:

- Always verify: claims that identify a bug location, a failure mode,
  or a control-flow decision.
- Often verify: claims about what a function does or what a register
  holds.
- Rarely verify: claims about structural organization ("this file has
  a function called X").

The verification is a spot-check, not a re-reading. Two or three
citations per phase is usually enough if the findings are otherwise
coherent.

## 6e — Update model

Revisions from this phase propagate:

- Into the next phase's prediction. If Phase N surfaced that
  `machine_shutdown` uses hotplug offline rather than IPI-park,
  Phase N+1 must treat the hotplug path as given, not as a
  possibility.
- Into the investigator-visible summary. The orchestrator reports
  revisions to the investigator at the phase boundary.
- Into the cross-phase open-questions register, if any questions
  raised in earlier phases are answered here or if new questions are
  raised.

## 6f — Carry questions forward

Questions surfaced but out-of-scope for this phase are recorded with
three fields: question, phase where raised, phase where likely
answered. They are revisited at their answering phase. Unanswered
questions at the end of the investigation are acceptable — not every
question must be closed to conclude the RCA — but the register
preserves them so the investigator can decide which matter.

**What to produce.** For each phase, four sections in the trace
document, populated in order:

- **Prediction** (written in step 6a, before reading).
- **Findings** (written in step 6b, by the delegate).
- **Review** (written in step 6d, by the orchestrator).
- **Open questions** (appended in step 6f).

Plus an updated entry in the cross-phase open-questions register.

**What to avoid.**

- Writing the prediction *after* reading. Bias contamination. The
  prediction block, once written, is not retroactively edited. If
  it was wrong, it is wrong in writing.
- Skipping verification. The findings are not trustworthy until at
  least the load-bearing citations are confirmed.
- Letting the delegate decide the next phase. It cannot — it sees one
  phase. The orchestrator sees the arc.
- Treating a phase that produced nothing as worthless. "This phase
  ruled out X" is a valid finding. Record it.

**Example — Phase 6 of the kexec investigation (a phase that surfaced
a refutation).**

**Prediction** (written first, recorded in full):

> Primary CPU arrives at new kernel entry with MMU off, `x0 = dtb_phys`,
> `x1..x3 = 0`, DAIF masked, EL1 (HVF guest). Expected path: `_head` →
> `primary_entry` → `init_kernel_el` (no-op under EL1) → `__primary_switch`
> → `start_kernel()` → subsystem init → `smp_init`.
>
> RCA implication: time passes in Phase 6. Paging setup, driver init.
> **If secondary vCPUs' threads run during this window**, their pending
> async `arm_set_cpu_off_async_work` should drain. **If halted vCPUs
> don't process their work queue**, the race window stays open.

**Delegate TODO** (excerpt):

```
Scope: from new kernel entry through start_kernel up to (but not
including) smp_init_cpus (Phase 7).

Sources to read:
- linux/arch/arm64/kernel/head.S — _head, primary_entry, init_kernel_el
- linux/init/main.c — start_kernel
- QEMU: accel/hvf/hvf-accel-ops.c — vCPU thread lifecycle, halted handling

Verification questions:
1. primary_entry sequence. Cite.
...
7. RCA-critical: QEMU/HVF vCPU thread behavior when halted = 1.
   - Does it block on a condvar when halted?
   - Does it still process async work?
   - What wakes a halted vCPU?
```

**Findings** (coroutine report, excerpt):

> - HVF vCPU halted = condvar sleep. Not a busy loop. Async work in
>   `cpu_work_list` **does not run** until the thread is kicked via
>   `SIG_IPI` or `qemu_cond_broadcast`. Phase 6 does not kick
>   secondaries. This is the window in which the race stays open.

**Orchestrator verification** (spot-check):

> Read `qemu/cpu-common.c:169-180` (`async_run_on_cpu`). It calls
> `queue_work_on_cpu` → `cpu_exit`. `cpu_exit` sets `exit_request`, not
> a condvar broadcast. Coroutine's "needs explicit kick" claim confirmed
> for already-halted case.
>
> But: re-reading the HVF main loop in `hvf-accel-ops.c:177-186`:
>
> ```c
> do {
>     qemu_process_cpu_events(cpu);   // drains work queue
>     if (cpu_can_run(cpu)) {
>         r = hvf_arch_vcpu_exec(cpu);
>     }
> } while (...);
> ```
>
> `qemu_process_cpu_events` is called at the top of every iteration.
> For the *self-CPU_OFF* case, the target vCPU is the CPU making the
> call — it is running, not halted, when the work is queued. On the
> next loop iteration, `qemu_process_cpu_events` drains the work
> before the halted check. `halted = 1` is set by the drained work.
> Next iteration: halted = 1, no work → sleep on halt_cond.
>
> So the work DOES drain reliably in the self-CPU_OFF case. The
> coroutine's claim is correct only for the already-halted case, which
> does not apply to the secondary issuing its own PSCI_CPU_OFF HVC.

**Consequence.** The working hypothesis at this point — "the race
between async CPU_OFF work and subsequent CPU_ON is what produces
`ALREADY_ON`" — was refuted by this phase. The refutation was recorded
in the trace, the model updated, and the investigation continued with
a narrower candidate set: the bug is somewhere *else* in the
CPU_OFF / CPU_ON flow, and the next phases' predictions must not
assume the race is the mechanism.

That refutation was positive progress. It eliminated the mechanism
that had attracted the most attention and redirected the investigation
toward the actual bug (the `vcpu_dirty` gap discovered in Phase 12).
