#!/usr/bin/env bash
# Regression checks for the Carter-hosted cold secondary management VM.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-secondary-mgmt.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
alert_rules="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
glance_template="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -f "$playbook" ]] || fail 'secondary management playbook is missing'

grep -Fq 'hosts: carter' "$playbook" \
  || fail 'the secondary VM must be created specifically on Carter'
grep -Fq 'secondary_mgmt_vmid != 100' "$playbook" \
  || fail 'the playbook must reject the primary management VMID'
grep -Fq -- '--onboot 0' "$playbook" \
  || fail 'the standby must never auto-start with Carter'
grep -Fq -- '--protection 1' "$playbook" \
  || fail 'the completed standby must be protected against accidental removal'
grep -Fq 'zfs set refreservation=none' "$playbook" \
  || fail 'the cold recovery disk must not reserve its entire 64 GB virtual size on Carter'
grep -Fq 'operator-desktop-cloudinit.pub' "$playbook" \
  || fail 'the operator desktop key must be staged for independent login'
grep -Fq 'secondary-mgmt-automation' "$playbook" \
  || fail 'the secondary must generate its own revocable automation key'
grep -Fq 'github-deploy@mgmt-vm2' "$playbook" \
  || fail 'the secondary must generate a distinct repo-scoped GitHub deploy key'
grep -Fq 'git remote set-url --push origin git@github.com:osmondsimon-bit/homelab.git' "$playbook" \
  || fail 'repository fetch must stay credential-free while pushes use the deploy key'
grep -Fq 'ansible.posix.authorized_key' "$playbook" \
  || fail 'the secondary automation key must be deployed idempotently'
grep -Fq 'inventory/hosts.ini' "$playbook" \
  || fail 'the local-only Ansible inventory must be copied to the secondary'
grep -Fq 'inventory/group_vars/all.yml' "$playbook" \
  || fail 'the local-only Ansible variables must be copied to the secondary'
grep -Fq 'files/patching/setup-unattended.sh' "$playbook" \
  || fail 'the cold VM must catch up security updates after a powered-off interval'
grep -Fq 'https://github.com/osmondsimon-bit/homelab.git' "$playbook" \
  || fail 'the secondary must get a credential-free read checkout'
grep -Fq 'cloud-init status --wait --long' "$playbook" \
  || fail 'first boot must inspect cloud-init details, not only its degraded exit code'
grep -Fq "'errors: []' not in secondary_mgmt_cloud_init.stdout" "$playbook" \
  || fail 'a degraded cloud-init result is acceptable only when the real error list is empty'
grep -Fq 'ansible proxmox -m ansible.builtin.ping' "$playbook" \
  || fail 'the secondary must prove it can control every PVE host before shutdown'
grep -Fq 'qm shutdown {{ secondary_mgmt_vmid }}' "$playbook" \
  || fail 'the build must finish by returning the VM to a cold state'

grep -Fq 'secondary_mgmt_vmid: 128' "$example_vars" \
  || fail 'the example inventory must reserve VMID 128'
grep -Fq 'secondary_mgmt_hostname: mgmt-vm2' "$example_vars" \
  || fail 'the example inventory must name the independent secondary'
grep -Fq 'secondary_mgmt_ip: YOUR_SECONDARY_MGMT_IP/24' "$example_vars" \
  || fail 'the public inventory must keep the real secondary address local-only'
grep -Fq 'secondary_mgmt_ram_mb: 8192' "$example_vars" \
  || fail 'the recovery workstation must have enough RAM for management tools'
grep -Fq 'secondary_mgmt_disk_gb: 64' "$example_vars" \
  || fail 'the recovery workstation must retain the established management disk size'

grep -Fq 'Cold secondary management VM' "$runbook" \
  || fail 'the activation and shutdown procedure must be documented'
grep -Fq 'Never run both management VMs from the same working branch' "$runbook" \
  || fail 'the runbook must guard against divergent infrastructure edits'
grep -Fq 'Commissioning status (2026-07-18)' "$runbook" \
  || fail 'the runbook must preserve the final live commissioning state'
grep -Fq 'Settings → Deploy keys' "$runbook" \
  || fail 'the runbook must retain the one-time GitHub deploy-key step'
grep -Fq 'A cold VM cannot start itself' "$runbook" \
  || fail 'the runbook must state the remaining remote bootstrap limitation'

grep -Fq 'id!="qemu/128"' "$alert_rules" \
  || fail 'the intentionally stopped cold VM must be excluded from GuestDown'
grep -Fq 'intentional cold standby' "$alert_rules" \
  || fail 'the GuestDown exclusion must explain why VM 128 is exceptional'

[[ "$(grep -Fc 'id!="qemu/128"' "$glance_template")" -ge 3 ]] \
  || fail 'the intentionally stopped cold VM must be omitted from workload resource queries'

if grep -Eq '192\.168\.[0-9]+\.[0-9]+' "$playbook"; then
  fail 'the tracked playbook must not contain real private addresses'
fi

printf 'PASS: secondary management VM regression tests\n'
