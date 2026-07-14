#!/usr/bin/env bash
# Regression contract for the Carter-hosted, tailnet-only Actual Budget deployment.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-actual.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
patching_playbook="${repo_root}/homelab/ansible/playbooks/provision-patching.yml"
maintenance_playbook="${repo_root}/homelab/ansible/playbooks/provision-maintenance-monitoring.yml"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
acl_reference="${repo_root}/homelab/ansible/files/tailscale-acl.hujson"
component_doc="${repo_root}/homelab/docs/components/actual-budget.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -f "$playbook" ]] || fail 'provision-actual.yml must exist'
[[ -f "$component_doc" ]] || fail 'Actual Budget component documentation must exist'

grep -Fq 'hosts: carter' "$playbook" \
  || fail 'Actual must be created on Carter only'
grep -Fq 'actual_vmid: 127' "$example_vars" \
  || fail 'Actual must use the agreed VMID 127'
grep -Fq 'actualbudget/actual-server:26.7.0' "$example_vars" \
  || fail 'Actual must use the pinned stable container release'
grep -Fq '127.0.0.1:5006:5006' "$playbook" \
  || fail 'Actual must bind only to VM loopback'
grep -Fq './data:/data' "$playbook" \
  || fail 'Actual data must persist outside the container'
grep -Fq 'ACTUAL_ALLOWED_LOGIN_METHODS=password' "$playbook" \
  || fail 'Actual must accept password login only'
grep -Fq 'no-new-privileges:true' "$playbook" \
  || fail 'the Actual container must enable no-new-privileges'
grep -Fq 'cap_drop:' "$playbook" \
  || fail 'the Actual container must drop Linux capabilities'
grep -Fq 'tailscale serve --bg --https=443 http://127.0.0.1:5006' "$playbook" \
  || fail 'Tailscale Serve must provide the only HTTPS ingress'
grep -Fq 'curl -fsS --max-time 8 http://127.0.0.1:5006' "$playbook" \
  || fail 'provisioning must include a local application smoke test'

grep -Fq 'name: actual-patching' "$patching_playbook" \
  || fail 'Actual must be enrolled in Ubuntu security patching'
grep -Fq 'when: actual_enabled | default(false) | bool' "$patching_playbook" \
  || fail 'Actual patching must remain disabled until the VM is live'
grep -Fq 'name: actual, ip: "{{ actual_ip }}"' "$maintenance_playbook" \
  || fail 'Actual must be enrolled in maintenance monitoring'
grep -Fq "(actual_ip | regex_replace('/.*$', '')) ~ ':9100'" "$monitoring_playbook" \
  || fail 'Prometheus must scrape Actual node_exporter'
grep -Fq 'tag:actual' "$acl_reference" \
  || fail 'the versioned Tailscale policy must cover Actual'

if grep -Fq 'actualbudget/actual-server:latest' "$example_vars"; then
  fail 'Actual must not use the floating latest tag'
fi

printf 'PASS: Actual Budget deployment regression contract\n'
