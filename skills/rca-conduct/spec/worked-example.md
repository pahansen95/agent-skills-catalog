# Worked example index

> Lossless reference. Read as a companion to [`README.md`](README.md).

The examples in this specification are drawn from a single real
investigation: the root-cause analysis of a multi-vCPU kexec failure
under QEMU+HVF on Apple Silicon. The full trace of that investigation
lives outside this catalog, in the author's working knowledge base; it
is not reproduced here.

## Summary

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

## How this example is used by the spec

Each stage's `Example` block is extracted from this investigation:

| Stage | What the example illustrates |
|---|---|
| [1](stage-1-activate.md) | The activation decision: refusing to act on the inherited hypothesis. |
| [2](stage-2-observe.md) | A hypothesis-free observed-symptom statement, including non-manifestation conditions. |
| [3](stage-3-substrate.md) | Substrate built mid-investigation (arm64 exception levels, PSCI, vCPUs, trampolines). |
| [4](stage-4-sources.md) | Participants and arbitrators tables; vendoring and PDF-extraction commands. |
| [5](stage-5-decompose.md) | A 15-phase decomposition along the causal chain; mid-trace merge of phases 9–13. |
| [6](stage-6-phase-loop.md) | Phase 6's full loop: prediction, delegate TODO, findings, orchestrator spot-check, refutation. |
| [7](stage-7-refutation.md) | Two preserved refutations (Phase 2's hypothesis-on-mechanism, Phase 6's race-window theory). |
| [8](stage-8-validate.md) | The 2×2 control matrix with predicted-vs-observed comparison. |

The example is complete on its own for a reader who wants to see the
entire investigation; it is illustrative for a reader who wants the
shape of each stage. The spec does not require readers to study the
full trace to apply the specification.
