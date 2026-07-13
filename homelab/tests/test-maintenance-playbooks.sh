#!/usr/bin/env bash
# Regression tests for synchronous maintenance-collector refreshes in Ansible playbooks.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
install_tasks="${repo_root}/homelab/ansible/playbooks/tasks/install-maintenance-collector.yml"
update_playbook="${repo_root}/homelab/ansible/playbooks/update-pve-host.yml"
maintenance_playbook="${repo_root}/homelab/ansible/playbooks/provision-maintenance-monitoring.yml"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_synchronous_start() {
  local file="$1" task_name="$2" block
  block="$(awk -v task_name="$task_name" '
    $0 == "- name: " task_name || $0 == "    - name: " task_name { capture = 1 }
    capture && seen && $0 ~ /^[[:space:]]*- name:/ { exit }
    capture { print; seen = 1 }
  ' "$file")"

  grep -Fq 'ansible.builtin.command: systemctl start homelab-maintenance.service' <<< "$block" \
    || fail "${task_name} must wait for the oneshot collector to finish"
}

assert_synchronous_start "$install_tasks" 'Run the maintenance collector now'
assert_synchronous_start "$update_playbook" 'Refresh dashboard maintenance state immediately'

grep -Fq 'Carter GUI/TOTP login will fail while /etc/pve is read-only.' "$update_playbook" \
  || fail 'the apophis update path must warn that Carter TOTP depends on quorum'

grep -Fq "ssh root@carter 'pvecm expected 1'" "$update_playbook" \
  || fail 'the apophis update path must print the Carter SSH quorum-recovery command'

grep -Fq 'only AFTER confirming apophis is actually down' "$update_playbook" \
  || fail 'the quorum-recovery command must include its split-brain safety condition'

grep -Fq 'inventory_hostname == "apophis"' "$update_playbook" \
  || fail 'the Carter quorum warning must be scoped to apophis'

grep -Fq 'ansible-playbook playbooks/provision-maintenance-monitoring.yml --ask-become-pass' \
  "$maintenance_playbook" \
  || fail 'the canonical deployment command must request the local sudo password'

grep -Fq "OnCalendar=*-*~1 12:00 {{ patching_timezone | default('Etc/UTC') }}" \
  "$maintenance_playbook" \
  || fail 'the reminder must run at noon on the last day of each month in the configured timezone'

grep -Fq 'Persistent=true' "$maintenance_playbook" \
  || fail 'the monthly reminder must catch up after mgmt-vm downtime'

grep -Fq 'when: inventory_hostname == "mgmt-vm-maintenance"' "$maintenance_playbook" \
  || fail 'the monthly reminder must be installed only on mgmt-vm'

grep -Fq 'Review Glance Maintenance State and Renovate PRs.' "$maintenance_playbook" \
  || fail 'the reminder must direct the operator to both maintenance queues'

if grep -Eq 'ExecStart=.*(apt|reboot|shutdown)' "$maintenance_playbook"; then
  fail 'the monthly timer must remind only; it must not patch or reboot'
fi

systemd-analyze calendar '*-*~1 12:00 Etc/UTC' >/dev/null \
  || fail 'systemd must accept the last-day-of-month calendar expression'

printf 'PASS: maintenance playbook regression tests\n'
