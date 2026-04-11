# Agent Skills Catalog

This project is a catalog of agent skills I have developed for quickly symlinking where ever they need to live.

Each skill has its own subproject including a README and a `skills/*` directory to allow for multiple instances of the skill to exist at any one time.

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

1. The skills spec: https://github.com/agentskills/agentskills
2. Anthropic's published skills: https://github.com/anthropics/skills
3. OpenAI's published skills: https://github.com/openai/skills
4. Other published skills & references

## Skills?

I don't like the name `skill` because we anthropomorphize a cluster of computers running linear algebra algorithms. Really this project is my collection of workflows that I automate through the use of an agent: a software harness around an LLM — a high-dimensional pattern matching machine built to guess the next most probable token.

These skills are effectively procedural instructions that program an agent's behavior; you might also hear me say `behavioral spec`.
