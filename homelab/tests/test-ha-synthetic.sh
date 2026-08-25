#!/usr/bin/env bash
# Contract checks for the isolated, rebuildable Home Assistant synthetic VM.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-ha-synthetic.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"
decision="${repo_root}/homelab/decisions/026-home-assistant-test-environments.md"
plan="${repo_root}/homelab/PLAN.md"
ansible_readme="${repo_root}/homelab/ansible/README.md"
component="${repo_root}/homelab/docs/components/home-assistant-synthetic.md"
monitoring_component="${repo_root}/homelab/docs/components/monitoring.md"
alert_rules="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
glance_template="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"
secondary_playbook="${repo_root}/homelab/ansible/playbooks/provision-secondary-mgmt.yml"
approval_tasks="${repo_root}/homelab/ansible/tasks/validate-ha-synthetic-approval.yml"
config_tasks="${repo_root}/homelab/ansible/tasks/validate-ha-synthetic-config.yml"
approval_script="${repo_root}/homelab/scripts/new-ha-synthetic-approval.sh"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -f "$playbook" ]] || fail 'synthetic Home Assistant playbook is missing'
[[ -x "$approval_script" ]] || fail 'short-lived approval helper is missing or not executable'

grep -Fq 'hosts: carter' "$playbook" \
  || fail 'the synthetic HAOS VM must be placed specifically on Carter'
grep -Fq 'Require the VM already be stopped before start approval' "$playbook" \
  || fail 'staged mode must leave the synthetic VM stopped'
grep -Fq 'ha_synthetic_isolation_approved | bool' "$playbook" \
  && fail 'caller-controlled isolation booleans must not authorize first boot'
grep -Fq 'ha_synthetic_allocation_approval_file' "$playbook" \
  || fail 'staged allocation must require a fresh digest-bound approval artifact'
grep -Fq 'ha_synthetic_start_approval_file' "$playbook" \
  || fail 'first boot must require a separate fresh digest-bound approval artifact'
grep -Fq 'expires_at_utc' "$approval_tasks" \
  || fail 'deployment approval artifacts must expire'
grep -Fq 'image_sha256' "$approval_tasks" \
  || fail 'deployment approval must bind the pinned HAOS asset digest'
grep -Fq 'vlan_tag' "$approval_tasks" \
  || fail 'deployment approval must bind the actual Test VLAN'
grep -Fq 'YOUR_' "$playbook" \
  || fail 'the playbook must fail closed on unresolved public placeholders'
grep -Fq 'pvesh get /cluster/resources --type vm --output-format json' "$playbook" \
  || fail 'VMID ownership must be checked cluster-wide before mutation'
[[ "$(grep -Fc 'pvecm status' "$playbook")" -ge 2 ]] \
  || fail 'cluster quorum must be healthy before Carter allocation'
grep -Fq 'ha_synthetic_carter_pvesr_status' "$playbook" \
  || fail 'Carter-source replication health must be checked on Carter'
grep -Fq 'ha_synthetic_apophis_pvesr_status' "$playbook" \
  || fail 'Apophis-source replication health must be checked independently'
grep -Fq 'delegate_to: apophis' "$playbook" \
  || fail 'VM 200 replication health must be queried on its source node'
grep -Fq 'pvesh get /cluster/replication --output-format json' "$playbook" \
  || fail 'replication ownership and synthetic-VM exclusion must be checked cluster-wide'
if grep -Fq "ha_synthetic_pvesr_status.stdout is regex('(?m)^\\s*200-0" "$playbook"; then
  fail 'Carter-local pvesr output must not be treated as evidence for Apophis-source job 200-0'
fi
[[ "$(grep -Fc 'zpool status -x' "$playbook")" -ge 2 ]] \
  || fail 'Carter ZFS health must be checked before image import'
grep -Fq '/etc/pve/nodes' "$playbook" \
  || fail 'stale cluster config files for VMID 201 must be checked explicitly'
grep -Fq '/etc/pve/firewall/{{ ha_synthetic_vmid }}.fw' "$playbook" \
  || fail 'a stale per-VM firewall file must block VMID reuse'
