#!/usr/bin/env bash
# Keep this computer running 24/7 for the Assistant. Run once with: sudo bash always-on.sh
# Undo: sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
#       sudo rm /etc/systemd/logind.conf.d/10-always-on.conf /etc/udev/rules.d/90-battery-threshold.rules
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

# 1. Never suspend or hibernate: not from KDE's idle timer, the lid, the menu or a key.
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target

# 2. Closing the lid does nothing (the screen still turns off on its own).
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/10-always-on.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
IdleAction=ignore
EOF
systemctl reload systemd-logind

# 3. Battery care (laptops whose battery supports charge thresholds, e.g. ThinkPads):
#    plugged in 24/7 at 100% wears a battery out fast, so charge only between 75% and 80%.
#    The battery still covers short power cuts. Skipped on desktops.
BAT=/sys/class/power_supply/BAT0
if [ -w "$BAT/charge_control_end_threshold" ] && [ -w "$BAT/charge_control_start_threshold" ]; then
    cat > /etc/udev/rules.d/90-battery-threshold.rules <<'EOF'
ACTION=="add|change", SUBSYSTEM=="power_supply", KERNEL=="BAT0", ATTR{charge_control_end_threshold}="80", ATTR{charge_control_start_threshold}="75"
EOF
    echo 80 > "$BAT/charge_control_end_threshold"
    echo 75 > "$BAT/charge_control_start_threshold"
    echo "Battery thresholds: $(cat "$BAT/charge_control_start_threshold")-$(cat "$BAT/charge_control_end_threshold")%"
else
    echo "No battery charge thresholds on this machine; skipping battery care."
fi

echo "Done. Sleep targets:"
systemctl is-enabled sleep.target suspend.target hibernate.target || true
