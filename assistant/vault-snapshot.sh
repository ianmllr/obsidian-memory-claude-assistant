#!/usr/bin/env bash
# Hourly snapshot of the vault into a git repo OUTSIDE the vault (~/vault-history),
# so every version of every note can be restored, including the assistant's own edits.
# Private/ and Obsidian's window layout are left out. Runs from agent-snapshot.timer.
#
# See what changed:      git --git-dir="$HOME/vault-history" log --stat
# Restore one note:      git --git-dir="$HOME/vault-history" --work-tree="$VAULT" checkout <commit> -- "Ideas/app ideas.md"
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT="$(sed -n 's/^VAULT_PATH=//p' "$DIR/.env")"
VAULT="${VAULT/#\~/$HOME}"
REPO="${VAULT_HISTORY:-$HOME/vault-history}"
[ -d "$VAULT/.obsidian" ] || { echo "VAULT_PATH ($VAULT) isn't an Obsidian vault" >&2; exit 1; }

git_() { git --git-dir="$REPO" --work-tree="$VAULT" "$@"; }

if [ ! -d "$REPO" ]; then
    git init -q --bare "$REPO"
    git --git-dir="$REPO" config core.bare false
    git --git-dir="$REPO" config user.name "vault-snapshot"
    git --git-dir="$REPO" config user.email "vault-snapshot@localhost"
fi
# Kept in the history repo, not the vault, so nothing extra syncs to other devices
cat > "$REPO/info/exclude" <<'EOF'
/Private/
/.stversions/
/.stfolder*
/.trash/
/.obsidian/workspace*.json
*.sync-conflict-*
*.tmp
EOF

git_ add -A
if git_ diff --cached --quiet; then
    exit 0  # nothing changed this hour
fi
git_ commit -q -m "Snapshot $(date '+%Y-%m-%d %H:%M')"
echo "Snapshot: $(git_ log -1 --format='%h %s') ($(git_ diff --stat HEAD~1 HEAD 2>/dev/null | tail -1 || echo 'first snapshot'))"
