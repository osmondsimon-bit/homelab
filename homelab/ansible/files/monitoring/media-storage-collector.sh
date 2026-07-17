#!/usr/bin/env bash
# Emit expected Media USB mount state and byte capacity for Prometheus node_exporter.
set -euo pipefail

NODE_NAME="${NODE_NAME:-$(hostname -s)}"
MOUNT_PATH="${MOUNT_PATH:-/mnt/usb-media}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
MOUNTPOINT_CMD="${MOUNTPOINT_CMD:-/usr/bin/mountpoint}"
DF_CMD="${DF_CMD:-/usr/bin/df}"

out="${TEXTFILE_DIR}/homelab_media_storage.prom"
mkdir -p "$TEXTFILE_DIR"
tmp="$(mktemp "${out}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

escape_label() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; :a;N;$!ba;s/\n/\\n/g'
}

emit() {
  printf '%s\n' "$1" >> "$tmp"
}

mounted=0
size=0
used=0
available=0

# Test the exact mountpoint before calling df. Without this guard, df would report the
# parent root filesystem when the expected USB drive is absent.
if "$MOUNTPOINT_CMD" -q "$MOUNT_PATH"; then
  read -r size used available < <(
    "$DF_CMD" -B1 --output=size,used,avail "$MOUNT_PATH" | awk 'NR == 2 { print $1, $2, $3 }'
  )
  [[ "$size" =~ ^[0-9]+$ && "$used" =~ ^[0-9]+$ && "$available" =~ ^[0-9]+$ ]]
  mounted=1
fi

node_label="$(escape_label "$NODE_NAME")"
mount_label="$(escape_label "$MOUNT_PATH")"
labels="node=\"${node_label}\",mountpoint=\"${mount_label}\""

emit '# HELP homelab_media_storage_mounted Whether the expected Media USB filesystem is mounted.'
emit '# TYPE homelab_media_storage_mounted gauge'
emit '# HELP homelab_media_storage_size_bytes Total bytes on the expected Media USB filesystem.'
emit '# TYPE homelab_media_storage_size_bytes gauge'
emit '# HELP homelab_media_storage_used_bytes Used bytes on the expected Media USB filesystem.'
emit '# TYPE homelab_media_storage_used_bytes gauge'
emit '# HELP homelab_media_storage_available_bytes Bytes available to unprivileged processes on the expected Media USB filesystem.'
emit '# TYPE homelab_media_storage_available_bytes gauge'
emit '# HELP homelab_media_storage_last_check_timestamp_seconds Timestamp of the latest successful Media USB check.'
emit '# TYPE homelab_media_storage_last_check_timestamp_seconds gauge'
emit "homelab_media_storage_mounted{${labels}} ${mounted}"
emit "homelab_media_storage_size_bytes{${labels}} ${size}"
emit "homelab_media_storage_used_bytes{${labels}} ${used}"
emit "homelab_media_storage_available_bytes{${labels}} ${available}"
emit "homelab_media_storage_last_check_timestamp_seconds{node=\"${node_label}\"} $(date +%s)"

chmod 0644 "$tmp"
mv -f "$tmp" "$out"
trap - EXIT
