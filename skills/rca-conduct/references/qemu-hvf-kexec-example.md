# Historical example: QEMU+HVF multi-vCPU kexec

This is a consolidated illustration from the author's prior investigation. The
full trace lives outside this catalog and was not available for independent
verification here. Preserve these details as an account of how the workflow was
used; do not reuse them as evidence in another RCA.

## Question and observations

An arm64 guest kernel kexec'd under QEMU+HVF on Apple Silicon with more than one
vCPU printed `"CPU N: failed to come online"` for each secondary, with one
failure after each roughly five-second timeout. Both `kexec_file_load(2)` and
`kexec_load(2)` followed by `reboot(LINUX_REBOOT_CMD_KEXEC)` manifested the
symptom. The workaround was `maxcpus=1`.

The author's non-manifestation cases were real hardware with independent PSCI
firmware, including EC2 Graviton and bare metal; cold boot through firmware on
the same QEMU+HVF configuration; and the single-vCPU workaround. This pointed
the investigation toward QEMU, the kexec-specific transition, and secondary
bringup without yet asserting a mechanism.

The entering hypothesis said the old kernel used `smp_send_stop()` and
`IPI_CPU_STOP` to WFE-park secondaries in `cpu_park_loop()`, leaving QEMU to see
them as `PSCI_ON` and return `ALREADY_ON` when the new kernel requested
`PSCI_CPU_ON`. The workflow kept that statement as a hypothesis and did not
patch QEMU's `ALREADY_ON` handling before tracing it.

## Substrate and sources

The investigation first established enough arm64 and virtualization context to
interpret later findings: EL0–EL3 privilege levels; HVC/SMC traps and ERET;
PSCI `CPU_ON`, `CPU_OFF`, `CPU_SUSPEND`, and `SYSTEM_RESET`; WFE/WFI; QEMU vCPU
threads and saved register state; Apple's HVF API; the kexec trampoline and
purgatory paths; and Trusted Firmware-A as a specification-compliant comparison
rather than executing code. The author's account says this primer took about
30 minutes and prevented later phase reports from being misread.

Sources were staged under `space/compute/vendor/` as shallow, single-branch
copies:

| Source | Category and role | Path | Recorded revision |
|---|---|---|---|
| Linux kernel | participant: guest OS on both sides of kexec | `linux/` | `v6.19` |
| kexec-tools | participant: userspace kexec driver | `kexec-tools/` | `master` |
| QEMU | participant: PSCI implementation and HVF glue | `qemu/` | `v10.2.2` |
| Trusted Firmware-A | comparison arbitrator: reference PSCI implementation | `arm-trusted-firmware/` | `de38734` |

The arbitrators staged under `.tmp/kb-staging/` were:

| Arbitrator | Recorded path | Initial phases governed |
|---|---|---|
| PSCI, ARM DEN 0022 | `arm-specs/DEN0022-PSCI.{pdf,txt}` | 3, 7, 8, 11, 12, 14, 15 |
| SMCCC, ARM DEN 0028 | `arm-specs/DEN0028-SMCCC.{pdf,txt}` | 9, 10, 11, 15 |
| ARMv8-A system registers | `arm-sysreg/` | 3, 4, 5, 6, 8, 10, 12 |
| A64 instruction set | `arm-isa-a64/` | 3, 4, 5, 9, 10, 13 |
| Apple Hypervisor framework | `apple-hvf/` | 10, 13 |

PDF specifications were also converted to searchable text with
`pdftotext -layout`. TF-A did not execute in QEMU+HVF and was deliberately
treated as comparison evidence, never as a participant.

## Causal decomposition

The initial phase index followed runtime handoffs:

| # | Action |
|---|---|
| 1 | Userspace arms kexec with `kexec -l` |
| 2 | Userspace fires kexec with `kexec -e` |
| 3 | Old kernel quiesces and stops secondaries |
| 4 | Primary tears itself down and jumps to the trampoline |
| 5 | Purgatory executes on the `kexec_load` path |
| 6 | New kernel enters at `_head` and performs early init |
| 7 | New kernel discovers secondaries and registers PSCI |
| 8 | New kernel requests secondary bringup |
| 9 | New kernel issues the PSCI `HVC #0` |
| 10 | The HVC trap exits through HVF to QEMU |
| 11 | QEMU dispatches the PSCI call |
| 12 | QEMU handles `CPU_ON` and inspects target-vCPU state |
| 13 | QEMU pushes reset vCPU state through HVF |
| 14 | TF-A provides reference behavior for real hardware |
| 15 | New kernel handles the PSCI result, times out, and reports failure |

