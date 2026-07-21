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
require_text "$template" '- name: Media' 'Media operations page is missing'
require_text "$template" 'head-widgets:' 'Overview must lead with full-width operational signals'
require_text "$template" 'css-class: operator-summary' 'operational summary must have a stable styling hook'
require_text "$template" 'Core telemetry' 'summary must describe only the telemetry it actually aggregates'
require_text "$template" 'sum(clamp_min(homelab_apt_upgrades_pending - ignoring(policy) homelab_apt_security_upgrades_pending, 0))' \
  'summary must distinguish routine updates from security updates'
if grep -Fq -- 'No concerns' "$template"; then
  fail 'summary must not claim that native service checks and version currency are healthy'
fi
require_text "$template" 'title: Service Directory' 'service launcher must be retained on Overview'
require_text "$template" 'title: Largest Media' 'Media page must rank physical usage by movie and series'
require_text "$template" 'title: Largest Files' 'Media page must expose the largest individual files'
require_text "$template" 'title: Now Playing' 'Media page must expose Jellyfin sessions when credentials are enabled'
require_text "$template" 'title: Automation Queue' 'Media page must consolidate Sonarr and Radarr queue state'
require_text "$template" 'title: Recent Imports' 'Media page must show recent Sonarr and Radarr imports'
require_text "$template" 'title: Media Services' 'Media page must retain direct service launchers and health checks'
require_text "$template" 'title: Host Pulse' 'Overview must attribute resource pressure to each physical host'
require_text "$template" 'css-class: host-pulse' 'host pulse must have a stable responsive styling hook'
require_text "$template" 'class="host-pulse-grid"' 'host pulse must render as a compact comparison grid'
require_text "$template" 'class="host-pulse-storage-grid"' 'shared and attached storage must remain visible in host pulse'
require_text "$template" 'homelab_apt_upgrades_pending{kind="pve-host"}' 'host pulse must include routine host maintenance'
require_text "$template" 'low="70" high="85"' 'resource meters must encode warning and critical thresholds'
require_text "$template" 'storage_used:' 'host pulse must query local ZFS usage in GB'
require_text "$template" 'storage_size:' 'host pulse must query local ZFS capacity in GB'
require_text "$template" 'class="host-pulse-capacity"' 'host pulse must display local ZFS usage and capacity'
require_text "$template" 'title: Update Review' 'exception-only configured-versus-latest review is missing'
[[ "$(grep -Fc -- 'title: Update Review' "$template")" -eq 1 ]] || fail 'update review must render exactly once'
require_text "$template" 'User-Agent: homelab-glance-dashboard' 'GitHub release checks require a valid User-Agent'
require_text "$template" 'X-GitHub-Api-Version: 2022-11-28' 'GitHub release checks must pin an API version'
require_text "$template" 'Release checks temporarily unavailable' 'currency API failures must collapse to one honest message'
require_text "$template" 'No application updates to review' 'current pins must collapse to one subdued no-action message'
require_text "$template" '{{ if not $current_' 'current applications must be omitted from update-review rows'
require_text "$template" '>Review<' 'outdated pins must be presented as review work'
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
require_text "$template" 'node_systemd_unit_state{job="node",node="apophis",name="mnt-usb\\x2dmedia.mount",state="active"}' 'Media USB state must use the generated systemd mount unit'
require_text "$template" 'up{job="node",node="apophis"}' 'Media USB state must distinguish host telemetry loss from mount loss'
require_text "$template" 'Media USB' 'attached media storage must be labelled by its physical role'
require_text "$template" 'Monitoring unavailable' 'missing Media USB telemetry must remain visible as an operator concern'
require_text "$template" 'Not mounted' 'an absent expected Media USB mount must remain visible as an operator concern'
require_text "$template" 'homelab_media_storage_used_bytes' 'cached Media USB used capacity must be visible'
require_text "$template" 'homelab_media_storage_size_bytes' 'cached Media USB total capacity must be visible'
require_text "$template" 'sampled %.0fh ago' 'Media USB capacity must disclose sample age'
require_text "$template" 'ne $guestType "qemu"' 'QEMU block allocation must not be presented as guest filesystem usage'
if grep -Fq -- 'title: Capacity Overview' "$template"; then
  fail 'redundant capacity overview must be removed after storage moves into host pulse'
