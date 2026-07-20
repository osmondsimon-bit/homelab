#!/usr/bin/env bash
# Regression contract for the in-place Jellyseerr-to-Seerr migration on VM 125.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
playbook="$repo_root/ansible/playbooks/provision-jellyseerr.yml"
vars="$repo_root/ansible/inventory/group_vars/all.yml.example"
component="$repo_root/docs/components/jellyseerr.md"

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

require_text "$vars" 'depName=ghcr.io/seerr-team/seerr' \
  'Renovate must track the official Seerr image'
require_text "$vars" 'seerr_image: "ghcr.io/seerr-team/seerr:v3.3.0"' \
  'Seerr must use the exact approved stable release'
reject_text "$vars" 'fallenbagel/jellyseerr' \
  'the retired Jellyseerr image must not remain in deployment defaults'

require_text "$playbook" '            seerr:' \
  'Compose must use the official Seerr service name'
require_text "$playbook" '              image: {{ seerr_image }}' \
  'Compose must consume the pinned Seerr image variable'
require_text "$playbook" '              container_name: seerr' \
  'the application container must be named seerr'
require_text "$playbook" '              init: true' \
  'the official image requires a container init process'
require_text "$playbook" 'owner: "1000"' \
  'the Seerr config tree must be writable by UID 1000'
require_text "$playbook" 'group: "1000"' \
  'the Seerr config tree must be writable by GID 1000'
require_text "$playbook" 'http://localhost:5055/api/v1/settings/public' \
  'Compose must use the official public health endpoint'
require_text "$playbook" 'http://127.0.0.1:{{ jellyseerr_port }}/api/v1/status' \
  'the existing status verification contract must remain available'
require_text "$playbook" 'no-new-privileges:true' \
  'the existing container privilege restriction must survive migration'
reject_text "$playbook" '--force-recreate' \
  'a Seerr change must not force-recreate the Prowlarr VPN sidecars'

require_text "$component" '# Seerr (VM 125)' \
  'the component documentation must use the current product name'
require_text "$component" '`ghcr.io/seerr-team/seerr:v3.3.0`' \
  'the component documentation must record the deployed image'

printf 'PASS: Seerr migration regression contract\n'
