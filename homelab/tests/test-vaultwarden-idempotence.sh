#!/usr/bin/env bash
# Regression contract for rerunning Vaultwarden without a bootstrap Tailscale key.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-vaultwarden.yml"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

grep -Fq 'vw_admin_token | length >= 16' "$playbook" \
  || fail 'the admin token must remain validated'
grep -Fq "when: (ts_state.stdout | from_json).BackendState != 'Running'" "$playbook" \
  || fail 'Tailscale bootstrap must remain conditional on an unjoined node'
grep -Fq "hostvars['vaultwarden-vm'].vw_ts_authkey is match('^tskey-')" "$playbook" \
  || fail 'an unjoined node must require a scoped Tailscale bootstrap key'

if grep -Fq "that: [ \"ts_authkey is match('^tskey-')\"" "$playbook"; then
  fail 'an already-joined VM must not require a new Tailscale bootstrap key'
fi

printf 'PASS: Vaultwarden reruns allow the existing Tailscale registration\n'
