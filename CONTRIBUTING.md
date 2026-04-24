# Guidelines & Context

## Maintain a Work Log

Record environmental context as you work. Use git with an emphasis on keeping history clean and meaningful:

- Commit early and often; keep commits atomic. Each commit should represent one logical change.
- Enrich commits with Git Notes. Use `git notes` to attach context that doesn't belong in the commit message itself (e.g. rationale, links, follow-up tasks) without rewriting history.

### Use Git Surgically

Prefer explicit, inspectable operations over convenient shorthands to minimize unintended side effects.

- Stage explicitly by file. Never use `git add .` or `git add -A`; name each file or directory being staged.
- Inspect before staging. Run `git diff <file>` on each target before staging to confirm only intended changes are included.
- Verify the index before committing. Run `git diff --staged` after staging and before `git commit` to confirm exactly what will be recorded.
- Confirm after committing. Run `git status` after every commit to verify the working tree is clean and nothing was left behind.

## Agents

The project is developed with Agents in mind. Let the agent be your CLI: if you run your work process through the agent then it can automate administrative processes & other boilerplate. Don't offload critical thinking to the agent; it is a computer system & accountability cannot be transferred from you to it!

Authorship of work in this repo is yours. Do not include AI attribution in commit messages — no `Co-Authored-By` trailers naming AI assistants, no "Generated with" watermarks, no 🤖 markers. The AI is a tool, not an author.

## Git Hooks

Repository-tracked hooks live in `hooks/` and enforce the no-attribution rule above. Activate them per-clone:

```sh
git config core.hooksPath hooks
```

See [`hooks/README.md`](hooks/README.md) for what's enforced and how to extend the deny list.
