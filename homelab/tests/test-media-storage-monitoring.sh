#!/usr/bin/env bash
# Regression checks for expected Media USB mount, capacity, alerting, and dashboard telemetry.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/media-storage-collector.sh"
playbook="${repo_root}/homelab/ansible/playbooks/provision-media-storage-monitoring.yml"
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

[[ -x "$collector" ]] || fail 'Media USB collector is missing or not executable'
[[ -f "$playbook" ]] || fail 'Media USB monitoring playbook is missing'

mkdir -p "$tmpdir/bin" "$tmpdir/mounted" "$tmpdir/missing"
cat > "$tmpdir/bin/mountpoint-present" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == "-q" && "$2" == "/mnt/usb-media" ]]
EOF
cat > "$tmpdir/bin/mountpoint-missing" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat > "$tmpdir/bin/df" <<'EOF'
#!/usr/bin/env bash
printf 'Size Used Avail\n536870912000 107374182400 429496729600\n'
EOF
chmod +x "$tmpdir/bin/"*

NODE_NAME=apophis MOUNT_PATH=/mnt/usb-media TEXTFILE_DIR="$tmpdir/mounted" \
  MOUNTPOINT_CMD="$tmpdir/bin/mountpoint-present" DF_CMD="$tmpdir/bin/df" \
  "$collector"

metrics="$tmpdir/mounted/homelab_media_storage.prom"
require_text "$metrics" 'homelab_media_storage_mounted{node="apophis",mountpoint="/mnt/usb-media"} 1' \
  'mounted drive must emit mounted=1'
require_text "$metrics" 'homelab_media_storage_size_bytes{node="apophis",mountpoint="/mnt/usb-media"} 536870912000' \
  'mounted drive must emit total bytes'
require_text "$metrics" 'homelab_media_storage_used_bytes{node="apophis",mountpoint="/mnt/usb-media"} 107374182400' \
  'mounted drive must emit used bytes'
require_text "$metrics" 'homelab_media_storage_available_bytes{node="apophis",mountpoint="/mnt/usb-media"} 429496729600' \
  'mounted drive must emit available bytes'
grep -Eq '^homelab_media_storage_last_check_timestamp_seconds\{node="apophis"\} [0-9]+$' "$metrics" \
  || fail 'collector must emit its last successful check time'

NODE_NAME=apophis MOUNT_PATH=/mnt/usb-media TEXTFILE_DIR="$tmpdir/missing" \
  MOUNTPOINT_CMD="$tmpdir/bin/mountpoint-missing" DF_CMD="$tmpdir/bin/df" \
  "$collector"

missing_metrics="$tmpdir/missing/homelab_media_storage.prom"
require_text "$missing_metrics" 'homelab_media_storage_mounted{node="apophis",mountpoint="/mnt/usb-media"} 0' \
  'missing drive must remain visible as mounted=0'
require_text "$missing_metrics" 'homelab_media_storage_size_bytes{node="apophis",mountpoint="/mnt/usb-media"} 0' \
  'missing drive must not report the parent root filesystem capacity'
if find "$tmpdir" -type f -name 'homelab_media_storage.prom.*' | grep -q .; then
  fail 'collector must atomically promote and clean temporary metric files'
fi

require_text "$playbook" 'hosts: apophis' 'collector must be installed only on the media host'
require_text "$playbook" 'media-storage-collector.sh' 'playbook must install the collector'
require_text "$playbook" 'MOUNT_PATH={{ media_host_root }}' 'playbook must use the declared media mount path'
require_text "$playbook" 'OnUnitActiveSec=5m' 'collector must refresh every five minutes'
require_text "$playbook" 'homelab_media_storage.prom' 'playbook must verify the emitted textfile'

require_text "$alerts" 'alert: MediaStorageNotMounted' 'missing media mount alert is required'
require_text "$alerts" 'homelab_media_storage_mounted == 0' 'missing media mount alert must use the dedicated state metric'
require_text "$alerts" 'alert: MediaStorageMetricsAbsent' 'dead collector alert is required'
require_text "$alerts" 'absent(homelab_media_storage_mounted)' 'dead collector must not silently mask the mount alert'
require_text "$alerts" 'alert: MediaStorageSpaceLow' 'media capacity alert is required'
require_text "$alerts" 'homelab_media_storage_available_bytes' 'media capacity alert must use available bytes'

require_text "$glance" 'homelab_media_storage_mounted' 'Glance must distinguish an unmounted drive from missing telemetry'
require_text "$glance" 'homelab_media_storage_used_bytes' 'Glance must use dedicated Media USB usage metrics'
require_text "$glance" 'homelab_media_storage_size_bytes' 'Glance must use dedicated Media USB capacity metrics'
require_text "$glance" 'Monitoring unavailable' 'Glance must expose a missing collector series'
require_text "$glance" 'Not mounted' 'Glance must expose an expected drive that is not mounted'
if grep -Fq -- 'node_filesystem_avail_bytes{mountpoint="/mnt/usb-media"}' "$glance"; then
  fail 'Glance must not infer Media USB state from an optional generic filesystem series'
fi

printf 'PASS: Media USB mount, capacity, alert, and dashboard monitoring are protected\n'
