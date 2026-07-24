#!/usr/bin/env bash
# Regression tests for persistent failure-only ZFS, disk, kernel, and memory monitoring.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/host-health-collector.sh"
playbook="${repo_root}/homelab/ansible/playbooks/install-node-exporter.yml"
rules_playbook="${repo_root}/homelab/ansible/playbooks/deploy-monitoring-rules.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_text() {
  local file="$1" text="$2" message="$3"
  grep -Fq -- "$text" "$file" || fail "$message"
}

reject_text() {
  local file="$1" text="$2" message="$3"
  if grep -Fq -- "$text" "$file"; then
    fail "$message"
  fi
}

assert_metric() {
  local file="$1" pattern="$2"
  grep -Eq "$pattern" "$file" || fail "missing metric matching: $pattern"
}

[[ -x "$collector" ]] || fail 'host health collector is missing or not executable'

cat > "$tmpdir/zpool" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "list" ]]; then
  printf 'rpool\n'
  exit 0
fi

if [[ "${HEALTH_CASE:-clean}" == "failing" ]]; then
  cat <<'OUT'
  pool: rpool
 state: DEGRADED
  scan: scrub repaired 4K in 00:00:12 with 1 errors on Sun Jul 12 00:24:13 2026
config:

        NAME       STATE     READ WRITE CKSUM
        rpool      DEGRADED     1     0     2
          disk-0   DEGRADED     1     0     2

errors: Permanent errors have been detected
OUT
else
  cat <<'OUT'
  pool: rpool
 state: ONLINE
  scan: scrub repaired 0B in 00:00:12 with 0 errors on Sun Jul 12 00:24:13 2026
config:

        NAME       STATE     READ WRITE CKSUM
        rpool      ONLINE       0     0     0
          disk-0   ONLINE       0     0     0

errors: No known data errors
OUT
fi
EOF

cat > "$tmpdir/smartctl" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "--scan-open" ]]; then
  printf '/dev/nvme0 -d nvme # test device\n'
  exit 0
fi

if [[ "${HEALTH_CASE:-clean}" == "failing" ]]; then
  cat <<'OUT'
SMART overall-health self-assessment test result: FAILED!
Critical Warning:                   0x01
Temperature:                        75 Celsius
Percentage Used:                    99%
Unsafe Shutdowns:                   221
Media and Data Integrity Errors:    3
OUT
else
  cat <<'OUT'
SMART overall-health self-assessment test result: PASSED
Critical Warning:                   0x00
Temperature:                        30 Celsius
Percentage Used:                    7%
Unsafe Shutdowns:                   218
Media and Data Integrity Errors:    0
OUT
fi
EOF

cat > "$tmpdir/journalctl" <<'EOF'
#!/usr/bin/env bash
if [[ "${HEALTH_CASE:-clean}" == "failing" ]]; then
  printf 'kernel: mce: Hardware Error: Machine check events logged\n'
else
  printf 'kernel: EDAC MC: Ver: 3.0.0\n'
fi
EOF
chmod +x "$tmpdir/zpool" "$tmpdir/smartctl" "$tmpdir/journalctl"

run_case() {
  local name="$1"
  mkdir -p "$tmpdir/$name/textfile"
  HEALTH_CASE="$name" \
  NODE_NAME=apophis \
  TEXTFILE_DIR="$tmpdir/$name/textfile" \
  ZPOOL_CMD="$tmpdir/zpool" \
  SMARTCTL_CMD="$tmpdir/smartctl" \
  JOURNALCTL_CMD="$tmpdir/journalctl" \
  "$collector"
}

run_case clean
clean_metrics="$tmpdir/clean/textfile/homelab_host_health.prom"
assert_metric "$clean_metrics" 'homelab_zfs_pool_healthy\{node="apophis",pool="rpool"\} 1'
assert_metric "$clean_metrics" 'homelab_zfs_pool_read_errors\{node="apophis",pool="rpool"\} 0'
assert_metric "$clean_metrics" 'homelab_zfs_pool_write_errors\{node="apophis",pool="rpool"\} 0'
assert_metric "$clean_metrics" 'homelab_zfs_pool_checksum_errors\{node="apophis",pool="rpool"\} 0'
assert_metric "$clean_metrics" 'homelab_zfs_known_data_errors\{node="apophis",pool="rpool"\} 0'
assert_metric "$clean_metrics" 'homelab_zfs_last_scrub_errors\{node="apophis",pool="rpool"\} 0'
assert_metric "$clean_metrics" 'homelab_smart_device_healthy\{node="apophis",device="/dev/nvme0"\} 1'
assert_metric "$clean_metrics" 'homelab_smart_device_temperature_celsius\{node="apophis",device="/dev/nvme0"\} 30'
assert_metric "$clean_metrics" 'homelab_nvme_critical_warning\{node="apophis",device="/dev/nvme0"\} 0'
assert_metric "$clean_metrics" 'homelab_nvme_media_errors\{node="apophis",device="/dev/nvme0"\} 0'
assert_metric "$clean_metrics" 'homelab_nvme_unsafe_shutdowns\{node="apophis",device="/dev/nvme0"\} 218'
assert_metric "$clean_metrics" 'homelab_kernel_hardware_error_events\{node="apophis"\} 0'
assert_metric "$clean_metrics" 'homelab_host_health_last_check_timestamp_seconds\{node="apophis"\} [0-9]+'

