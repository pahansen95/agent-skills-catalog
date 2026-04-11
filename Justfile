skills_dir := "~/.claude/skills"

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
