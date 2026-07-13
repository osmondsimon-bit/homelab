#!/usr/bin/env bash
# Regression tests for the maintenance textfile collector: kernel reboot detection and LXC patch enrollment.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/maintenance-collector.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_metric() {
  local file="$1" pattern="$2"
  grep -Eq "$pattern" "$file" || fail "missing metric matching: $pattern"
}

make_fake_apt() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env bash
cat <<'OUT'
Inst package-one [1.0] (1.1 Debian:stable [amd64])
Inst package-two [2.0] (2.1 Debian-Security:stable-security [amd64])
OUT
EOF
  chmod +x "$path"
}

run_kernel_case() {
  local running="$1" installed="$2" expected="$3"
  local case_dir="$tmpdir/kernel-$expected-$installed"
  mkdir -p "$case_dir/boot" "$case_dir/textfile"
  : > "$case_dir/boot/vmlinuz-$installed"
  make_fake_apt "$case_dir/apt-get"

  TARGET_NAME=apophis \
  TARGET_KIND=pve-host \
  TEXTFILE_DIR="$case_dir/textfile" \
  BOOT_DIR="$case_dir/boot" \
  RUNNING_KERNEL="$running" \
  REBOOT_REQUIRED_FILE="$case_dir/reboot-required" \
  APT_GET_CMD="$case_dir/apt-get" \
  PCT_CMD="$case_dir/no-pct" \
  "$collector"

  assert_metric "$case_dir/textfile/homelab_maintenance.prom" \
    "homelab_reboot_required\\{target=\"apophis\",kind=\"pve-host\"\\} $expected"
}

# A newly installed PVE kernel must report a required reboot even when
# /var/run/reboot-required is absent (the Proxmox behaviour that regressed).
run_kernel_case "6.8.12-9-pve" "6.8.12-10-pve" 1
run_kernel_case "6.8.12-10-pve" "6.8.12-10-pve" 0

# A package-created reboot flag must also be honoured.
flag_dir="$tmpdir/flag"
mkdir -p "$flag_dir/boot" "$flag_dir/textfile"
: > "$flag_dir/boot/vmlinuz-6.8.12-10-pve"
: > "$flag_dir/reboot-required"
make_fake_apt "$flag_dir/apt-get"
TARGET_NAME=oneill TARGET_KIND=pve-host TEXTFILE_DIR="$flag_dir/textfile" \
  BOOT_DIR="$flag_dir/boot" RUNNING_KERNEL="6.8.12-10-pve" \
  REBOOT_REQUIRED_FILE="$flag_dir/reboot-required" APT_GET_CMD="$flag_dir/apt-get" \
  PCT_CMD="$flag_dir/no-pct" "$collector"
assert_metric "$flag_dir/textfile/homelab_maintenance.prom" \
  'homelab_reboot_required\{target="oneill",kind="pve-host"\} 1'

# The collector must retain an actionable package count for manual targets.
assert_metric "$flag_dir/textfile/homelab_maintenance.prom" \
  'homelab_apt_upgrades_pending\{target="oneill",kind="pve-host",policy="manual-monthly"\} 2'
assert_metric "$flag_dir/textfile/homelab_maintenance.prom" \
  'homelab_apt_security_upgrades_pending\{target="oneill",kind="pve-host"\} 1'

# PVE-side intent reconciliation must expose an unenrolled new LXC instead of silently
# treating a running guest as compliant.
pct_dir="$tmpdir/pct"
mkdir -p "$pct_dir/boot" "$pct_dir/textfile"
: > "$pct_dir/boot/vmlinuz-6.8.12-10-pve"
make_fake_apt "$pct_dir/apt-get"
cat > "$pct_dir/pct" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  list)
    printf 'VMID Status Lock Name\n110 running - tailscale\n126 running - tailscale2\n'
    ;;
  config)
    [[ "$2" == "110" ]] && printf 'hostname: tailscale\n' || printf 'hostname: tailscale2\n'
    ;;
  exec)
    ctid="$2"
    shift 3
    if [[ "$1" == "systemctl" ]]; then
      [[ "$ctid" == "110" ]]
    elif [[ "$1" == "apt-get" ]]; then
      printf 'Inst package-one [1.0] (1.1 Debian-Security:stable-security [amd64])\n'
    elif [[ "$1" == "stat" ]]; then
      printf '1234567890\n'
    fi
    ;;
esac
EOF
chmod +x "$pct_dir/pct"
TARGET_NAME=apophis TARGET_KIND=pve-host TEXTFILE_DIR="$pct_dir/textfile" \
  BOOT_DIR="$pct_dir/boot" RUNNING_KERNEL="6.8.12-10-pve" \
  REBOOT_REQUIRED_FILE="$pct_dir/reboot-required" APT_GET_CMD="$pct_dir/apt-get" \
  PCT_CMD="$pct_dir/pct" "$collector"
assert_metric "$pct_dir/textfile/homelab_maintenance.prom" \
  'homelab_patch_enrolled\{target="tailscale",kind="lxc",node="apophis",id="110"\} 1'
assert_metric "$pct_dir/textfile/homelab_maintenance.prom" \
  'homelab_patch_enrolled\{target="tailscale2",kind="lxc",node="apophis",id="126"\} 0'

printf 'PASS: maintenance collector regression tests\n'
