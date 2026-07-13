#!/usr/bin/env bash
# Emit host/VM update state and PVE LXC patch-enrollment state for Prometheus/Glance.
set -euo pipefail

TARGET_NAME="${TARGET_NAME:-$(hostname -s)}"
TARGET_KIND="${TARGET_KIND:-manual-vm}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
BOOT_DIR="${BOOT_DIR:-/boot}"
RUNNING_KERNEL="${RUNNING_KERNEL:-$(uname -r)}"
REBOOT_REQUIRED_FILE="${REBOOT_REQUIRED_FILE:-/var/run/reboot-required}"
APT_HISTORY_FILE="${APT_HISTORY_FILE:-/var/log/apt/history.log}"
APT_GET_CMD="${APT_GET_CMD:-/usr/bin/apt-get}"
PCT_CMD="${PCT_CMD:-/usr/sbin/pct}"

out="${TEXTFILE_DIR}/homelab_maintenance.prom"
mkdir -p "$TEXTFILE_DIR"
tmp="$(mktemp "${out}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

escape_label() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; :a;N;$!ba;s/\n/\\n/g'
}

emit() {
  printf '%s\n' "$1" >> "$tmp"
}

count_pending() {
  local output
  if [[ ! -x "$APT_GET_CMD" ]]; then
    printf '0 0\n'
    return
  fi
  output="$($APT_GET_CMD -s -o Debug::NoLocking=1 dist-upgrade 2>/dev/null || true)"
  awk '
    /^Inst / { total++ }
    /^Inst / && tolower($0) ~ /security/ { security++ }
    END { printf "%d %d\n", total + 0, security + 0 }
  ' <<< "$output"
}

newest_installed_kernel() {
  local pattern='vmlinuz-*'
  [[ "$TARGET_KIND" == "pve-host" ]] && pattern='vmlinuz-*-pve'
  find "$BOOT_DIR" -maxdepth 1 -type f -name "$pattern" -printf '%f\n' 2>/dev/null \
    | sed 's/^vmlinuz-//' \
    | sort -V \
    | tail -1
}

emit '# HELP homelab_reboot_required Whether a deliberate reboot is required to run the newest installed kernel.'
emit '# TYPE homelab_reboot_required gauge'
emit '# HELP homelab_apt_upgrades_pending Number of packages awaiting a deliberate upgrade.'
emit '# TYPE homelab_apt_upgrades_pending gauge'
emit '# HELP homelab_apt_security_upgrades_pending Number of pending packages identified as security updates.'
emit '# TYPE homelab_apt_security_upgrades_pending gauge'
emit '# HELP homelab_patch_enrolled Whether an LXC has an enabled and active unattended-upgrades timer.'
emit '# TYPE homelab_patch_enrolled gauge'
emit '# HELP homelab_patch_last_success_timestamp_seconds Timestamp of the most recent apt/unattended-upgrades activity.'
emit '# TYPE homelab_patch_last_success_timestamp_seconds gauge'
emit '# HELP homelab_maintenance_last_check_timestamp_seconds Timestamp of the latest successful maintenance audit.'
emit '# TYPE homelab_maintenance_last_check_timestamp_seconds gauge'

target_label="$(escape_label "$TARGET_NAME")"
newest_kernel="$(newest_installed_kernel)"
reboot_required=0
if [[ -f "$REBOOT_REQUIRED_FILE" ]] || { [[ -n "$newest_kernel" ]] && [[ "$RUNNING_KERNEL" != "$newest_kernel" ]]; }; then
  reboot_required=1
fi

read -r pending security_pending < <(count_pending)
last_patch=0
[[ -f "$APT_HISTORY_FILE" ]] && last_patch="$(stat -c %Y "$APT_HISTORY_FILE")"

emit "homelab_reboot_required{target=\"${target_label}\",kind=\"${TARGET_KIND}\"} ${reboot_required}"
emit "homelab_apt_upgrades_pending{target=\"${target_label}\",kind=\"${TARGET_KIND}\",policy=\"manual-monthly\"} ${pending}"
emit "homelab_apt_security_upgrades_pending{target=\"${target_label}\",kind=\"${TARGET_KIND}\"} ${security_pending}"
emit "homelab_patch_last_success_timestamp_seconds{target=\"${target_label}\",kind=\"${TARGET_KIND}\"} ${last_patch}"

# On PVE nodes, audit every running LXC. This checks declared maintenance intent, not just liveness:
# a newly provisioned CT is red until provision-patching.yml has enrolled its timer.
if [[ -x "$PCT_CMD" ]]; then
  while read -r ctid; do
    [[ -n "$ctid" ]] || continue
    hostname="$($PCT_CMD config "$ctid" 2>/dev/null | awk -F': *' '$1 == "hostname" { print $2; exit }')"
    [[ -n "$hostname" ]] || hostname="ct-${ctid}"
    hostname_label="$(escape_label "$hostname")"

    enrolled=0
    if $PCT_CMD exec "$ctid" -- systemctl is-enabled --quiet apt-daily-upgrade.timer >/dev/null 2>&1 \
      && $PCT_CMD exec "$ctid" -- systemctl is-active --quiet apt-daily-upgrade.timer >/dev/null 2>&1; then
      enrolled=1
    fi

    ct_output="$($PCT_CMD exec "$ctid" -- apt-get -s -o Debug::NoLocking=1 dist-upgrade 2>/dev/null || true)"
    ct_pending="$(awk '/^Inst / { count++ } END { print count + 0 }' <<< "$ct_output")"
    ct_security="$(awk '/^Inst / && tolower($0) ~ /security/ { count++ } END { print count + 0 }' <<< "$ct_output")"
    ct_last_patch="$($PCT_CMD exec "$ctid" -- stat -c %Y /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null || printf '0')"

    emit "homelab_patch_enrolled{target=\"${hostname_label}\",kind=\"lxc\",node=\"${target_label}\",id=\"${ctid}\"} ${enrolled}"
    emit "homelab_apt_upgrades_pending{target=\"${hostname_label}\",kind=\"lxc\",node=\"${target_label}\",id=\"${ctid}\",policy=\"auto-security-manual-other\"} ${ct_pending}"
    emit "homelab_apt_security_upgrades_pending{target=\"${hostname_label}\",kind=\"lxc\",node=\"${target_label}\",id=\"${ctid}\"} ${ct_security}"
    emit "homelab_patch_last_success_timestamp_seconds{target=\"${hostname_label}\",kind=\"lxc\",node=\"${target_label}\",id=\"${ctid}\"} ${ct_last_patch}"
  done < <($PCT_CMD list 2>/dev/null | awk 'NR > 1 && $2 == "running" { print $1 }')
fi

emit "homelab_maintenance_last_check_timestamp_seconds{collector=\"${target_label}\"} $(date +%s)"

chmod 0644 "$tmp"
mv -f "$tmp" "$out"
trap - EXIT
