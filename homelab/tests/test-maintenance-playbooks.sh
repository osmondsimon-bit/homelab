#!/usr/bin/env bash
# Regression tests for synchronous maintenance-collector refreshes in Ansible playbooks.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
install_tasks="${repo_root}/homelab/ansible/playbooks/tasks/install-maintenance-collector.yml"
update_playbook="${repo_root}/homelab/ansible/playbooks/update-pve-host.yml"

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

printf 'PASS: maintenance playbook regression tests\n'
