# Stage 4 — Assemble sources

> Lossless reference. Read as a companion to [`README.md`](README.md).
> Previous: [Stage 3](stage-3-substrate.md). Next: [Stage 5](stage-5-decompose.md).

**Purpose.** Identify and locate every source the investigation will
cite, before the trace begins. Separate sources that *execute* during
the failure (participants) from sources that *adjudicate* whether
behavior is correct (arbitrators).

**When this stage applies.** Every RCA.

**What to do.**

1. Enumerate participants. For each codebase that executes during the
   failure, identify:
   - Its role in the failure (what it contributes to the symptom).
   - Its upstream source of truth (git repository, tag, revision).
   - Whether it is available locally or must be fetched.
2. Enumerate arbitrators. For each normative specification that
   governs participant behavior:
   - The spec identifier and version.
   - Which phases of the investigation it is expected to govern.
   - Where the canonical copy lives (URL, PDF, inline text).
3. Vendor and stage. Clone participants to a known local path.
   Download arbitrators to a known local path. Treat both as
   read-only primary sources for the duration of the investigation.
4. Prepare for searchability. For PDF arbitrators, extract text with
   `pdftotext -layout` so `grep` can locate sections. For large
   source trees, verify that navigation tools (file search, symbol
   search) work against the vendored copy.
5. Record. Produce a source index and an arbitrator index in the
   trace document. These get cited by phase findings.

**What to produce.**

- A **participants table**: codebase, role, local path, revision.
- An **arbitrators table**: spec, version, local path, phases it
  governs.
- Vendored copies of each, at a stable location the orchestrator and
  delegates can reach.

**What to avoid.**

- Starting the trace without vendored sources. Mid-investigation
  fetching breaks flow and introduces version drift between phases.
- Confusing participants with arbitrators. Source code executes; it
  does not specify. A spec specifies; it does not execute. A violation
  of the spec by the code is informative; a claim that the code is
  wrong without a spec to cite is just opinion.
- Treating an arbitrator as a participant. The authors of the spec
  are not the authors of the code; the spec does not make the code
  correct, and the code does not make the spec correct.

**Example.** The kexec investigation assembled:

**Participants** (vendored under `space/compute/vendor/`, shallow
single-branch clones):

| Codebase | Role | Vendored path | Revision |
|---|---|---|---|
| Linux kernel | Guest OS; owns both sides of kexec | `linux/` | `v6.19` |
| kexec-tools | Userspace kexec driver | `kexec-tools/` | master |
| QEMU | Virt-machine PSCI impl; HVF glue | `qemu/` | `v10.2.2` |
| Trusted Firmware-A | Reference PSCI impl at EL3 | `arm-trusted-firmware/` | `de38734` |

**Arbitrators** (staged under `.tmp/kb-staging/`):

| Arbitrator | Local path | Phases it governs |
|---|---|---|
| PSCI (ARM DEN 0022) | `arm-specs/DEN0022-PSCI.{pdf,txt}` | 3, 7, 8, 11, 12, 14, 15 |
| SMCCC (ARM DEN 0028) | `arm-specs/DEN0028-SMCCC.{pdf,txt}` | 9, 10, 11, 15 |
| ARMv8-A System Registers | `arm-sysreg/` | 3, 4, 5, 6, 8, 10, 12 |
| A64 Instruction Set | `arm-isa-a64/` | 3, 4, 5, 9, 10, 13 |
| Apple Hypervisor framework | `apple-hvf/` | 10, 13 |

Concrete commands used:

```sh
# Vendor a participant (shallow, single-branch, blobless).
git clone --depth 1 --single-branch --filter=blob:none \
  https://github.com/ARM-software/arm-trusted-firmware.git

# Extract arbitrator PDF to searchable text.
pdftotext -layout DEN0022-PSCI.pdf DEN0022-PSCI.txt
```

TF-A did not execute during the failure — it does not run under
QEMU+HVF. It was vendored as an arbitrator-by-comparison: a reference
implementation of what a spec-compliant PSCI handler looks like, so
that QEMU's implementation could be compared against it. That framing
was deliberate; treating TF-A as a participant would have been a
category error.
