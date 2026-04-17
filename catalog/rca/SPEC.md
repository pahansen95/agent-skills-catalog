# RCA — Specification

> Standalone authoritative specification of the Root Cause Analysis domain.

## Purpose & Scope

This document specifies a disciplined approach to Root Cause Analysis. It
defines how to conduct an investigation that produces a causal explanation
of a defect, grounded in primary sources, validated by a pre-designed
control experiment, and auditable end-to-end via provenance.

RCA in this specification is **source-level investigation of a specific
observed defect**. The defect has a reproducible symptom in a known system.
The investigation's output is a causal chain — observation to mechanism —
that explains the symptom, with every non-trivial claim cited to a primary
source. The proposed fix is a byproduct of the explanation, not the goal.

The specification covers eight stages and a set of cross-cutting concerns
that apply throughout. It is written for two audiences: a human developer
conducting RCA manually, and an agent orchestrator applying the
specification as a skill. Both operate under the same rules. Stage 9 —
handoff and archival of the RCA's output into external systems (upstream
trackers, bug-report repositories, downstream teams) — is explicitly out
of scope. This specification ends when the causal explanation is complete
and validated.

## Philosophy

RCA as defined here produces a **causal explanation with provenance**, not
a working system. The output is scientific — a claim about why a defect
occurs, supported by evidence anyone can independently verify.

A fix is a byproduct. If the explanation is correct and complete, the fix
falls out of it naturally; if no fix falls out, the explanation is not
complete. This is the test for whether you have done RCA or something
that resembles it.

The discipline is scientific method applied to a software system:

- **Observe** the symptom. Precisely, without interpretation.
- **Hypothesize** a mechanism. Name it explicitly as a hypothesis.
- **Predict** what sources will show if the hypothesis is true. Write
  the predictions down *before* reading the sources.
- **Test** the predictions against the sources.
- **Refute, revise, or confirm.** A refuted hypothesis is information;
  preserve it, update the model, iterate.
- **Validate** the surviving hypothesis with a control experiment the
  investigation itself cannot produce. The experiment must have been
  designable before the fix existed.

Three claims follow from this philosophy, and the rest of the
specification is built on them:

1. **Hypotheses are disposable; the trace is not.** A good RCA discards
   multiple hypotheses along the way. The record of that disposal — what
   was tried, what refuted it, what survived — is the artifact of value.
   The final hypothesis without the refutations is a guess; the final
   hypothesis plus the refutations is a conclusion.

2. **Provenance is the boundary between investigation and gossip.** Any
   claim without a source citation is not part of the RCA — it is
   commentary. An investigation whose claims are not independently
   verifiable is indistinguishable from confident invention.

3. **The orchestrator thinks; delegates read.** Prediction and
   verification are cognitive work; the investigator cannot outsource
   them and still call the result their RCA. Reading source code,
   running commands, extracting quotes — these are mechanical. Delegate
   them freely. Do not delegate the reasoning that decides what to read
   next or whether what was read confirms what was predicted.

If any of these three claims fails for your investigation, you are
producing something adjacent to RCA, not RCA.

## Roles

Four roles appear in this specification. Any person or agent executing
RCA occupies one or more of them. A single actor often occupies multiple
roles concurrently; the roles are distinct functions, not distinct
entities.

### Investigator

The principal driving the RCA. Owns the question being asked, the scope
of the investigation, and the decision to start, halt, or stop. Human or
agent. In most RCAs the investigator is the person who observed the
defect and wants it explained.

### Orchestrator

The agent doing prediction and verification. Reads the output of each
stage, decides the next action, owns the trace document. Where the
investigator is a human, the orchestrator is often an agent the human
drives. Where the investigator is an agent (a skill invoking this
specification), investigator and orchestrator are the same actor.

The orchestrator does not delegate thinking. It delegates reading.

### Delegate

A sub-agent, coroutine worker, or tool invoked by the orchestrator to
perform bounded, mechanical work — reading source files, extracting
quotes, running commands, producing reports. Delegates are optional;
small RCAs do not need them. Large RCAs use delegates to parallelize
reading and to protect the orchestrator's context window from large
source dumps.

Delegates do not decide what to investigate next. They receive a task
and report back. Interpretation of their reports is the orchestrator's
job.

### Arbitrator-authors

Not a role in the RCA process — a reference. The authors of normative
specifications (ISA references, protocol standards, RFCs) are absent
from the investigation but present via their documents. The
specifications themselves are arbitrators: they adjudicate whether
participant behavior is correct.

