#!/usr/bin/env bash
# Regression test for security-only unattended upgrades on the normal Ubuntu VMs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
patching_playbook="${repo_root}/homelab/ansible/playbooks/provision-patching.yml"
maintenance_playbook="${repo_root}/homelab/ansible/playbooks/provision-maintenance-monitoring.yml"
setup_script="${repo_root}/homelab/ansible/files/patching/setup-unattended.sh"
collector="${repo_root}/homelab/ansible/files/monitoring/maintenance-collector.sh"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

for target in mgmt-vm vaultwarden jellyseerr actual; do
  grep -Fq "name: ${target}-patching" "$patching_playbook" \
    || fail "provision-patching.yml must register ${target}"
done

grep -Fq 'groups: _ubuntu_patch_targets' "$patching_playbook" \
  || fail 'Ubuntu VMs must be collected in the dedicated patch target group'
grep -Fq 'hosts: _ubuntu_patch_targets' "$patching_playbook" \
  || fail 'the patching play must target the registered Ubuntu VMs'
grep -Fq 'become: true' "$patching_playbook" \
  || fail 'Ubuntu VM patch enrollment requires privilege escalation'
grep -Fq 'ansible_distribution == "Ubuntu"' "$patching_playbook" \
  || fail 'the VM patching play must refuse non-Ubuntu targets'
grep -Fq 'files/patching/setup-unattended.sh' "$patching_playbook" \
  || fail 'Ubuntu VMs must use the shared unattended-upgrade policy script'

grep -Fq 'Unattended-Upgrade::Automatic-Reboot "false";' "$setup_script" \
  || fail 'automatic reboots must remain disabled'
grep -Fq 'OnCalendar=$CAL' "$setup_script" \
  || fail 'the unattended-upgrade timer must remain pinned to local noon'
grep -Fq 'OnFailure=patch-notify.service' "$setup_script" \
  || fail 'unattended-upgrade failures must notify the operator'

if grep -Eq '^[[:space:]]*"\$\{distro_id\}:\$\{distro_codename\}-updates";' "$setup_script"; then
  fail 'the homelab policy must not enable Ubuntu feature/bugfix updates automatically'
fi

grep -Fq 'maintenance_target_kind: ubuntu-vm' "$maintenance_playbook" \
  || fail 'maintenance metrics must identify the auto-security Ubuntu VM policy'
grep -Fq '[[ "$TARGET_KIND" == "ubuntu-vm" ]] && target_policy="auto-security-manual-other"' "$collector" \
  || fail 'Ubuntu VM metrics must advertise auto-security/manual-other intent'

printf 'PASS: Ubuntu VM security-only patching policy regression tests\n'
