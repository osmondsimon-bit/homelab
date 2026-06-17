#!/usr/bin/env bash
# Configure unattended SECURITY upgrades inside a Debian guest LXC (ADR-015). Idempotent —
# delivered + run via provision-patching.yml (piped to `bash -s` inside the CT). Arg $1 is the
# ntfy URL (base + private topic) for failure notifications; pass "" to skip the notify hook.
#
# Policy: security pocket only (the distro's shipped Origins-Pattern default — we don't widen it),
# NEVER auto-reboot, and apply at MIDDAY (not the ~06:00 default) so any fallout is seen while the
# operator is around rather than surfacing as dead morning automations.
set -euo pipefail
NTFY_URL="${1:-}"
PATCH_TZ="${2:-}"   # IANA tz (Region/City form) so 12:00 = LOCAL noon, DST-safe; blank = UTC
export DEBIAN_FRONTEND=noninteractive

if ! dpkg -s unattended-upgrades >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq unattended-upgrades >/dev/null
fi

# Turn the periodic update + unattended-upgrade on (security-only is the shipped default origin set).
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

# Homelab policy drop-in (ADR-015). Security-only is the distro default Origins-Pattern; we only
# assert no-auto-reboot here. Non-security updates are applied deliberately in the monthly window.
cat > /etc/apt/apt.conf.d/52homelab-unattended <<'EOF'
// Managed by Ansible (provision-patching.yml, ADR-015) — do not edit by hand.
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# Apply at 12:00 LOCAL (override the vendor ~06:00 randomized schedule). The CTs run in UTC, so we
# pin the timezone in the calendar spec (systemd >= 252) — otherwise "12:00" would be 12:00 UTC.
if [ -n "$PATCH_TZ" ]; then CAL="*-*-* 12:00 $PATCH_TZ"; else CAL="*-*-* 12:00"; fi
mkdir -p /etc/systemd/system/apt-daily-upgrade.timer.d
cat > /etc/systemd/system/apt-daily-upgrade.timer.d/override.conf <<EOF
[Timer]
OnCalendar=
OnCalendar=$CAL
RandomizedDelaySec=0
Persistent=true
EOF

# Failure notification -> ntfy, via an OnFailure hook on the upgrade service.
if [ -n "$NTFY_URL" ]; then
  command -v curl >/dev/null 2>&1 || { apt-get update -qq; apt-get install -y -qq curl >/dev/null; }
  mkdir -p /etc/homelab
  printf '%s\n' "$NTFY_URL" > /etc/homelab/ntfy-url
  chmod 600 /etc/homelab/ntfy-url
  cat > /usr/local/bin/patch-notify.sh <<'EOF'
#!/usr/bin/env bash
# Managed by Ansible (provision-patching.yml). Pushes an ntfy alert if unattended-upgrade fails.
url="$(cat /etc/homelab/ntfy-url 2>/dev/null)" || exit 0
[ -n "$url" ] || exit 0
curl -fsS --max-time 10 \
  -H "Title: Unattended-upgrade FAILED on $(hostname)" -H "Priority: high" \
  -H "Tags: rotating_light,package" \
  -d "apt-daily-upgrade.service failed — check: journalctl -u apt-daily-upgrade" \
  "$url" >/dev/null 2>&1 || true
EOF
  chmod 755 /usr/local/bin/patch-notify.sh
  cat > /etc/systemd/system/patch-notify.service <<'EOF'
[Unit]
Description=Notify ntfy on unattended-upgrade failure
[Service]
Type=oneshot
ExecStart=/usr/local/bin/patch-notify.sh
EOF
  mkdir -p /etc/systemd/system/apt-daily-upgrade.service.d
  cat > /etc/systemd/system/apt-daily-upgrade.service.d/onfailure.conf <<'EOF'
[Unit]
OnFailure=patch-notify.service
EOF
fi

systemctl daemon-reload
systemctl enable --now apt-daily.timer apt-daily-upgrade.timer >/dev/null 2>&1 || true
echo "unattended-upgrades configured on $(hostname) (security-only, no-reboot, 12:00)"
