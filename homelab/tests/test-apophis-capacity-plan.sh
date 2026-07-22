#!/usr/bin/env bash
# Regression checks for the accepted 16 GB Apophis capacity and failover model.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
plan="${repo_root}/homelab/PLAN.md"
adr="${repo_root}/homelab/decisions/009-cluster-ha-zfs.md"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
vault_playbook="${repo_root}/homelab/ansible/playbooks/provision-vaultwarden.yml"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Fq 'Accepted 16 GB operating model (2026-07-22)' "$plan" \
  || fail 'PLAN must identify the accepted 16 GB operating model'
grep -Fq 'Refinement (2026-07-22 — Apophis reduced to 16 GB)' "$adr" \
  || fail 'ADR-009 must record the reduced-capacity decision'
grep -Fq 'Capacity-aware manual failover (VMs 118/200, when Carter is truly dead)' "$runbook" \
  || fail 'runbook must contain the Carter-loss capacity sequence'
grep -Fq 'qm shutdown 100 --timeout 60' "$runbook" \
  || fail 'Carter-loss recovery must free VM 100 memory before starting both replicas'

expected_matcher='id!~"lxc/(120|121|123|124)|qemu/(125|128)"'
grep -Fq "$expected_matcher" "$alerts" \
  || fail 'GuestDown must exclude only the accepted cold media tier and VM 128'
grep -Fq 'Intentional cold/capacity-tier guests' "$alerts" \
  || fail 'GuestDown exclusion must explain the capacity-tier exception'
grep -Fq 'targets carter' "$vault_playbook" \
  || fail 'Vaultwarden rebuild instructions must preserve its accepted Carter placement'

echo 'PASS: Apophis 16 GB capacity model is documented and alert-safe'
