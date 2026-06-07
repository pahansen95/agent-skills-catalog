# Agent Skills Catalog

A catalog of behavioral specs, each in its own subproject under `catalog/`.
The `skills/*` directory allows multiple variants of a spec to coexist.

I don't like the name `skill` — it anthropomorphizes a cluster of computers
running linear algebra algorithms. This project is my collection of workflows
automated via an agent: a software harness around an LLM — a high-dimensional
pattern matching machine built to guess the next most probable token.

These are procedural instructions that program an agent's behavior; equivalently,
a behavioral spec.

## Simple skill

A single behavioral spec with no supporting code:

```
catalog/
└── <name>/
    ├── README.md
    └── skills/
        └── <name>/
            └── SKILL.md        -- symlink → ../../README.md
```

## Complex domain skill

A domain covering multiple facets, each with its own behavioral spec, shared
source code, and supporting assets:

```
catalog/
└── <domain>/
    ├── README.md               -- domain overview & first principles
    ├── protocol.md             -- shared spec loaded by skills at runtime
    ├── src/
    │   └── tool.py             -- shared implementation
    └── skills/
        ├── <facet-a>/
        │   ├── SKILL.md        -- behavioral spec for facet A
        │   ├── protocol.md     -- symlink → ../../protocol.md
        │   └── scripts/
        │       ├── tool.py     -- symlink → ../../../src/tool.py
        │       ├── Justfile    -- task runner wrapping tool.py
        │       └── alias       -- shell alias → just --justfile Justfile
        └── <facet-b>/
            └── SKILL.md        -- behavioral spec for facet B
```

Key properties:
- `src/` holds the source of truth for shared code — skills reference it via symlink
- `protocol.md` is a shared spec document loaded at runtime, not inlined
- `scripts/alias` is a shell script that resolves its own location via `BASH_SOURCE`
  and delegates to `just`, so it works from any working directory
- Symlinks keep everything DRY: one file, multiple entry points

## What a skill is and how to draft one

A skill is a workflow: it takes inputs, produces an output, and may fail instead.
It works against some state, and owns a small, named set of responsibilities —
everything outside that set is explicitly not its concern.

Skills are independent. A skill never depends on another skill. If two seem to
depend on each other, they are really one composite skill (collapse them), or
they share substrate through a domain's `protocol.md` and `src/`. Composition
happens at runtime and is driven by the user, who stacks independent skills
together. A skill enables this by delegating **behaviors** — replaceable parts
defined by a contract — that another skill can satisfy without either naming the
other. This is distinct from its **settings**, which are plain values that tune a
run. Behaviors are the seams; settings are the knobs.

To draft one:

- Name the responsibilities it owns, and — just as explicitly — its non-goals.
- Define its contract: the inputs, the output, and how it fails; and the state
  it works against.
- Separate behaviors (the seams it delegates) from settings (its tunables), and
  ship a default for each behavior so the skill stands alone.
- State the invariants it holds throughout.
- Choose the layout: a simple skill, or a complex domain when shared
  `protocol.md`/`src/` is justified (see above).
- Write it as `SKILL.md` with YAML frontmatter (`name`, `description`,
  `metadata.version`). Follow the repo's git discipline: atomic commits,
  explicit staging, no AI attribution.

## The `vendor/` tree

Holds gitsubmodules for reference and specification:

| Submodule | Purpose |
|---|---|
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | Skills specification |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's published skills |
| [openai/skills](https://github.com/openai/skills) | OpenAI's published skills |