run_case failing
failing_metrics="$tmpdir/failing/textfile/homelab_host_health.prom"
assert_metric "$failing_metrics" 'homelab_zfs_pool_healthy\{node="apophis",pool="rpool"\} 0'
assert_metric "$failing_metrics" 'homelab_zfs_pool_read_errors\{node="apophis",pool="rpool"\} 1'
assert_metric "$failing_metrics" 'homelab_zfs_pool_checksum_errors\{node="apophis",pool="rpool"\} 2'
assert_metric "$failing_metrics" 'homelab_zfs_known_data_errors\{node="apophis",pool="rpool"\} 1'
assert_metric "$failing_metrics" 'homelab_zfs_last_scrub_errors\{node="apophis",pool="rpool"\} 1'
assert_metric "$failing_metrics" 'homelab_smart_device_healthy\{node="apophis",device="/dev/nvme0"\} 0'
assert_metric "$failing_metrics" 'homelab_smart_device_temperature_celsius\{node="apophis",device="/dev/nvme0"\} 75'
assert_metric "$failing_metrics" 'homelab_nvme_critical_warning\{node="apophis",device="/dev/nvme0"\} 1'
assert_metric "$failing_metrics" 'homelab_nvme_media_errors\{node="apophis",device="/dev/nvme0"\} 3'
assert_metric "$failing_metrics" 'homelab_kernel_hardware_error_events\{node="apophis"\} 1'

require_text "$playbook" 'homelab-host-health.timer' \
  'the persistent health collector timer must be deployed'
require_text "$playbook" 'prometheus-node-exporter-smartmon.timer' \
  'the distro SMART collector timer must be repaired and enabled on every host'
require_text "$playbook" 'zfs-scrub-monthly@rpool.timer' \
  'every rpool must receive the native monthly scrub timer'
require_text "$playbook" 'zfs-trim-monthly@rpool.timer' \
  'consumer SSD pools must use the native periodic trim timer'
reject_text "$playbook" 'zpool set autotrim=on' \
  'continuous autotrim must not be enabled incidentally on consumer SSDs'

[[ -f "$rules_playbook" ]] || fail 'focused monitoring-rule deployment playbook is missing'
require_text "$rules_playbook" 'promtool check rules' \
  'candidate Prometheus rules must be validated before deployment'
require_text "$rules_playbook" '/tmp/homelab-alert-rules.candidate.yml' \
  'alert rules must be staged separately from the live file'
require_text "$rules_playbook" 'systemctl reload prometheus' \
  'validated alert rules must be loaded without restarting the monitoring stack'

for alert in \
  HostHealthCollectorAbsent \
  HostHealthCollectorStale \
  ZFSPoolUnhealthy \
  ZFSPoolErrors \
  ZFSKnownDataErrors \
  ZFSScrubFailed \
  ZFSScrubStale \
  SmartMetricsAbsent \
  SmartDeviceUnhealthy \
  SmartMediaIndicators \
  SmartCRCErrors \
  NVMeCriticalWarning \
  NVMeMediaErrors \
  NVMeWearHigh \
  NVMeUnsafeShutdown \
  DiskTemperatureHigh \
  KernelHardwareError \
  ApophisMemoryGuardrail; do
  require_text "$alerts" "alert: $alert" "missing failure-only alert: $alert"
done

reject_text "$alerts" 'alert: HostHealthPass' \
  'healthy host checks must never generate an alert'
reject_text "$collector" 'curl' \
  'the collector must emit metrics only, not send PASS/FAIL notifications directly'
if grep -Eq 'zpool (clear|scrub|trim|set)|smartctl .*-(t|X)|systemctl reboot|(^|[[:space:]])reboot([[:space:]]|$)' "$collector"; then
  fail 'the health collector must remain read-only'
fi

require_text "$runbook" 'Persistent host hardware and ZFS health' \
  'deployment, interpretation, and failure response must be documented'
require_text "$runbook" 'One-at-a-time hardware confidence tests' \
  'SMART, memory, and reboot maintenance must be staged in the runbook'
require_text "$runbook" 'Power-continuity validation' \
  'power transfer and graceful-shutdown testing must be explicit'

printf 'PASS: persistent host health monitoring is failure-only and maintenance-safe\n'
