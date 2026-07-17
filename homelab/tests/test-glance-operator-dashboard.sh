#!/usr/bin/env bash
# Regression checks for the responsive two-page Glance operator dashboard.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
template="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"
vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
playbook="${repo_root}/homelab/ansible/playbooks/provision-glance.yml"
stylesheet="${repo_root}/homelab/ansible/files/glance/operator.css"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_text() {
  local file="$1"
  local text="$2"
  local message="$3"
  grep -Fq -- "$text" "$file" || fail "$message"
}

require_text "$template" '- name: Overview' 'Overview must be the first dashboard page'
require_text "$template" '- name: Infrastructure' 'Infrastructure detail page is missing'
require_text "$template" 'head-widgets:' 'Overview must lead with full-width operational signals'
require_text "$template" 'css-class: operator-summary' 'operational summary must have a stable styling hook'
require_text "$template" 'title: Service Directory' 'service launcher must be retained on Overview'
require_text "$template" 'low="70" high="85"' 'resource meters must encode warning and critical thresholds'
require_text "$template" 'title: Version Currency' 'configured-versus-latest currency signal is missing'
require_text "$template" 'title: Workloads by Host' 'guest resources must be consolidated and grouped by host'
require_text "$template" 'id=~"storage/.*/local-zfs"' 'physical storage must use node-local ZFS backends only'
require_text "$template" 'sort_desc(100 * max by(node)' 'capacity rows must put the most-consumed node first'
require_text "$template" 'id=~"storage/.*/pbs-oneill"' 'PBS shared capacity must be queried separately for deduplication'
require_text "$template" 'mountpoint="/mnt/usb-media"' 'media SSD capacity must be shown when its metric is available'
require_text "$template" 'not reported' 'missing VM filesystem usage must not be presented as zero percent'
require_text "$template" 'ne $guestType "qemu"' 'QEMU block allocation must not be presented as guest filesystem usage'

awk '
  /^glance_services:/ { in_services = 1; next }
  /^glance_version_currency:/ { in_services = 0 }
  in_services && /^  - / {
    if ($0 !~ /node:/ || $0 !~ /workload:/) exit 1
    count++
  }
  END { if (count == 0) exit 1 }
' "$vars" || fail 'every monitored service must declare its physical node and VM/CT identity'

require_text "$vars" 'glance_version_currency:' 'version-currency targets must be data-driven'
require_text "$playbook" 'operator.css' 'the Glance playbook must deploy the operator stylesheet'
require_text "$template" 'custom-css-file: /assets/operator.css' 'Glance must load the operator stylesheet'

[[ -f "$stylesheet" ]] || fail 'operator stylesheet is missing'
require_text "$stylesheet" '@media (max-width: 700px)' 'stylesheet must include explicit phone treatment'
require_text "$stylesheet" '.resource-meter' 'stylesheet must style visual resource meters'
if grep -Fq -- 'hsl(var(--color-' "$stylesheet"; then
  fail 'Glance color variables already contain complete color values'
fi

printf 'PASS: Glance operator dashboard structure, metadata, and responsive styling are protected\n'
