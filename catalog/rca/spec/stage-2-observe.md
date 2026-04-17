# Stage 2 — Articulate observations

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 1](stage-1-activate.md). Next: [Stage 3](stage-3-substrate.md).

**Purpose.** Produce a precise, hypothesis-free statement of what is
observed and under what conditions. This becomes the ground truth the
investigation is accountable to.

**When this stage applies.** Every RCA, immediately after activation.

**What to do.**

1. List the observations. Exact error strings, log excerpts, serial
   output, exit codes. Include timestamps or sequence markers where
   available. Do not paraphrase — quote.
2. List the conditions under which the symptom manifests. Arch,
   hypervisor, versions, configuration, code paths.
3. List the conditions under which the symptom does *not* manifest.
   Workarounds already known, related-but-different scenarios that
   work, control cases that pass.
4. List the known unknowns. Gaps in the observation record that
   subsequent phases will need to fill — e.g., "we don't know what
   return code the failing syscall produced; we only know the caller
   timed out."
5. Separately, carry forward the prior hypothesis *labeled as such*.
   Do not dissolve it into the observation set. It is a candidate to
   refute, not a starting point to extend.

**What to produce.** An *Observed Symptom* section in the trace
document containing:

- Verbatim symptom quotes
- Manifestation conditions (table)
- Non-manifestation conditions (table)
- Known unknowns (bulleted)
- Prior hypothesis (clearly labeled, with provenance — where did the
  hypothesis come from)

**What to avoid.**

- Conflating hypothesis with observation. "Secondary CPUs time out
  because they're WFE-parked" is two claims: the observation (they
  time out) and the mechanism (they're WFE-parked). Split them.
- Paraphrasing symptom strings. If the kernel prints `"CPU 1: failed
  to come online"`, quote it. Do not summarize to "the secondary CPU
  fails."
- Skipping the non-manifestation table. The set of conditions under
  which the defect does *not* appear is often the most discriminating
  evidence in the investigation.

**Example.** From the kexec investigation, the observation statement
produced was:

- **Symptom (verbatim).** After `kexec_file_load(2)` or `kexec_load(2)`
  + `reboot(LINUX_REBOOT_CMD_KEXEC)`: `"CPU 1: failed to come online"`,
  `"CPU 2: failed to come online"`, `"CPU 3: failed to come online"`,
  one line per secondary, each after ~5 s.
- **Manifests under.** arm64, QEMU+HVF on Apple Silicon, vCPU count > 1,
  both syscall paths.
- **Does NOT manifest under.** `maxcpus=1`, real hardware (EC2 Graviton,
  bare metal) with independent PSCI firmware, cold boot through
  firmware on the same QEMU+HVF config.
- **Prior hypothesis (labeled).** Old kernel parks secondaries in
  `cpu_park_loop()` via `smp_send_stop()` → `IPI_CPU_STOP`; new
  kernel's `PSCI_CPU_ON` call hits a QEMU emulation gap.

The non-manifestation list was decisive: real-hardware success pointed
at QEMU; cold-boot success under the same QEMU pointed at the
kexec-specific path; `maxcpus=1` success pointed at the secondary-CPU
bringup specifically rather than the kexec transition itself. These
conditions narrowed the investigation long before any source had been
read.
