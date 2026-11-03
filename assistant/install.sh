#!/usr/bin/env bash
# Set up the Assistant on this computer. Safe to re-run (e.g. after `git pull`).
#   cd ~/agent && bash install.sh
# It does NOT start the bot: make sure it's stopped on any other computer first.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
say()  { printf '\n== %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }
fail() { warn "$*"; exit 1; }

say "Checking prerequisites"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || fail "Python 3.10 or newer is needed (found $(python3 --version 2>&1))."
CLAUDE="$(command -v claude)" \
    || fail "Claude Code CLI not found. Install it, then run 'claude' once and log in with your Pro account."
[ -z "${ANTHROPIC_API_KEY:-}" ] \
    || fail "ANTHROPIC_API_KEY is set. Remove it (also from ~/.bashrc etc.) so the bot uses your Pro plan."
if ! timeout 120 claude -p "reply with just: ok" 2>/dev/null | grep -qi ok; then
    fail "'claude -p' didn't answer. Run 'claude' and log in first."
fi
echo "Python $(python3 --version | cut -d' ' -f2), claude at $CLAUDE, logged in."
systemctl --user is-active --quiet syncthing \
    || warn "Syncthing's user service isn't running. The vault must be synced here before the bot starts (see README)."

say "Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m py_compile main.py brain.py tools.py heartbeat.py
echo "OK"

say ".env"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
fi
chmod 600 .env
NEEDS_ENV=0
if grep -q 'paste-bot-token-here' .env || grep -q '^OWNER_ID=123456789012345678' .env; then
    NEEDS_ENV=1
    warn "Fill in DISCORD_TOKEN and OWNER_ID in $DIR/.env (or copy .env from the old computer)."
fi
VAULT="$(sed -n 's/^VAULT_PATH=//p' .env)"
VAULT="${VAULT/#\~/$HOME}"
if [ ! -d "$VAULT/.obsidian" ]; then
    NEEDS_ENV=1
    warn "VAULT_PATH in .env ($VAULT) isn't an Obsidian vault on this computer."
fi

say "systemd user service"
mkdir -p ~/.config/systemd/user
# Point the service at this checkout and put the claude CLI's folder first on its PATH
sed -e "s|%h/agent|$DIR|g" \
    -e "s|^Environment=PATH=|Environment=PATH=$(dirname "$CLAUDE"):|" \
    agent.service > ~/.config/systemd/user/agent.service
for unit in agent-snapshot.service agent-snapshot.timer; do
    sed -e "s|%h/agent|$DIR|g" "$unit" > ~/.config/systemd/user/"$unit"
done
systemctl --user daemon-reload
systemctl --user enable agent >/dev/null
systemctl --user enable --now agent-snapshot.timer >/dev/null   # hourly vault history
if ! loginctl show-user "$USER" -p Linger | grep -q 'Linger=yes'; then
    loginctl enable-linger "$USER"   # start user services at boot, without logging in
fi
echo "Installed and enabled (starts at boot), plus the hourly vault snapshot."

say "Done"
if [ "$NEEDS_ENV" = 1 ]; then
    echo "Fix the .env items above, then start the bot."
fi
cat <<EOF
Before starting: stop the bot on the old computer, or both will answer every message:
    (old computer)  systemctl --user disable --now agent
Then start it here:
    systemctl --user restart agent
    journalctl --user -u agent -f        # should say "Logged in as ..."
For a 24/7 machine, also run once:  sudo bash $DIR/always-on.sh
EOF
