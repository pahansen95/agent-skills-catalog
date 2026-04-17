# Stage 5 — Decompose into phases

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 4](stage-4-sources.md). Next: [Stage 6](stage-6-phase-loop.md).

**Purpose.** Partition the investigation into a sequence of bounded,
citeable subproblems that follow the causal chain of the failure from
first symptom-adjacent event to final observable outcome.

**When this stage applies.** Every RCA that spans more than one
obviously atomic lookup. If the investigation can be done in one read
of one function, skip decomposition and treat it as a one-phase RCA.

**What to do.**

1. Follow the code path, not the source tree. The phase list is
   organized around what happens in order at runtime, not around
   which repository contains the code. A single phase may cross
   repository boundaries; a single repository may span several phases.
2. Choose phase boundaries at **natural handoffs**. A phase ends where
   control transfers cleanly: a syscall return, a trap into a
   hypervisor, a branch into new code context, an error path leaving
   a function. These are the points where findings stitch together
   with minimal ambiguity.
3. Name each phase by its action, not its location. "New kernel
   requests secondary bringup" is a phase; "`arch/arm64/kernel/smp.c`"
   is not.
4. Identify the prime suspect phase up front. Most RCAs have a phase
   where the defect is most likely to live. Name it and bias reading
   weight toward it — but do not skip the preceding phases, because
   their findings are what constrain the suspect phase's
   interpretation.
5. Allow phases to be merged or split as evidence accumulates. The
   initial decomposition is a working hypothesis. When two adjacent
   phases prove too coupled to investigate independently, merge them.
   When a phase turns out to contain an uninvestigated boundary
   inside, split it.
6. Record the phase list in the trace document as an index table:
   number, name, path applicability, status (pending / in progress /
   complete).

**What to produce.** A phase index table at the top of the trace
document; one section per phase in the trace document with
placeholders (`Prediction`, `Findings`, `Review`, `Open questions`) to
be filled by the per-phase loop ([Stage 6](stage-6-phase-loop.md)).

**What to avoid.**

- Decomposing by source tree. The result is a phase list that matches
  the codebase layout but not the failure's temporal shape.
- Phase boundaries inside a function call. A phase whose start or end
  is in the middle of a continuous code execution is hard to cite
  cleanly. Push the boundary to the next handoff.
- Too many phases. More phases produce more context overhead, more
  delegate dispatches, and more divergence-risk between predictions
  and findings. If a phase is thin (a single citation), merge it with
  a neighbor.
- Too few phases. A phase that spans "the new kernel boots and brings
  up all secondaries" is too coarse to produce citeable predictions.
  Split at the first natural handoff.
- Rigid adherence to the initial decomposition. Phases are a working
  tool, not a contract.

**Example — the kexec investigation decomposition.**

Fifteen phases covering symptom-to-cause, organized along the causal
chain. The table below is the one the trace document used:

| # | Phase | Rationale for the boundary |
|---|---|---|
| 1 | Userspace: arm the kexec (`kexec -l`) | Starts the staging; ends when the syscall returns with kexec armed. |
| 2 | Userspace: fire the kexec (`kexec -e`) | From `reboot(LINUX_REBOOT_CMD_KEXEC)` to entry into `machine_kexec()`. |
| 3 | Old kernel: quiesce and stop secondaries | `machine_shutdown` drives secondaries offline. Ends when all are off. |
| 4 | Old kernel: primary tears itself down, jumps to trampoline | Disables MMU/caches; branches out. |
| 5 | Purgatory executes (`kexec_load` path only) | Optional; depends on which syscall was used. |
| 6 | New kernel: head, early init | From `_head` through `start_kernel` up to SMP init. |
| 7 | New kernel: discover secondaries from DTB, register PSCI | DT parse, cpu_ops registration. |
| 8 | New kernel: request secondary bringup | `smp_init` → `cpu_up` → `boot_secondary`. Ends at PSCI call. |
| 9 | New kernel: issue PSCI call (`HVC #0`) | The trap itself. |
| 10 | HVC trap exits guest into HVF | Guest exit; HVF returns to QEMU. |
| 11 | QEMU: dispatch PSCI call | `hvf_handle_psci_call` function-ID switch. |
| 12 | QEMU: handle `CPU_ON` — inspect target vCPU state | **Prime suspect.** State machine for PSCI. |
| 13 | QEMU: if reset happens, push vCPU state via HVF | State push to the hardware-backing layer. |
| 14 | TF-A reference behavior on real hardware | Compliance anchor. |
| 15 | Back in new kernel: handle PSCI return, timeout, report failure | Closes the loop at the symptom. |

The causal chain runs symptom-back-to-cause *and* cause-forward-to-
symptom — by the time Phase 15 runs, the investigation has walked every
step between the Phase 8 request and the Phase 15 timeout. This
bidirectionality is deliberate: it means the investigation can validate
that its mechanism explains the specific observed symptom, not merely
*a* symptom consistent with the mechanism.

**Phase 12 named as prime suspect** before reading any source. The
prior hypothesis placed the bug in PSCI `CPU_ON` handling; phase
numbering reflected that without assuming the prior hypothesis was
correct. The prime-suspect label meant: expect phases 1–11 to complete
quickly (confirming inputs and narrowing scope) and phase 12 to
require more scrutiny.

**Mid-trace adjustment.** Phases 9 through 13 were initially
decomposed as five independent phases. By the time Phase 8 was
complete, the coupling between them (HVC issuance → HVF exit → QEMU
dispatch → CPU_ON handling → vCPU reset) was tight enough that
investigating them independently produced redundant context loads and
unclear handoffs. The orchestrator merged 9–13 into a single coroutine
dispatch with a combined TODO. The initial decomposition was a
hypothesis; the merge was the refinement.
