#!/usr/bin/env bash
# Cache Media USB filesystem capacity for Prometheus without probing it on every scrape.
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

if ! "$MOUNTPOINT_CMD" -q "$MOUNT_PATH"; then
  # Mount state comes from node_exporter's systemd collector. Preserve the last successful
  # capacity sample instead of replacing it with the host root filesystem or zeroes.
  exit 0
fi

read -r size used available < <(
  "$DF_CMD" -B1 --output=size,used,avail "$MOUNT_PATH" | awk 'NR == 2 { print $1, $2, $3 }'
)
[[ "$size" =~ ^[0-9]+$ && "$used" =~ ^[0-9]+$ && "$available" =~ ^[0-9]+$ ]]

node_label="$(escape_label "$NODE_NAME")"
mount_label="$(escape_label "$MOUNT_PATH")"
labels="node=\"${node_label}\",mountpoint=\"${mount_label}\""

{
  printf '%s\n' '# HELP homelab_media_storage_size_bytes Cached total bytes on the Media USB filesystem.'
  printf '%s\n' '# TYPE homelab_media_storage_size_bytes gauge'
  printf '%s\n' '# HELP homelab_media_storage_used_bytes Cached used bytes on the Media USB filesystem.'
  printf '%s\n' '# TYPE homelab_media_storage_used_bytes gauge'
  printf '%s\n' '# HELP homelab_media_storage_available_bytes Cached bytes available to unprivileged processes.'
  printf '%s\n' '# TYPE homelab_media_storage_available_bytes gauge'
  printf '%s\n' '# HELP homelab_media_storage_last_check_timestamp_seconds Timestamp of the latest successful capacity sample.'
  printf '%s\n' '# TYPE homelab_media_storage_last_check_timestamp_seconds gauge'
  printf 'homelab_media_storage_size_bytes{%s} %s\n' "$labels" "$size"
  printf 'homelab_media_storage_used_bytes{%s} %s\n' "$labels" "$used"
  printf 'homelab_media_storage_available_bytes{%s} %s\n' "$labels" "$available"
  printf 'homelab_media_storage_last_check_timestamp_seconds{node="%s"} %s\n' "$node_label" "$(date +%s)"
} > "$tmp"

chmod 0644 "$tmp"
mv -f "$tmp" "$out"
trap - EXIT
