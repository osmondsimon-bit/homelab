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
require_text "$template" 'Core telemetry' 'summary must describe only the telemetry it actually aggregates'
require_text "$template" 'sum(homelab_apt_upgrades_pending)' 'summary must expose the routine update backlog'
if grep -Fq -- 'No concerns' "$template"; then
  fail 'summary must not claim that native service checks and version currency are healthy'
fi
require_text "$template" 'title: Service Directory' 'service launcher must be retained on Overview'
require_text "$template" 'title: Host Pulse' 'Overview must attribute resource pressure to each physical host'
require_text "$template" 'css-class: host-pulse' 'host pulse must have a stable responsive styling hook'
require_text "$template" 'class="host-pulse-grid"' 'host pulse must render as a compact comparison grid'
require_text "$template" 'class="host-pulse-storage-grid"' 'shared and attached storage must remain visible in host pulse'
require_text "$template" 'homelab_apt_upgrades_pending{kind="pve-host"}' 'host pulse must include routine host maintenance'
require_text "$template" 'low="70" high="85"' 'resource meters must encode warning and critical thresholds'
require_text "$template" 'storage_used:' 'host pulse must query local ZFS usage in GB'
require_text "$template" 'storage_size:' 'host pulse must query local ZFS capacity in GB'
require_text "$template" 'class="host-pulse-capacity"' 'host pulse must display local ZFS usage and capacity'
require_text "$template" 'title: Version Currency' 'configured-versus-latest currency signal is missing'
[[ "$(grep -Fc -- 'title: Version Currency' "$template")" -eq 1 ]] || fail 'version currency must render exactly once'
require_text "$template" 'User-Agent: homelab-glance-dashboard' 'GitHub release checks require a valid User-Agent'
require_text "$template" 'X-GitHub-Api-Version: 2022-11-28' 'GitHub release checks must pin an API version'
require_text "$template" 'Release checks temporarily unavailable' 'currency API failures must collapse to one honest message'
if grep -Fq -- '>Unknown<' "$template"; then
  fail 'version currency must not render a row of ambiguous Unknown statuses'
fi
require_text "$template" 'title: Workloads by Host' 'guest resources must be consolidated and grouped by host'
require_text "$template" 'data-collapse-after="5"' 'resource-ranked workloads must collapse after five rows per host'
require_text "$template" '&lt;1%' 'fractional workload CPU must not be rounded down to zero'
require_text "$template" 'VM guest filesystem usage is not collected' 'QEMU disk limitations must be explained once'
if grep -Fq -- 'not reported' "$template"; then
  fail 'QEMU disk limitations must not be repeated in every workload row'
fi
if grep -Fq -- 'title: Storage Semantics' "$template"; then
  fail 'storage implementation notes belong in documentation, not the operator surface'
fi
require_text "$template" 'id=~"storage/.*/local-zfs"' 'physical storage must use node-local ZFS backends only'
require_text "$template" 'id=~"storage/.*/pbs-oneill"' 'PBS shared capacity must be queried separately for deduplication'
require_text "$template" 'node_filesystem_size_bytes{job="node",node="apophis",mountpoint="/mnt/usb-media"}' 'Media USB capacity must use native node_exporter telemetry'
require_text "$template" 'up{job="node",node="apophis"}' 'Media USB state must distinguish host telemetry loss from mount loss'
require_text "$template" 'Media USB' 'attached media storage must be labelled by its physical role'
require_text "$template" 'Monitoring unavailable' 'missing Media USB telemetry must remain visible as an operator concern'
require_text "$template" 'Not mounted' 'an absent expected Media USB mount must remain visible as an operator concern'
require_text "$template" 'ne $guestType "qemu"' 'QEMU block allocation must not be presented as guest filesystem usage'
if grep -Fq -- 'title: Capacity Overview' "$template"; then
  fail 'redundant capacity overview must be removed after storage moves into host pulse'
fi

version_line="$(grep -n -m1 'title: Version Currency' "$template" | cut -d: -f1)"
maintenance_line="$(grep -n -m1 'title: Maintenance State' "$template" | cut -d: -f1)"
columns_line="$(grep -n -m1 '^    columns:' "$template" | cut -d: -f1)"
pulse_line="$(grep -n -m1 'title: Host Pulse' "$template" | cut -d: -f1)"
services_line="$(grep -n -m1 'title: Service Directory' "$template" | cut -d: -f1)"
(( version_line < maintenance_line )) || fail 'version currency must be visible before maintenance detail'
(( version_line < columns_line )) || fail 'version currency must remain above the fold and first on phones'
(( pulse_line < services_line )) || fail 'host pulse must sit immediately before the host-grouped services'

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
require_text "$vars" 'repository: seerr-team/seerr' 'Jellyseerr currency must follow its current upstream repository'
require_text "$playbook" 'operator.css' 'the Glance playbook must deploy the operator stylesheet'
require_text "$template" 'custom-css-file: /assets/operator.css' 'Glance must load the operator stylesheet'

[[ -f "$stylesheet" ]] || fail 'operator stylesheet is missing'
require_text "$stylesheet" '@media (max-width: 700px)' 'stylesheet must include explicit phone treatment'
require_text "$stylesheet" '@media (min-width: 1600px)' 'stylesheet must improve readability on large displays'
require_text "$stylesheet" '.resource-meter' 'stylesheet must style visual resource meters'
require_text "$stylesheet" '.version-currency-head .currency-grid' 'version currency must use a compact responsive grid'
require_text "$stylesheet" '.host-pulse-grid' 'host pulse must have responsive grid styling'
require_text "$stylesheet" '.host-pulse-storage-grid' 'host pulse must style shared and attached storage responsively'
require_text "$stylesheet" '.host-pulse-capacity' 'host pulse must style local ZFS GB detail'
require_text "$stylesheet" '.currency-unavailable' 'currency failures must have compact fallback styling'
require_text "$stylesheet" 'content: "Service Directory"' 'service launcher needs a visible section heading'
require_text "$stylesheet" 'font-size: 1rem;' 'section heading must remain readable'
require_text "$stylesheet" '.service-directory + .widget-type-monitor' 'core infrastructure must be separated from the service directory'
if grep -Fq -- 'hsl(var(--color-' "$stylesheet"; then
  fail 'Glance color variables already contain complete color values'
fi

printf 'PASS: Glance operator dashboard structure, metadata, and responsive styling are protected\n'
