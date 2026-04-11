# Agent Skills Catalog

A catalog of behavioral specs, each in its own subproject under `catalog/`.
The `skills/*` directory allows multiple variants of a spec to coexist.

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

## The `vendor/` tree

Holds gitsubmodules for reference and specification:

| Submodule | Purpose |
|---|---|
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | Skills specification |
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's published skills |
| [openai/skills](https://github.com/openai/skills) | OpenAI's published skills |

## Skills?

I don't like the name `skill` — it anthropomorphizes a cluster of computers
running linear algebra algorithms. This project is my collection of workflows
automated via an agent: a software harness around an LLM — a high-dimensional
pattern matching machine built to guess the next most probable token.

These are procedural instructions that program an agent's behavior; equivalently,
a behavioral spec.
