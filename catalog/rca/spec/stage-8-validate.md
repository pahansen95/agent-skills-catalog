# Stage 8 — Validate with a control experiment

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 7](stage-7-refutation.md). Next: the RCA is complete;
> see [`artifacts.md`](artifacts.md) for the expected outputs.

**Purpose.** Confirm the surviving hypothesis by an experiment designed
before the fix is applied. The experiment produces observations that
should be predicted by the hypothesis, and the predictions are made in
writing beforehand. This is the falsification step the trace itself
cannot perform — the trace reads code; the experiment runs it.

**When this stage applies.** Every RCA whose hypothesis proposes a
fix. If the RCA's output is purely a causal explanation without a
proposed intervention, this stage may be replaced by an equivalent
falsification (e.g., a regression test) but cannot be skipped — the
hypothesis must be testable against observation, not only against
source.

**What to do.**

1. Design the experiment **before** running it. Write down: what you
   will measure, what values would confirm the hypothesis, what
   values would refute it, what alternative explanations remain
   viable if the experiment passes.
2. Include controls. An experiment that only tests the fixed case
   does not separate "the fix works" from "the symptom was already
   not manifesting for unrelated reasons." Include an unfixed run
   immediately before the fixed run, with the same inputs and
   environment.
3. Factor out confounding variables. If the investigation touches
   multiple layers (build system, runtime, source), run the
   experiment across the axes you can vary, to show the outcome
   depends on the hypothesized variable and no others.
4. Execute. Record raw outputs, not summaries.
5. Compare observations to predictions. If they match, the
   hypothesis survives this test. Note: survives, not "is proven."
   Another experiment could still refute it.
6. If they do not match, return to [Stage 7](stage-7-refutation.md). The
   hypothesis is wrong or incomplete; a new refutation entry
   is recorded and the trace resumes.

**What to produce.**

- An **experiment design** recorded in the trace document or its
  companion before execution.
- Raw **observations** from the experiment runs, stored alongside the
  trace.
- A **predicted-vs-observed** comparison table.
- A **conclusion** section stating whether the hypothesis survived
  and what outstanding alternatives remain if it did.

**What to avoid.**

- Designing the experiment after running it. An ex-post-facto
  experiment is a narrative, not a test — by the time you write down
  predictions, you already know the outcome, and the predictions
  match by construction.
- Testing only the positive case. An experiment without a control
  cannot distinguish the fix from the fix-being-irrelevant.
- Stopping at one data point. Even two points across a single axis
  make a stronger claim than one point in isolation.
- Declaring the RCA complete before this stage. The trace can be
  self-consistent and still wrong; the experiment is the external
  check.

**Example — the 2×2 control matrix from the kexec investigation.**

Hypothesis entering Stage 8: *QEMU's `arm_set_cpu_on_async_work` in
`target/arm/arm-powerctl.c` fails to set `target_cpu_state->vcpu_dirty
= true` after `cpu_set_pc`. Under HVF, `flush_cpu_state` gates the
register push on this flag; with the flag false, the new PC never
reaches the hardware state, and the secondary vCPU resumes at its
last-seen PC — in overwritten memory after kexec — instead of the
kernel's secondary entry point. A one-line patch setting the flag
should cause the secondary to boot cleanly.*

**Experiment design, written before execution:**

- **Factor A (build path).** Two binaries, built independently:
  - *Bottle:* Homebrew's `qemu` formula, rebuilt from source via
    `brew reinstall --build-from-source qemu` with a `patch` block
    added to the formula.
  - *Vendored:* built directly from the vendored QEMU source tree
    (`space/compute/vendor/qemu`), signed with the HVF entitlement.
- **Factor B (patch state).** Two states:
  - *Unpatched:* working tree clean.
  - *Patched:* our one-line diff applied.
- **Measurement.** Kernel serial log after kexec into an arm64 guest
  with 4 vCPUs. Count of `"CPU N: failed to come online"` messages.
  Timing of `"CPU N: Booted secondary processor"` messages when
  present. Disassembly of `arm_set_cpu_on_async_work` checked for
  presence/absence of the expected `strb` instruction.
- **Predictions:**
  - Unpatched bottle + unpatched vendored: 3 secondaries fail with
    ~5 s timeouts each (`CPU1` at t+5 s, `CPU2` at t+10 s, `CPU3` at
    t+15 s, reflecting the kernel's serial 5-second timeout per
    secondary).
  - Patched bottle + patched vendored: all 3 secondaries boot within
    < 1 ms of `smp: Bringing up secondary CPUs ...`.
  - Disassembly: unpatched binaries do not contain a `strb` to the
    `CPUState.vcpu_dirty` field inside `arm_set_cpu_on_async_work`;
    patched binaries do.
- **Alternative explanations that would survive a pass:** A pass in
  all four cells confirms the hypothesis at the `vcpu_dirty` flag
  level. It does not rule out the flag being necessary but not
  sufficient across other accelerators (KVM, WHPX, TCG). Those
  accelerators were not tested; the conclusion is scoped to HVF.

**Execution and raw observations.**

Test procedure identical in all four cells: create Debian guest VM
with 4 vCPUs under the QEMU binary under test, install `kexec-tools`,
copy an arm64 Alpine kernel and initramfs, arm kexec with a cmdline
lacking `maxcpus=1`, fire kexec, sample serial after 45 s.

**Observed, all four runs:**

| Build | Patch state | `strb` in `arm_set_cpu_on_async_work` | Result |
|---|---|---|---|
| Bottle | unpatched | absent | `CPU1: failed to come online` at t+5.1 s; `CPU2` at t+10.2 s; `CPU3` at t+15.4 s |
| Bottle | patched | present at offset `0x334` of `CPUState` | `CPU1: Booted secondary processor` at t+0.46 ms; `CPU2` at t+0.54 ms; `CPU3` at t+0.61 ms |
| Vendored | unpatched | absent | `CPU1` at t+5.1 s; `CPU2` at t+10.2 s; `CPU3` at t+15.4 s |
| Vendored | patched | present at offset `0x334` of `CPUState` | `CPU1` at t+0.42 ms; `CPU2` at t+0.45 ms; `CPU3` at t+0.49 ms |

**Predicted vs. observed.**

| Prediction | Observed | Match? |
|---|---|---|
| Unpatched bottle: 3 failures at 5/10/15 s | 5.1 / 10.2 / 15.4 s | ✓ |
| Unpatched vendored: 3 failures at 5/10/15 s | 5.1 / 10.2 / 15.4 s | ✓ |
| Patched bottle: 3 successes in < 1 ms | 0.46 / 0.54 / 0.61 ms | ✓ |
| Patched vendored: 3 successes in < 1 ms | 0.42 / 0.45 / 0.49 ms | ✓ |
| `strb` present iff patched | confirmed in all four | ✓ |

**Conclusion.** The hypothesis predicted all four outcomes correctly.
The unpatched and patched runs differ only in the single `strb`
instruction's presence, and the outcome flips accordingly. Identical
timing between the two unpatched runs (5.1/10.2/15.4 s) across
independent build paths rules out build-system artifacts. The one-
line fix is sufficient to resolve the defect under HVF on this host.

Scope of the conclusion: HVF on Apple Silicon, QEMU 10.2.2.
Untested: KVM, WHPX, TCG. Untested: QEMU versions other than 10.2.2.
These are recorded in the open-questions register, not claimed as
confirmed.

The RCA completes at this point. The investigator ratified
completion; the investigation did not continue past the answered
question.
