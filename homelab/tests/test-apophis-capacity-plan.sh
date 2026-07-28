#!/usr/bin/env bash
# Regression checks for the restored 32 GB Apophis capacity and autostart model.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
plan="${repo_root}/homelab/PLAN.md"
adr="${repo_root}/homelab/decisions/009-cluster-ha-zfs.md"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
vault_playbook="${repo_root}/homelab/ansible/playbooks/provision-vaultwarden.yml"
media_playbooks=(
  "${repo_root}/homelab/ansible/playbooks/provision-jellyfin.yml"
  "${repo_root}/homelab/ansible/playbooks/provision-qbittorrent.yml"
  "${repo_root}/homelab/ansible/playbooks/provision-sonarr.yml"
  "${repo_root}/homelab/ansible/playbooks/provision-radarr.yml"
  "${repo_root}/homelab/ansible/playbooks/provision-jellyseerr.yml"
)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Fq 'Restored 32 GB operating model (2026-07-28)' "$plan" \
  || fail 'PLAN must identify the restored 32 GB operating model'
grep -Fq 'VM 200 Apophis→Carter; VM 118 Carter→Apophis' "$plan" \
  || fail 'PLAN must record the restored split replication directions'
grep -Fq 'Refinement (2026-07-28 — Apophis restored to 32 GB)' "$adr" \
  || fail 'ADR-009 must record the restored-capacity decision'
grep -Fq 'VM 200 returns to Apophis; VM 118 stays on Carter' "$adr" \
  || fail 'ADR-009 must record the restored standard placement'
grep -Fq 'Capacity-aware manual failover (VM 118, when Carter is truly dead)' "$runbook" \
  || fail 'runbook must contain the Carter-loss Vaultwarden sequence'
if grep -Fq 'qm shutdown 100 --timeout 60' "$runbook"; then
  fail 'Carter-loss recovery must keep VM 100 available on 32 GB Apophis'
fi
if grep -Fq 'mv /etc/pve/nodes/carter/qemu-server/200.conf' "$runbook"; then
  fail 'Carter-loss recovery must not move VM 200 away from its standard Apophis owner'
fi

expected_matcher='id!="qemu/128"'
grep -Fq "$expected_matcher" "$alerts" \
  || fail 'GuestDown must exclude only cold recovery VM 128'
grep -Fq 'Intentional cold recovery guest' "$alerts" \
  || fail 'GuestDown exclusion must explain the VM 128 exception'
grep -Fq 'VM 118 replicates' "$alerts" \
  || fail 'replication monitoring must record VM 118 as Carter-owned'
grep -Fq 'VM 200 replicates' "$alerts" \
  || fail 'replication monitoring must record VM 200 as Apophis-owned'
grep -Fq 'expr: up == 0' "$alerts" \
  || fail 'TargetDown must cover every configured scrape target'
if grep -Fq 'labels: { availability: "optional", guest: "qemu/125" }' "$monitoring_playbook"; then
  fail 'VM 125 must not remain an optional monitoring target after media autostart is restored'
fi
grep -Fq 'targets carter' "$vault_playbook" \
  || fail 'Vaultwarden rebuild instructions must preserve its accepted Carter placement'
grep -Fq 'pvesr 118-0 -> apophis' "$vault_playbook" \
  || fail 'Vaultwarden onboarding must replicate from Carter to Apophis'

for playbook in "${media_playbooks[@]}"; do
  grep -Fq -- '--onboot 1' "$playbook" \
    || fail "$(basename "$playbook") must provision its media guest with autostart enabled"
done

for service in jellyfin qbittorrent sonarr radarr 'seerr (+ prowlarr, byparr, gluetun)'; do
  grep -F "| ${service} |" "$plan" | grep -Fq '**Running, `onboot=1`.**' \
    || fail "$service must be recorded as running with autostart enabled"
done

echo 'PASS: Apophis 32 GB capacity and media-autostart model is documented and alert-safe'
