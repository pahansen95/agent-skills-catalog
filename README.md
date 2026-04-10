# Agent Skills Catalog

This project is a catalog of agent skills I have developed for quickly symlinking where ever they need to live.

This project doesn't maintain a raw list of skills. Instead each skill has it's own subproject including a README and a `skills/*` directory to allow for multiple instances of the skill to exist at any one time.

The most basic scenario is:

```
catalog/
  <name>/
    README.md               -- a simple skill
    skills/<name>/SKILL.md  -- symlink back to README.md
```

But the more complex scenario is:

```
catalog/
  <domain>/
    README.md                   -- a complex domain topic w/ multiple facets
    skills/<facet-a>/SKILL.md   -- skill tuned for A
    skills/<facet-z>/SKILL.md   -- skill tuned for B
```

The `vendor/` tree holds gitsubmodules to:

1. The skills spec: https://github.com/agentskills/agentskills
2. Anthropic's published skills: https://github.com/anthropics/skills
3. OpenAI's published skills: https://github.com/openai/skills
4. Other published skills & references

## Skills?

I don't like the name `skill` because we anthropomorphize a cluster of computers running linear algebra algorithms. Really this project is my collection of workflows that I automate through the use of an agent: a software harness around an LLM — a high-dimensional pattern matching machine built to guess the next most probable token.

These skills are effectively procedural instructions that program an agent's behavior; you might also hear me say `behavioral spec`.
