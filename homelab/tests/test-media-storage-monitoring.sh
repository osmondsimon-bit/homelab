#!/usr/bin/env bash
# Regression checks for safe Media USB mount-state alerting and dashboard telemetry.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/media-storage-collector.sh"
collector_playbook="${repo_root}/homelab/ansible/playbooks/provision-media-storage-monitoring.yml"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
node_exporter_playbook="${repo_root}/homelab/ansible/playbooks/install-node-exporter.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
glance="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"

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

[[ ! -e "$collector" ]] || fail 'Media USB must not have a custom host collector'
[[ ! -e "$collector_playbook" ]] || fail 'Media USB must not have a custom host provisioning playbook'

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
reject_text "$alerts" 'alert: MediaStorageSpaceLow' \
  'Media USB capacity must not be probed after the host-lock incident'
reject_text "$alerts" 'node_filesystem_size_bytes{job="node", node="apophis", mountpoint="/mnt/usb-media"}' \
  'Media USB alerts must not query filesystem size'
reject_text "$alerts" 'node_filesystem_avail_bytes{job="node", node="apophis", mountpoint="/mnt/usb-media"}' \
  'Media USB alerts must not query filesystem availability'
reject_text "$alerts" 'MediaStorageMetricsAbsent' \
  'TargetDown already covers unavailable node_exporter telemetry'
reject_text "$alerts" 'homelab_media_storage_' \
  'alerts must not depend on retired custom Media USB metrics'

require_text "$glance" 'up{job="node",node="apophis"}' \
  'Glance must distinguish unavailable apophis telemetry from a missing mount'
require_text "$glance" 'node_systemd_unit_state{job="node",node="apophis",name="mnt-usb\\x2dmedia.mount",state="active"}' \
  'Glance must use the generated systemd mount unit state'
reject_text "$glance" 'node_filesystem_' \
  'Glance must not probe the Media USB filesystem'
require_text "$glance" 'Monitoring unavailable' 'Glance must expose an unavailable exporter'
require_text "$glance" 'Not mounted' 'Glance must expose an absent expected mount'
require_text "$glance" 'Mounted' 'Glance must expose an active expected mount'
require_text "$glance" 'Capacity not probed' 'Glance must explain the deliberate capacity omission'
reject_text "$glance" 'homelab_media_storage_' \
  'Glance must not depend on retired custom Media USB metrics'

printf 'PASS: safe Media USB systemd mount-state monitoring is protected\n'