grep -Fq 'qemu-server/200.conf' "$playbook" \
  || fail 'the known-good production HAOS VM shape must be compared read-only'
grep -Fq 'ha-manager config' "$playbook" \
  || fail 'the synthetic guest must be excluded from Proxmox HA-manager resources'
grep -Fq "ha_synthetic_zfs_names.stdout is not" "$playbook" \
  || fail 'stale VMID 201 ZFS datasets or snapshots must be checked explicitly'
grep -Fq 'MemAvailable' "$playbook" \
  || fail 'the Carter memory guardrail must be checked before creation or start'
grep -Fq 'ha_synthetic_min_host_headroom_mb' "$playbook" \
  || fail 'the Carter headroom threshold must be explicit'
grep -Fq 'ha_synthetic_recovery_vmids' "$playbook" \
  || fail 'recovery guest conflicts must be checked before activation'
[[ "$(grep -Fc 'pvesm status --storage' "$playbook")" -ge 2 ]] \
  || fail 'the target storage must be checked before image import'
grep -Fq 'pvesh get /storage/{{ ha_synthetic_storage }} --output-format json' "$playbook" \
  || fail 'the target storage must use the supported Proxmox storage API'
grep -Fq '0.70' "$playbook" \
  || fail 'allocation must preserve the repository 70% local-zfs warning band'
grep -Fq 'checksum: "sha256:{{ ha_synthetic_image_sha256 }}"' "$playbook" \
  || fail 'the HAOS download must use the pinned official SHA-256'
grep -Fq 'qemu-img check' "$playbook" \
  || fail 'the decompressed HAOS image must pass an integrity check'
grep -Fq -- '--force' "$playbook" \
  || fail 'the qcow2 must always be regenerated from the verified compressed asset'
grep -Fq -- '- --machine' "$playbook" \
  || fail 'the synthetic VM must preserve the q35 machine contract'
grep -Fq -- '- --bios' "$playbook" \
  || fail 'the synthetic VM must use OVMF'
grep -Fq -- '- "{{ ha_synthetic_cores | string }}"' "$playbook" \
  || fail 'the synthetic VM CPU allocation must come from the reviewed contract'
grep -Fq -- '- --sockets' "$playbook" \
  || fail 'the synthetic VM must use the reviewed one-socket CPU topology'
grep -Fq -- '- "{{ ha_synthetic_ram_mb | string }}"' "$playbook" \
  || fail 'the synthetic VM RAM allocation must come from the reviewed contract'
grep -Fq -- '- --balloon' "$playbook" \
  || fail 'the reviewed fixed memory allocation must not silently balloon'
grep -Fq -- '- --onboot' "$playbook" \
  || fail 'the synthetic VM must never auto-start with Carter'
grep -Fq 'virtio,bridge={{ ha_synthetic_bridge }},tag={{ ha_synthetic_vlan_tag }},firewall=1' "$playbook" \
  || fail 'the VM NIC must be tagged for Test and retain PVE firewall support'
grep -Fq -- '--sata0' "$playbook" \
  || fail 'HAOS must use the established SATA boot-disk workaround'
grep -Fq 'qm disk resize {{ ha_synthetic_vmid }} sata0' "$playbook" \
  || fail 'the imported HAOS disk must be resized to the reviewed capacity'
grep -Fq 'refreservation' "$playbook" \
  || fail 'the 64 GiB local-zfs disk must be proven thin after import'
grep -Fq 'pvesh get /cluster/backup --output-format json' "$playbook" \
  || fail 'PBS/vzdump job exclusion must be proven after provisioning'
[[ "$(grep -Fc 'pvesr status' "$playbook")" -ge 3 ]] \
  || fail 'replication exclusion must be proven after provisioning'
grep -Fq 'ha_synthetic_created_this_run | bool' "$playbook" \
  || fail 'failure cleanup must be limited to a VM created by the current run'
grep -Fq 'ha_synthetic_cleanup_identity' "$playbook" \
  || fail 'failure cleanup must re-check the exact guest identity before destruction'