Do not treat the code or the arbitrator as speaking for each other.
The code shows what happens; the arbitrator shows what *should* happen.
Divergence between them is one of the most informative findings an RCA
can produce.

### Role ownership table

| Function | Owner |
|---|---|
| Frame the question, set scope | Investigator |
| Stop/halt on direction-changing evidence | Investigator |
| Scaffold the trace document | Orchestrator |
| Write predictions before each phase | Orchestrator |
| Read source and produce findings | Delegate (if used), else Orchestrator |
| Verify cited provenance | Orchestrator — never delegated |
| Decide next phase, merge/split phases | Orchestrator |
| Declare the explanation complete | Investigator |
| Design the control experiment | Orchestrator |
| Judge whether control experiment passed | Orchestrator + Investigator |

## Cross-cutting concerns

These concerns apply to every stage. Read them before the stages; they
are preconditions, not appendices.

### Provenance discipline

Every non-trivial claim in the RCA cites a primary source. Citations are
specific enough that a reader can locate the cited material without
further search.

Required citation forms:

- **Source code:** `file:line-range` or `file:function-name`. Prefer
  line ranges for snippets longer than one line; a single line is
  acceptable when you quote the line.
- **Specifications:** `<spec-id> § <section>` and page number when the
  source is a PDF. If the spec is versioned, include the version.
- **Disassembly:** address + instruction mnemonic + symbol name.
- **Logs and serial output:** file path + line number, plus a timestamp
  or sequence marker.

A claim without a citation is not part of the RCA. It may appear in the
trace document as *investigator commentary* if explicitly marked as
such, but it carries no evidentiary weight and does not support
conclusions.

Citations are checked, not trusted. The orchestrator verifies at least
the load-bearing citations directly — opens the cited file, reads the
cited lines, confirms the claim matches. Verification happens after the
claim is made, before the claim propagates into later phases. See
Stage 6 for the mechanism.

### Prediction vs reading — who does what

The orchestrator predicts. The orchestrator verifies. The orchestrator
does not read unbounded source.

The orchestrator writes, in user-visible text before any reading occurs
for a phase, the expected causal chain — function names, call order,
return values, state transitions. The prediction is falsifiable: if it
is vague enough that any finding could be said to match, it is not a
prediction.

The delegate (coroutine, sub-agent, or the orchestrator itself acting in
a reader capacity) then performs the reading: locating source files,
extracting snippets, assembling the actual causal chain with citations,
and producing a findings document that flags divergences from the
prediction explicitly.

The orchestrator receives the findings, verifies the load-bearing
citations, and updates the working model.

The separation is not a productivity optimization. It is a bias
discipline. Readers who know what they expect to find tend to find it;
predictors who have not yet read the source are not yet biased by it.

### Halting on direction-changing evidence

When a phase surfaces evidence that would invalidate a load-bearing
assumption of the investigation — a refuted mechanism, a reclassified
failure mode, a new candidate bug location — the orchestrator halts
before the next phase and escalates to the investigator.

Halt means: finish writing the current phase's findings, do not dispatch
the next phase's delegate, present the divergence to the investigator
with the data that produced it.

The investigator decides whether to:

- **Continue** with a revised model. Usually correct; the phases were
  decomposed from the code path, which the refutation typically does
  not change (only interpretation does).
- **Re-scope.** Expand or contract the phase list if the refutation
  reshapes the failure's surface.
- **Abort.** The defect was not what was thought; a new RCA begins.

The orchestrator does not make this decision unilaterally. Small
divergences — citation corrections, tightening of a phase boundary, a
predicted function name being slightly different — are resolved inline
without a halt. Direction-changing divergences are not.

### Stop condition — question answered, not system fully understood

The RCA ends when the investigator's original question is answered to
their satisfaction. It does not end when every subsystem touched has
been fully characterized.

Concretely: the investigation stops when the causal chain from symptom
to mechanism is complete, every claim along the chain is cited, and a
control experiment has confirmed the mechanism's predictive power. Open
questions that are not on that chain remain open — recorded in the
open-questions register, not investigated further.

Stopping is the orchestrator's suggestion; the investigator ratifies.
If the orchestrator believes the explanation is complete and the
investigator disagrees, surface the gap and continue.

Do not stop *before* completeness because the investigation is long.
Do not continue *past* completeness because the investigation is
interesting. Neither effort-based nor curiosity-based stop criteria
apply.

### Compute budget awareness

Delegating reading to agents has a non-trivial per-turn cost. The
orchestrator tracks cost when a budget is relevant and reports it at
phase boundaries. A phase that costs more than expected is a signal —
possibly of an overbroad prompt, possibly of genuinely deep source
material.

