# Stage 3 — Build substrate mental model

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 2](stage-2-observe.md). Next: [Stage 4](stage-4-sources.md).

**Purpose.** Ensure the investigator has the architectural model needed
to read the trace. Without it, subsequent phases produce citations
attached to incorrect interpretations.

**When this stage applies.** When the defect sits in a subsystem whose
architecture is not already understood by the investigator. Skip when
the investigator (or orchestrator) already has the model. Build when
investigator signals a gap ("I don't understand how X and Y interact"),
or when an attempted prediction reveals one ("I can't predict what
should happen here because I don't know what does what").

**What to do.**

1. Identify the gap. What is the investigator or orchestrator unsure
   of? Name it.
2. Build bottom-up. Start from the lowest abstraction relevant to the
   defect and work up to the subsystem boundary. Each concept should
   depend only on concepts already established.
3. Anchor to the defect. Every concept introduced should be visibly
   relevant to the failure. If it isn't, it belongs in a textbook, not
   in this RCA.
4. Write the model down. A brief written substrate model shared with
   the investigator — not a complete domain tutorial, just enough to
   support reading the code path.
5. Resume the investigation. The substrate is a prerequisite, not a
   deliverable. Do not over-invest.

**What to produce.** A short architectural primer, shared with the
investigator, covering only the concepts load-bearing for the
investigation. Recorded in the trace document so later reviewers can
reconstruct the investigator's mental model at the time of the
investigation.

**What to avoid.**

- Treating this as a textbook rewrite. The target is *just enough
  substrate*. Everything beyond what the defect requires is scope
  creep.
- Refusing to do it because it "feels like a detour." The detour
  exists because the trace does not stand alone; a trace interpreted
  without substrate will produce conclusions that sound plausible and
  are wrong.
- Doing it too late. If Phase N produces citations the investigator
  cannot interpret, the substrate should have been built before Phase
  N. Catching this only after several wasted phases is an anti-
  pattern; catch it at the first unsure prediction.

**Example.** The kexec investigation built substrate after the
investigator signaled: *"I don't understand how QEMU, HVF, and the
hardware interact; I don't have a grounding for assessing proposed
fixes."* The orchestrator paused the trace and walked through:

- **arm64 exception levels.** EL0 (user), EL1 (kernel), EL2
  (hypervisor), EL3 (secure monitor). Privilege directions. `HVC`
  routes EL1→EL2; `SMC` routes to EL3; `ERET` returns from a higher
  level to a lower.
- **Traps.** Synchronous exceptions caused by deliberate instructions
  (`HVC`, `SMC`, `SVC`) or by architectural events (page fault,
  illegal instruction). Hypervisors use traps to virtualize CPU
  operations.
- **PSCI.** Standardized firmware interface for CPU power management,
  defined by ARM DEN 0022. Functions: `CPU_ON`, `CPU_OFF`,
  `CPU_SUSPEND`, `SYSTEM_RESET`. Invoked via HVC or SMC depending on
  conduit. Implemented by EL3 firmware on real hardware; by QEMU on
  virtual machines.
- **WFE/WFI.** `Wait For Event` / `Wait For Interrupt` — low-power
  halt instructions. Used by idle loops and, historically, by
  secondary-CPU park loops.
- **vCPU, HVF.** A vCPU is the hypervisor's abstraction of a CPU
  presented to the guest: a thread + saved register state. HVF is
  Apple's closed-source hypervisor kext; QEMU drives it via the
  `hv_vcpu_*` API family.
- **Trampoline, purgatory.** Position-independent, MMU-off code that
  bridges from old kernel to new kernel entry during kexec. Kernel-
  internal trampoline for `kexec_file_load(2)`; userspace-supplied
  purgatory for the legacy `kexec_load(2)` path.
- **TF-A.** Trusted Firmware-A, the open-source reference EL3 PSCI
  implementation. Not present on QEMU+HVF; used as a specification-
  compliant reference to compare QEMU's emulation against.

With this substrate in hand, the investigator could correctly read a
finding like *"arm_set_cpu_on queues async work on target vCPU but
never sets vcpu_dirty"* — a sentence that requires knowing what vCPUs
are, what HVF expects of QEMU, and why "dirty" matters. Without the
substrate, such a finding is noise.

The substrate took about 30 minutes to build and saved the
investigation from several hours of misinterpreted phase outputs.