grep -Fq 'ha_synthetic_cleanup_identity_json.name == ha_synthetic_hostname' "$playbook" \
  || fail 'destructive cleanup must require exact parsed identity rather than substrings'
grep -Fq 'ha_synthetic_config_device_keys' "$config_tasks" \
  || fail 'final authority validation must reject extra device keys'
grep -Fq 'ha_synthetic_config_json.args is not defined' "$config_tasks" \
  || fail 'the final guest must reject arbitrary QEMU argument passthrough'
grep -Fq 'Stop the synthetic VM if the post-start guardrail fails' "$playbook" \
  || fail 'an attended start must roll back to stopped when Carter headroom is unsafe'

grep -Fq 'ha_synthetic_vmid: 201' "$example_vars" \
  || fail 'the example inventory must reserve reviewed VMID 201'
grep -Fq 'ha_synthetic_hostname: ha-synthetic' "$example_vars" \
  || fail 'the example inventory must carry the synthetic guest identity'
grep -Fq 'ha_synthetic_cores: 2' "$example_vars" \
  || fail 'the example inventory must carry the reviewed CPU allocation'
grep -Fq 'ha_synthetic_ram_mb: 8192' "$example_vars" \
  || fail 'the example inventory must carry the reviewed RAM allocation'
grep -Fq 'ha_synthetic_disk_gb: 64' "$example_vars" \
  || fail 'the example inventory must carry the reviewed thin disk size'
grep -Fq 'ha_synthetic_storage: local-zfs' "$example_vars" \
  || fail 'the example inventory must place the disk on Carter local-zfs'
grep -Fq 'ha_synthetic_vlan_tag: YOUR_TEST_VLAN_TAG' "$example_vars" \
  || fail 'the public inventory must not disclose the real Test VLAN tag'
grep -Fq 'ha_synthetic_activation: staged' "$example_vars" \
  || fail 'the public default must build a stopped staged VM'
grep -Fq 'ha_synthetic_allocation_approved: false' "$example_vars" \
  && fail 'persistent booleans must not authorize live VM allocation'
grep -Fq 'ha_synthetic_allocation_approval_file: YOUR_LOCAL_ALLOCATION_APPROVAL_JSON' "$example_vars" \
  || fail 'public inventory must point at a local allocation approval artifact'
grep -Fq 'ha_synthetic_start_approval_file: YOUR_LOCAL_START_APPROVAL_JSON' "$example_vars" \
  || fail 'public inventory must point at a separate local start approval artifact'
grep -Fq 'ha_synthetic_image_version: "18.2"' "$example_vars" \
  || fail 'the HAOS version must be pinned rather than following latest'
grep -Fq '254e53f354df0739e3afc09be5431a07df53f0df6b703885404f665c454f254e' "$example_vars" \
  || fail 'the official HAOS 18.2 OVA qcow2 digest must be pinned'
if grep -Eq 'ha_synthetic_.*(backup|pbs|replication).*: *(true|yes|1)' "$example_vars"; then
  fail 'the rebuildable synthetic VM must not opt into backup or replication'
fi

grep -Fq 'Synthetic Home Assistant environment' "$decision" \
  || fail 'the public architecture must distinguish synthetic testing from recovery restore'
grep -Fq 'never contains a production backup' "$decision" \
  || fail 'the decision must prohibit production restore into the persistent synthetic VM'
grep -Fq 'VM 128' "$decision" \
  || fail 'the Carter recovery precedence must be recorded'
grep -Fq 'VM 200' "$decision" \
  || fail 'the production HA recovery precedence must be recorded'
grep -Fq 'Home Assistant synthetic VM' "$runbook" \
  || fail 'the staged build and first-boot procedure must be documented'
grep -Fq 'Deploy the qemu/201 expected-off rules before allocation' "$runbook" \
  || fail 'expected-off alerting must be deployed before VM 201 is allocated'
grep -Fq 'provision-glance.yml --limit oneill' "$runbook" \
  || fail 'the workload dashboard exclusion must be deployed before VM 201 is allocated'
grep -Fq 'active deny tests' "$runbook" \
  || fail 'first boot must require active isolation evidence from the exact guest'
