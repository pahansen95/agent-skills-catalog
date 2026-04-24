skills_dir := "~/.claude/skills"
skill_tool := justfile_directory() / "tools" / "skill"

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

# List catalog skill refs as `<domain>/<name>`, one per line.
list:
    @{{ skill_tool }} list

# Install a skill.
# Usage: just install <domain/skill-name> [dest]
install skill dest=skills_dir:
    {{ skill_tool }} --dest {{ dest }} install {{ skill }}

# Uninstall a skill by name.
# Usage: just uninstall <skill-name> [dest]
uninstall name dest=skills_dir:
    {{ skill_tool }} --dest {{ dest }} uninstall {{ name }}

# Reinstall a skill. If the installed tree has scripts/reinstall, it drives
# the preserve-list contract; otherwise falls back to uninstall + install.
# Usage: just reinstall <domain/skill-name> [dest]
reinstall skill dest=skills_dir:
    {{ skill_tool }} --dest {{ dest }} reinstall {{ skill }}