Cost awareness does not override correctness. If a phase requires deep
investigation to produce cited findings, the investigation is done
deeply regardless of cost. The discipline is visibility: the
investigator can see what the RCA costs and redirect if needed.

### Refutation as progress

A hypothesis refuted by a phase is a positive outcome. The investigation
has eliminated a candidate and narrowed the search space. The trace
document preserves the refuted hypothesis, the phase that refuted it,
and the revised model.

Treat refutations as expected events, not failures. Do not delete
refuted hypotheses from the trace — they are the evidence that the
surviving hypothesis was selected on merit. An RCA that never refutes
anything is either solving a trivial problem or selection-biased.

## Stages

### Stage 1 — Activate

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

### Stage 2 — Articulate observations

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

### Stage 3 — Build substrate mental model

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

### Stage 4 — Assemble sources

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

### Stage 5 — Decompose into phases

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
be filled by the per-phase loop (Stage 6).

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

### Stage 6 — Per-phase loop

**Purpose.** Execute one phase of the investigation. This stage is
invoked once per phase and forms the core of the RCA.

**When this stage applies.** Every phase produced by Stage 5, run in
sequence. Parallel execution of phases is possible in principle but
not recommended — later phases' predictions depend on earlier phases'
findings.

**What to do.** The loop has six steps. Do them in order. Do not skip.

#### 6a — Predict

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

#### 6b — Delegate the read

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

#### 6c — Receive findings

The delegate returns a structured report. The orchestrator reads it
and checks:

- Each claim has a citation.
- Divergences from the prediction are explicitly called out.
- Open questions are tagged with raised-in / likely-answered-in
  pointers.

If the report is missing these, send it back for revision before
moving on.

#### 6d — Verify provenance

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

#### 6e — Update model

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

#### 6f — Carry questions forward

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

### Stage 7 — Refutations as progress

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
   (Stage 5 rule: phases can be adjusted).
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

### Stage 8 — Validate with a control experiment

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
6. If they do not match, return to Stage 7 (refutation). The
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

## Artifacts

An RCA conducted under this specification produces four artifacts. All
four are mandatory; their formats are flexible but their content is not.

### Trace document

The primary output. A living markdown document updated section by
section as phases execute. Structure:

- **Header.** Purpose, scope, observed symptom, manifestation /
  non-manifestation tables.
- **Source index.** Participants table (codebase → path → revision).
- **Arbitrator index.** Arbitrators table (spec → path → phases
  governed).
- **Glossary** (optional but recommended for substantial RCAs).
- **Phase index.** Phase list table with status column.
- **One section per phase.** Each with `Prediction`, `Findings`,
  `Review`, `Open questions` subsections.
- **Refutation log.** Entries keyed to the phase that produced each
  refutation.
- **Conclusions.** Populated at end. States the surviving causal chain
  and the scope of the conclusion.

Every non-trivial claim in this document cites a primary source per
the provenance rules.

### Open-questions register

A cross-phase table of questions raised but not answered in the phase
where they appeared. Columns: question, phase raised, phase answered
(if any), status (open / answered / closed-as-out-of-scope).

The register is not aspirational. Closed questions stay in the
register marked closed; open questions stay visible. The investigator
can use the register to decide whether the RCA is truly complete or
whether any unresolved question is load-bearing for the conclusion.

### Control experiment record

The output of Stage 8. Contains:

- Experiment design (written before execution).
- Raw observations (logs, command outputs).
- Predicted-vs-observed comparison table.
- Conclusion with explicit scope.

The record is independently reproducible. Anyone with the recorded
environment and commands can re-run the experiment and get the same
outcome. If they cannot, the record is incomplete.

### Conclusions section of the trace document

A concise restatement of the surviving causal chain, cited back to the
phases that established each link. Includes:

- The mechanism, stated once, in plain language.
- The proposed fix (if any), with location.
- The scope of the claim — which environments, versions, and
  configurations it covers.
- Outstanding uncertainties — what the experiment did not test, which
  open questions remain.

These four artifacts together are the deliverable. Any RCA output
missing one of them is incomplete under this specification.

## Anti-patterns

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

## Glossary

Terms defined by this specification.