grep -Fq 'qm shutdown 201' "$runbook" \
  || fail 'the commissioning runbook must return the on-demand guest to stopped state'
grep -Fq 'do not restore a production backup' "$runbook" \
  || fail 'the synthetic commissioning runbook must preserve the no-restore boundary'
grep -Fq 'ha-synthetic (planned)' "$plan" \
  || fail 'PLAN must record the guest as planned rather than falsely live'
grep -Fq '`provision-ha-synthetic.yml`' "$ansible_readme" \
  || fail 'the new playbook must be present in the Ansible catalogue'
grep -Fq 'Reproducible from code' "$component" \
  || fail 'the sanitized component page must record the continuity decision'
grep -Fq 'qemu/201' "$monitoring_component" \
  || fail 'monitoring documentation must treat the planned powered-off guest explicitly'
grep -Fq 'id!="qemu/128",id!="qemu/201"' "$alert_rules" \
  || fail 'GuestDown must exclude both intentional cold/on-demand guests'
grep -Fq 'alert: SyntheticHAUnexpectedlyRunning' "$alert_rules" \
  || fail 'monitoring must detect VM 201 left running beyond its attended window'
[[ "$(grep -Fc 'id!="qemu/128",id!="qemu/201"' "$glance_template")" -ge 3 ]] \
  || fail 'Glance workload queries must omit both intentional cold/on-demand guests'
grep -Fq 'secondary_mgmt_ha_synthetic_matches' "$secondary_playbook" \
  || fail 'VM 128 activation must check that the lower-priority synthetic guest is stopped'
grep -Fq 'ha_synthetic_final_cluster_vm.pool | default' "$playbook" \
  || fail 'backup exclusion must use authoritative cluster pool membership'
grep -Fq 'already be stopped before start approval' "$playbook" \
  || fail 'start approval must not retroactively adopt an already-running VM'
grep -Fq 'Require a separately staged guest for attended start mode' "$playbook" \
  || fail 'allocation and first boot must not occur in one invocation'
grep -Fq 'Revalidate the authority surface immediately before start' "$playbook" \
  || fail 'the exact VM authority surface must be refreshed immediately before start'

approval_test_dir="$(mktemp -d)"
trap 'rm -rf "$approval_test_dir"' EXIT
printf '{"preflight":"test-only"}\n' >"$approval_test_dir/evidence.json"
"$approval_script" allocate 123 "$approval_test_dir/evidence.json" \
  "$approval_test_dir/allocate.json" >/dev/null
python3 - "$approval_test_dir/allocate.json" <<'PY'
import json
import os
import stat
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    approval = json.load(handle)
assert approval["action"] == "allocate"
assert approval["vmid"] == 201
assert approval["vlan_tag"] == 123
assert len(approval["image_sha256"]) == 64
assert len(approval["evidence_sha256"]) == 64
assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
PY
ansible-playbook -i carter, -c local \
  "$repo_root/homelab/tests/fixtures/validate-ha-synthetic-approval.yml" \
  -e "approval_file=$approval_test_dir/allocate.json" >/dev/null
ansible-playbook -i carter, -c local \
  "$repo_root/homelab/tests/fixtures/validate-ha-synthetic-config.yml" >/dev/null
if ansible-playbook -i carter, -c local \
    "$repo_root/homelab/tests/fixtures/validate-ha-synthetic-config.yml" \
    -e inject_extra_nic=true >/dev/null 2>&1; then
  fail 'the exact-authority validator must reject an extra VM network interface'
fi
if "$approval_script" allocate 123 "$approval_test_dir/evidence.json" \
    "$approval_test_dir/allocate.json" >/dev/null 2>&1; then
  fail 'approval helper must refuse to overwrite a reusable approval artifact'
fi

if rg -n '(192\.168\.|10\.[0-9]+\.|172\.(1[6-9]|2[0-9]|3[01])\.)' \
    "$playbook" "$decision" "$component" >/dev/null; then
  fail 'public synthetic-HA artifacts must not contain private RFC1918 addresses'
fi

printf 'PASS: synthetic Home Assistant VM contract tests\n'
