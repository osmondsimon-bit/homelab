#!/usr/bin/env bash
# Regression checks for the Carter-hosted cold secondary management VM.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-secondary-mgmt.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
decision="${repo_root}/homelab/decisions/000-mgmt-vm.md"
plan="${repo_root}/homelab/PLAN.md"
tech_radar="${repo_root}/homelab/docs/tech-radar.md"
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
grep -Fq 'https://downloads.claude.ai/keys/claude-code.asc' "$playbook" \
  || fail 'Claude Code must use the published Anthropic signing key'
grep -Fq '31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE' "$playbook" \
  || fail 'the Anthropic signing key fingerprint must be verified before use'
grep -Fq 'https://downloads.claude.ai/claude-code/apt/stable' "$playbook" \
  || fail 'Claude Code must use the Anthropic stable apt channel'
grep -Fq 'name: claude-code' "$playbook" \
  || fail 'the recovery workstation must install the standalone Claude Code CLI'
grep -Fq 'npm install --global @openai/codex@latest' "$playbook" \
  || fail 'the recovery workstation must install the official Codex CLI package'
grep -Fq 'NPM_CONFIG_PREFIX: /home/simon/.local/npm' "$playbook" \
  || fail 'Codex must install in the unprivileged user-local npm prefix'
grep -Fq 'claude --version' "$playbook" \
  || fail 'the recovery workstation must validate the Claude Code binary'
grep -Fq 'codex --version' "$playbook" \
  || fail 'the recovery workstation must validate the Codex binary'
grep -Fq 'Agent authentication remains manual on mgmt-vm2' "$playbook" \
  || fail 'the build must preserve manual, independent agent authentication'
if grep -Eq 'src:.*(\.claude|\.codex|auth\.json|credentials\.json)' "$playbook"; then
  fail 'the recovery workstation must never copy agent config or credentials from the primary'
fi
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
grep -Fq '### Use the recovery VM' "$runbook" \
  || fail 'the runbook must explain when and how to use the recovery VM'
grep -Fq 'git status --short --branch' "$runbook" \
  || fail 'the recovery workflow must check repository state before making changes'
grep -Fq 'ansible proxmox -m ping' "$runbook" \
  || fail 'the recovery workflow must verify managed-host access'
grep -Fq 'claude auth login' "$runbook" \
  || fail 'the recovery workflow must document independent Claude authentication'
grep -Fq 'codex login --device-auth' "$runbook" \
  || fail 'the recovery workflow must document headless Codex authentication'
grep -Fq 'Claude Code and Codex extensions in the remote window' "$runbook" \
  || fail 'the recovery workflow must document VS Code remote extension commissioning'

grep -Fq "Anthropic's signed stable apt channel" "$decision" \
  || fail 'the management ADR must record the Claude Code supply channel'
grep -Fq "official npm package" "$decision" \
  || fail 'the management ADR must record the Codex supply channel'
grep -Fq 'AI-ready refresh codified 2026-07-19' "$plan" \
  || fail 'the project plan must record the pending recovery-node refresh'
grep -Fq 'Claude Code + Codex' "$tech_radar" \
  || fail 'the technology radar must record both adopted coding agents'

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