| Term | Definition |
|---|---|
| **Arbitrator** | A normative specification that adjudicates whether participant behavior is correct. Not subject to investigation; a reference. |
| **Control matrix** | The observational design of Stage 8: a set of runs across one or more varied factors, including at least one unchanged control, producing data points that the surviving hypothesis must predict. |
| **Delegate** | A sub-agent, coroutine worker, or tool invoked by the orchestrator to perform bounded, mechanical reading. Does not decide what to investigate next. |
| **Divergence** | A difference between a phase's prediction (written before reading) and its findings (produced by reading). Divergences are flagged explicitly by the delegate and examined by the orchestrator. |
| **Finding** | A claim produced by a phase about the actual behavior of participant code or the actual mandate of an arbitrator. Must cite a primary source. |
| **Investigator** | The principal driving the RCA. Owns the question, the scope, and the decisions to start, halt, and stop. |
| **Orchestrator** | The agent performing prediction and verification. Owns the trace document and the per-phase loop. May be the same actor as the investigator. |
| **Participant** | A codebase that executes during the failure. Subject of investigation — its behavior is what the RCA explains. |
| **Phase** | A bounded segment of the investigation that follows the causal chain of the failure, from one natural handoff to the next. Produces a prediction, findings, review, and open questions. |
| **Prediction** | A falsifiable statement of expected causal chain, written by the orchestrator before any source is read for a phase. Recorded in the trace document. |
| **Provenance** | The citation of a primary source — `file:line` or `§:page` — for a non-trivial claim. Required for every finding. |
| **Refutation** | A phase's findings that contradict a working hypothesis. Recorded in the trace, propagated into the revised model, escalated to the investigator. |
| **Substrate** | The architectural mental model required to read the trace. Built in Stage 3 when absent. Not a deliverable; a prerequisite. |
| **Trace document** | The primary output: a living markdown document containing the scope, source indices, glossary, phase index, per-phase sections, refutation log, and conclusions. |

## Worked example index

The examples in this document are drawn from a single real
investigation: the root-cause analysis of a multi-vCPU kexec failure
under QEMU+HVF on Apple Silicon. The full trace of that investigation
lives outside this catalog, in the author's working knowledge base; it
is not reproduced here.

### Summary

- **Defect.** arm64 guest kernel kexec'd under QEMU+HVF with more than
  one vCPU prints `"CPU N: failed to come online"` for each secondary
  after a 5-second timeout. Workaround was `maxcpus=1`.
- **Entering hypothesis.** Secondaries were WFE-parked by
  `IPI_CPU_STOP`; QEMU saw them as `PSCI_ON`; `PSCI_CPU_ON` returned
  `ALREADY_ON`.
- **Actual root cause.** QEMU's `arm_set_cpu_on_async_work` in
  `target/arm/arm-powerctl.c` modifies `CPUARMState` (resets the CPU
  and writes the requested entry into `env.pc`) but does not set
  `target_cpu_state->vcpu_dirty = true`. Under HVF,
  `flush_cpu_state` (called at the top of `hvf_arch_vcpu_exec`)
  gates `hvf_arch_put_registers` on `vcpu_dirty`. With the flag
  false, the new PC never reaches HVF's hardware state; the
  secondary vCPU resumes at its last-seen PC — in overwritten
  memory after kexec — and never reaches `secondary_start_kernel`.
- **Fix.** One line: `target_cpu_state->vcpu_dirty = true;` after
  `cpu_set_pc(target_cpu_state, info->entry);`.
- **Validation.** 2×2 matrix ({bottle, vendored} × {unpatched,
  patched}) on the same host. All four cells matched prediction:
  unpatched failed at t+5/10/15 s on both build paths; patched
  succeeded in < 1 ms on both. Disassembly confirmed the `strb` store
  to `vcpu_dirty` was the sole diff in both build paths.

### How this example is used by the spec

Each stage's `Example` block in this document is extracted from
this investigation:

| Stage | What the example illustrates |
|---|---|
| 1 | The activation decision: refusing to act on the inherited hypothesis. |
| 2 | A hypothesis-free observed-symptom statement, including non-manifestation conditions. |
| 3 | Substrate built mid-investigation (arm64 exception levels, PSCI, vCPUs, trampolines). |
| 4 | Participants and arbitrators tables; vendoring and PDF-extraction commands. |
| 5 | A 15-phase decomposition along the causal chain; mid-trace merge of phases 9–13. |
| 6 | Phase 6's full loop: prediction, delegate TODO, findings, orchestrator spot-check, refutation. |
| 7 | Two preserved refutations (Phase 2's hypothesis-on-mechanism, Phase 6's race-window theory). |
| 8 | The 2×2 control matrix with predicted-vs-observed comparison. |

The example is complete on its own for a reader who wants to see the
entire investigation; it is illustrative for a reader who wants the
shape of each stage. The spec does not require readers to study the
full trace to apply the specification.