fi

version_line="$(grep -n -m1 'title: Update Review' "$template" | cut -d: -f1)"
maintenance_line="$(grep -n -m1 'title: Maintenance State' "$template" | cut -d: -f1)"
columns_line="$(grep -n -m1 '^    columns:' "$template" | cut -d: -f1)"
pulse_line="$(grep -n -m1 'title: Host Pulse' "$template" | cut -d: -f1)"
services_line="$(grep -n -m1 'title: Service Directory' "$template" | cut -d: -f1)"
(( version_line > maintenance_line )) || fail 'update review must sit below maintenance detail'
(( version_line > columns_line )) || fail 'update review must not occupy the above-the-fold head area'
(( pulse_line < services_line )) || fail 'host pulse must sit immediately before the host-grouped services'

require_text "$template" 'Automatic at daily patch window' 'auto-security targets must say that no immediate operator action is needed'
require_text "$template" 'Monthly action' 'manual routine updates must be labelled as planned operator work'
require_text "$template" 'Action required: reboot' 'reboot-required targets must be unmistakably actionable'
require_text "$template" 'security automatic' 'maintenance detail must distinguish automatic security work from manual routine work'
require_text "$template" '(and (eq $policy "manual-monthly") (gt $securityN 0.0))' \
  'a fully patched manual target must say no action rather than monthly action'
require_text "$template" '{{ printf "%.0f security automatic" $securityN }}' \
  'an automatic-only security backlog must identify itself without implying manual action'

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
require_text "$playbook" 'LoadCredential=jellyfin-api-key:' 'Jellyfin API key must use a systemd credential'
require_text "$playbook" 'LoadCredential=sonarr-api-key:' 'Sonarr API key must use a systemd credential'
require_text "$playbook" 'LoadCredential=radarr-api-key:' 'Radarr API key must use a systemd credential'
require_text "$playbook" 'no_log: true' 'secret deployment must suppress credential values from Ansible output'
require_text "$template" '${readFileFromEnv:GLANCE_JELLYFIN_API_KEY_FILE}' \
  'Jellyfin API calls must read the systemd credential through an environment-provided path'
require_text "$template" '${readFileFromEnv:GLANCE_SONARR_API_KEY_FILE}' \
  'Sonarr API calls must read the systemd credential through an environment-provided path'
require_text "$template" '${readFileFromEnv:GLANCE_RADARR_API_KEY_FILE}' \
  'Radarr API calls must read the systemd credential through an environment-provided path'
if grep -Eq -- '(api_key|apikey)=.*readFileFromEnv' "$template"; then
  fail 'API credentials must never be emitted into browser-visible query URLs'
fi

[[ -f "$stylesheet" ]] || fail 'operator stylesheet is missing'
require_text "$stylesheet" '@media (max-width: 700px)' 'stylesheet must include explicit phone treatment'
require_text "$stylesheet" '@media (min-width: 1600px)' 'stylesheet must improve readability on large displays'
require_text "$stylesheet" '.resource-meter' 'stylesheet must style visual resource meters'
require_text "$stylesheet" '.update-review .currency-grid' 'update review must use a compact responsive grid'
require_text "$stylesheet" '.host-pulse-grid' 'host pulse must have responsive grid styling'
require_text "$stylesheet" '.host-pulse-storage-grid' 'host pulse must style shared and attached storage responsively'
require_text "$stylesheet" '.host-pulse-capacity' 'host pulse must style local ZFS GB detail'
require_text "$stylesheet" '.currency-unavailable' 'currency failures must have compact fallback styling'
require_text "$stylesheet" '.media-storage-grid' 'Media storage summary must have responsive grid styling'
require_text "$stylesheet" '.media-consumer-row' 'largest-media rows must have dedicated responsive styling'
require_text "$stylesheet" 'content: "Service Directory"' 'service launcher needs a visible section heading'
require_text "$stylesheet" 'font-size: 1rem;' 'section heading must remain readable'
require_text "$stylesheet" '.service-directory + .widget-type-monitor' 'core infrastructure must be separated from the service directory'
if grep -Fq -- 'hsl(var(--color-' "$stylesheet"; then
  fail 'Glance color variables already contain complete color values'
fi

printf 'PASS: Glance operator dashboard structure, metadata, and responsive styling are protected\n'
