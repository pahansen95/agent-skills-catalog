# Git Hooks

Repository-tracked git hooks. Activated per-clone by pointing
`core.hooksPath` at this directory.

## Enable

After cloning:

```sh
git config core.hooksPath hooks
```

That's it. No symlinks, no install script.

## What's enforced

- **`commit-msg`** — rejects commit messages containing AI ownership
  claims (Co-Authored-By trailers, "Generated with" watermarks,
  🤖 watermarks).
- **`pre-push`** — re-scans every commit in the push range for the
  same patterns. Defense-in-depth against `--no-verify` bypasses,
  hook swaps, or commits authored before the hooks were enabled.

The pattern lives in [`lib/ai-attribution-pattern.sh`](lib/ai-attribution-pattern.sh)
and is sourced by both hooks. To extend the deny list, edit that
file only.

## Why

Authorship of work in this repo is the human's. AI tools assist;
they do not co-author or generate commits in any attributable
sense. Stripping these markers keeps history honest about
accountability.

## Bypassing

`--no-verify` on commit bypasses `commit-msg`; `pre-push` will
catch it. `--no-verify` on push bypasses both — but at that point
you're explicitly opting out, and the next person to look at the
log will see the mark. Don't.
