# Agent Skills Catalog

A flat registry of behavioral specifications. Each skill is self-contained in
`skills/<name>/`, with `SKILL.md` as its entry point and any code, references,
or templates it needs beside it.

I don't like the name `skill` — it anthropomorphizes a cluster of computers
running linear algebra algorithms. This project is my collection of workflows
automated via an agent: a software harness around an LLM — a high-dimensional
pattern matching machine built to guess the next most probable token.

These are procedural instructions that program an agent's behavior;
equivalently, a behavioral spec.

```
skills/
├── coro-develop/
├── epistemic/
├── iterative-docs/
├── iso-24495/
├── playwright-service/
├── rca-conduct/
└── salience/
```

| Skill | Purpose |
|---|---|
| [`coro-develop`](skills/coro-develop/SKILL.md) | Orchestrate a stateful, resumable worker session. |
| [`epistemic`](skills/epistemic/SKILL.md) | Make factual claims traceable to their support. |
| [`iterative-docs`](skills/iterative-docs/SKILL.md) | Write long documents incrementally with a structure-first approach. |
| [`iso-24495`](skills/iso-24495/SKILL.md) | Write reader-centred plain-language communication, with routed guidance for legal, science, document-design, and organisational-practice work. |
| [`playwright-service`](skills/playwright-service/SKILL.md) | Use the shared Playwright browser automation service. |
| [`rca-conduct`](skills/rca-conduct/SKILL.md) | Conduct a cited, control-validated root-cause analysis. |
| [`salience`](skills/salience/SKILL.md) | Shape natural-language communication to the reader's capacity. |

This repository is a registry, not an installer. Make a skill directory
available through the skill mechanism used by your agent host; no automatic
discovery of `.agent/skill` directories is provided here.

`coro-develop` requires Deno 2.9.6 or newer and the `claude` CLI at runtime;
its launcher uses the skill-local Deno configuration and preserves the caller's
working directory. `rca-conduct` requires `iterative-docs` and `coro-develop`
to be available in the same session. Coroutine workers activate `/salience on`
for their worker-role preamble.

## What a skill is and how to draft one

A skill is a workflow: it takes inputs, produces an output, and may fail
instead. It works against some state, and owns a small, named set of
responsibilities — everything outside that set is explicitly not its concern.

Skills compose through behaviors: replaceable parts defined by a contract. A
skill can delegate a behavior without prescribing which available skill or
host mechanism supplies it. Settings are plain values that tune a run.
`rca-conduct` is explicit about its two required skills because its operational
contract uses their behaviors; those dependencies are listed above.

To draft one:

- Name the responsibilities it owns, and — just as explicitly — its non-goals.
- Define its contract: the inputs, the output, how it fails, and the state it works against.
- Separate delegated behaviors from settings, and ship a default for each behavior so the skill stands alone.
- State the invariants it holds throughout.
- Put its complete entry point at `skills/<name>/SKILL.md`; keep supporting files in that directory.
- Use YAML frontmatter (`name`, `description`, `metadata.version`) and follow the repository's git discipline.

## The `vendor/` tree

Holds git submodules for reference and specification:

| Submodule | Purpose |
|---|---|
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | Skills specification |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's published skills |
| [openai/skills](https://github.com/openai/skills) | OpenAI's published skills |
