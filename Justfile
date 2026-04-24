skills_dir := "~/.claude/skills"

# Per-clone setup: mount the meta/hooks orphan branch as a worktree at
# hooks/ and point core.hooksPath at it. Idempotent — safe to re-run.
# The leading underscore marks this as clone-setup, not daily-use.
_setup-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -e hooks/.git ]; then
        echo "hooks/ worktree already mounted"
    else
        git worktree add hooks meta/hooks
    fi
    git config core.hooksPath hooks
    echo "hooks active: core.hooksPath=$(git config core.hooksPath)"

# List all available domain/skill slugs.
list:
    #!/usr/bin/env bash
    set -euo pipefail
    for skill in catalog/*/skills/*/; do
        domain="${skill#catalog/}"
        domain="${domain%%/*}"
        skill_name="${skill%/}"
        skill_name="${skill_name##*/}"
        echo "${domain}/${skill_name}"
    done

# Install a skill into the skills directory.
# Usage: just install <domain/skill-name> [dest]
# Example: just install documentation/iterative-docs
install skill dest=skills_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    domain="{{ skill }}"
    skill_name="${domain#*/}"
    src="catalog/${domain%/*}/skills/${skill_name}"
    dst="${HOME}/.claude/skills/${skill_name}"
    [[ "{{ dest }}" != "~/.claude/skills" ]] && dst="{{ dest }}/${skill_name}"
    if [[ ! -d "${src}" ]]; then
        echo "error: skill not found: ${src}" >&2
        exit 1
    fi
    mkdir -p "${dst}"
    rsync -rL --delete "${src}/" "${dst}/"
    echo "installed ${skill_name} -> ${dst}"
