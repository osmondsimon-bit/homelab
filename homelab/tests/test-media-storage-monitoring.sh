#!/usr/bin/env bash
# Regression checks for safe mount-state and low-frequency cached Media USB capacity telemetry.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/media-storage-collector.sh"
collector_playbook="${repo_root}/homelab/ansible/playbooks/provision-media-storage-monitoring.yml"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
node_exporter_playbook="${repo_root}/homelab/ansible/playbooks/install-node-exporter.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
glance="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"
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

[[ -x "$collector" ]] || fail 'Media USB cached-capacity collector is missing or not executable'
[[ -f "$collector_playbook" ]] || fail 'Media USB monitoring playbook is missing'
require_text "$collector" 'mountpoint' 'capacity sampling must guard against an absent USB mount'
require_text "$collector" 'df' 'capacity sampling must use a filesystem allocation query'
require_text "$collector" 'homelab_media_storage_last_check_timestamp_seconds' \
  'cached capacity must include its sample timestamp'
require_text "$collector_playbook" 'OnUnitActiveSec=6h' \
  'capacity sampling must be low-frequency rather than the retired five-minute cadence'
require_text "$collector_playbook" 'OnBootSec=15m' \
  'capacity sampling must not probe the USB immediately during host boot'

mkdir -p "$tmpdir/textfile"
cat > "$tmpdir/mountpoint" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$tmpdir/df" <<'EOF'
#!/usr/bin/env bash
printf '1B-blocks Used Available\n500000000000 125000000000 375000000000\n'
EOF
chmod +x "$tmpdir/mountpoint" "$tmpdir/df"
NODE_NAME=apophis MOUNT_PATH=/mnt/usb-media TEXTFILE_DIR="$tmpdir/textfile" \
  MOUNTPOINT_CMD="$tmpdir/mountpoint" DF_CMD="$tmpdir/df" "$collector"
metrics="$tmpdir/textfile/homelab_media_storage.prom"
require_text "$metrics" 'homelab_media_storage_size_bytes{node="apophis",mountpoint="/mnt/usb-media"} 500000000000' \
  'collector must cache the exact filesystem size'
require_text "$metrics" 'homelab_media_storage_used_bytes{node="apophis",mountpoint="/mnt/usb-media"} 125000000000' \
  'collector must cache the exact used bytes'
cp "$metrics" "$tmpdir/previous.prom"
sed -i 's/exit 0/exit 1/' "$tmpdir/mountpoint"
NODE_NAME=apophis MOUNT_PATH=/mnt/usb-media TEXTFILE_DIR="$tmpdir/textfile" \
  MOUNTPOINT_CMD="$tmpdir/mountpoint" DF_CMD="$tmpdir/df" "$collector"
cmp -s "$metrics" "$tmpdir/previous.prom" \
  || fail 'an absent mount must preserve the last successful sample rather than report rootfs or zero'

require_text "$monitoring_playbook" 'labels: { node: "{{ n.name }}" }' \
  'PVE node_exporter targets must carry a stable node label'
require_text "$monitoring_playbook" 'targets: ["{{ n.host }}:9100"]' \
  'each labelled PVE node_exporter target must use its declared host address'

require_text "$node_exporter_playbook" 'inventory_hostname == "apophis"' \
  'the Media USB systemd collector must be scoped to apophis'
require_text "$node_exporter_playbook" '--collector.systemd' \
  'apophis node_exporter must enable the built-in systemd collector'
require_text "$node_exporter_playbook" '--collector.systemd.unit-include=^mnt-usb.*media[.]mount$' \
  'the systemd collector must include only the Media USB mount unit'
require_text "$node_exporter_playbook" '--collector.systemd.unit-exclude=^$' \
  'the systemd collector default exclusion of mount units must be cleared'

require_text "$alerts" 'alert: MediaStorageNotMounted' 'missing media mount alert is required'
require_text "$alerts" 'up{job="node", node="apophis"} == 1' \
  'missing mount alert must fire only while the apophis exporter is reachable'
require_text "$alerts" 'unless on(node)' \
  'missing mount alert must distinguish host loss from mount loss'
require_text "$alerts" 'node_systemd_unit_state{job="node", node="apophis", name="mnt-usb\\x2dmedia.mount", state="active"} == 1' \
  'missing mount alert must use the generated systemd mount unit state'
require_text "$alerts" 'alert: MediaStorageSpaceLow' \
  'cached Media USB capacity must alert when operator action is required'
require_text "$alerts" 'alert: MediaStorageCapacityStale' \
  'a failed low-frequency capacity collector must not silently retain old data'
require_text "$alerts" 'absent(homelab_media_storage_last_check_timestamp_seconds{node="apophis"})' \
  'a mounted disk with no first capacity sample must be actionable'
reject_text "$alerts" 'node_filesystem_size_bytes{job="node", node="apophis", mountpoint="/mnt/usb-media"}' \
  'Media USB alerts must use cached metrics rather than scrape-time filesystem probes'
reject_text "$alerts" 'node_filesystem_avail_bytes{job="node", node="apophis", mountpoint="/mnt/usb-media"}' \
  'Media USB alerts must not query filesystem availability at scrape time'

require_text "$glance" 'up{job="node",node="apophis"}' \
  'Glance must distinguish unavailable apophis telemetry from a missing mount'
require_text "$glance" 'node_systemd_unit_state{job="node",node="apophis",name="mnt-usb\\x2dmedia.mount",state="active"}' \
  'Glance must use the generated systemd mount unit state'
reject_text "$glance" 'node_filesystem_' \
  'Glance must consume cached metrics rather than probe the Media USB filesystem at page load'
require_text "$glance" 'Monitoring unavailable' 'Glance must expose an unavailable exporter'
require_text "$glance" 'Not mounted' 'Glance must expose an absent expected mount'
require_text "$glance" 'Mounted' 'Glance must expose an active expected mount'
require_text "$glance" 'homelab_media_storage_used_bytes' 'Glance must show cached used capacity'
require_text "$glance" 'homelab_media_storage_size_bytes' 'Glance must show cached total capacity'
require_text "$glance" 'homelab_media_storage_last_check_timestamp_seconds' 'Glance must show capacity sample age'

printf 'PASS: safe mount-state and cached Media USB capacity monitoring is protected\n'