Phase 12 was marked prime suspect before source reading because the entering
hypothesis implicated `CPU_ON`. Earlier phases still constrained how that phase
could be interpreted. During the run, phases 9–13 were merged into one read
when the trap, dispatch, state transition, and register push proved too coupled
for useful independent reports.

## Refutations

The first direction change arrived while tracing shutdown. The phase report
said arm64 `machine_shutdown()` on the kexec path calls
`smp_shutdown_nonboot_cpus(reboot_cpu)`, while `smp_send_stop()` is used for
halt, power-off, and restart paths. The kexec path takes secondaries through CPU
hotplug offline, ending in `cpu_psci_cpu_die()` and
`psci_ops.cpu_off()`—a real `PSCI_CPU_OFF` HVC from each secondary. That
contradicted the WFE-park hypothesis. The trace preserved it as refuted and
continued after the investigator accepted a revised candidate set.

A later hypothesis proposed a race: QEMU's queued
`arm_set_cpu_off_async_work` might not run before the new kernel's `CPU_ON`, so
`power_state` could remain `PSCI_ON`. The Phase 6 prediction expected the
primary to enter with the MMU off, `x0 = dtb_phys`, `x1..x3 = 0`, DAIF masked,
and the guest at EL1, then follow `_head` → `primary_entry` →
`init_kernel_el` → `__primary_switch` → `start_kernel()` → SMP initialization.
It asked whether secondary vCPU threads would drain pending async work during
that interval.

The delegated report initially claimed an HVF vCPU sleeping on a condition
variable would not process `cpu_work_list` until explicitly kicked. The
orchestrator checked the load-bearing claim. The recorded review cited
`qemu/cpu-common.c:169-180` for `async_run_on_cpu` → `queue_work_on_cpu` →
`cpu_exit`, then re-read the HVF loop at `hvf-accel-ops.c:177-186`. In the
self-`CPU_OFF` case the target is still running when it queues the work;
`qemu_process_cpu_events` runs at the top of the next loop iteration and drains
the work before the halted check. Only afterward does the vCPU sleep. The race
hypothesis was therefore refuted. Four replacement candidates were recorded,
including the `vcpu_dirty` gap that later survived, instead of silently adopting
the delegate's broader claim.

## Surviving mechanism

The author's final causal chain was:

1. QEMU's `arm_set_cpu_on_async_work` in `target/arm/arm-powerctl.c` resets the
   target `CPUARMState` and calls `cpu_set_pc(target_cpu_state, info->entry)`.
2. It does not set `target_cpu_state->vcpu_dirty = true`.
3. Under HVF, `flush_cpu_state` at the start of `hvf_arch_vcpu_exec` gates
   `hvf_arch_put_registers` on that flag.
4. With the flag false, the new program counter is not pushed into HVF hardware
   state. The secondary resumes at its last-seen PC in memory overwritten by
   kexec and never reaches `secondary_start_kernel`.
5. The proposed intervention was one line after `cpu_set_pc`:
   `target_cpu_state->vcpu_dirty = true;`.

## Recorded validation

Before running it, the author designed a 2×2 control matrix across two factors:

- build path: a Homebrew bottle/formula rebuilt from source, and a binary built
  from the vendored QEMU tree and signed with the HVF entitlement;
- patch state: clean unpatched source and the one-line intervention.

Each run used a Debian guest with four vCPUs, installed `kexec-tools`, an arm64
Alpine kernel and initramfs, a command line without `maxcpus=1`, and serial-log
sampling after 45 seconds. Predictions called for three serial five-second
timeouts in each unpatched build, all three secondaries booting within one
millisecond in each patched build, and a `strb` to `CPUState.vcpu_dirty` in
disassembly only when patched.

The account records:

| Build | State | Disassembly | Serial result |
|---|---|---|---|
| Bottle | unpatched | relevant `strb` absent | failures at 5.1, 10.2, and 15.4 s |
| Bottle | patched | `strb` at offset `0x334` | boots at 0.46, 0.54, and 0.61 ms |
| Vendored | unpatched | relevant `strb` absent | failures at 5.1, 10.2, and 15.4 s |
| Vendored | patched | `strb` at offset `0x334` | boots at 0.42, 0.45, and 0.49 ms |

All recorded outcomes matched the written predictions. The two build paths were
used to challenge a build-artifact explanation. The conclusion was limited to
QEMU 10.2.2 with HVF on that Apple Silicon host. KVM, WHPX, TCG, and other QEMU
versions were not tested. Those limits remained in the open-questions register,
and the investigation stopped when the investigator ratified that the original
question had been answered.
