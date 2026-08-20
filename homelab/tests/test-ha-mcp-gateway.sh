#!/usr/bin/env bash
# Regression contract for the design-only, fail-closed HA MCP mediation gateway.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-ha-mcp-gateway.yml"
vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
unit="${repo_root}/homelab/ansible/templates/ha-mcp-gateway/ha-mcp-gateway.service.j2"
config="${repo_root}/homelab/ansible/templates/ha-mcp-gateway/config.yaml.j2"
manifest_schema="${repo_root}/homelab/ansible/files/ha-mcp-gateway/semantic-manifest.schema.json"
approval_schema="${repo_root}/homelab/ansible/files/ha-mcp-gateway/runtime-approval.schema.json"
firewall="${repo_root}/homelab/ansible/templates/ha-mcp-gateway/firewall.nft.j2"
firewall_unit="${repo_root}/homelab/ansible/templates/ha-mcp-gateway/ha-mcp-gateway-firewall.service.j2"
monitoring="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
glance="${repo_root}/homelab/ansible/playbooks/provision-glance.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
component="${repo_root}/homelab/docs/components/ha-mcp-gateway.md"
adr="${repo_root}/homelab/decisions/027-home-assistant-configuration-and-mcp-boundary.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

for file in "$playbook" "$vars" "$unit" "$config" "$manifest_schema" "$approval_schema" "$firewall" "$firewall_unit" \
  "$monitoring" "$glance" "$alerts" "$component" "$adr"; do
  [[ -f "$file" ]] || fail "missing gateway contract file: $file"
done

grep -Fq 'ha_mcp_gateway_mode: disabled' "$vars" \
  || fail 'gateway must be disabled by default'
grep -Fq 'ha_mcp_gateway_control_enabled: false' "$vars" \
  || fail 'mediated control must be independently disabled'
grep -Fq 'ha_mcp_gateway_native_mcp_control_enabled: false' "$vars" \
  || fail 'native MCP control must remain disabled'
grep -Fq 'ha_mcp_gateway_backup_mode: encrypted_pbs_image' "$vars" \
  || fail 'stateful audit history requires encrypted PBS backup'
grep -Fq 'ha_mcp_gateway_test_client_identity:' "$vars" \
  || fail 'attended identity test must name the reviewed certificate identity'
grep -Fq 'ha_mcp_gateway_runtime_approval_file:' "$vars" \
  || fail 'production requires a separate runtime approval artifact'
if grep -Fq 'ha_mcp_gateway_operator_approved:' "$vars"; then
  fail 'a reusable inventory Boolean cannot authorize production'
fi

if grep -Eq 'pct create|qm create' "$playbook"; then
  fail 'design-only gateway playbook must not invent or create a guest'
fi
grep -Fq "'unprivileged: 1' in ha_mcp_gateway_ct_config.stdout_lines" "$playbook" \
  || fail 'playbook must prove the pre-created CT is unprivileged'
grep -Fq "ha_mcp_gateway_host | default('unassigned') != ha_mcp_gateway_pbs_host | default('oneill')" "$playbook" \
  || fail 'gateway placement must avoid the PBS datastore host'
for gate in infrastructure_reviewed security_reviewed network_policy_registered \
  patching_registered monitoring_registered backup_registered backup_freshness_registered \
  prohibited_attempt_monitoring_implemented \
  restore_drill_recorded no_control_recovery_tested kill_switch_tested \
  old_credential_rejection_tested; do
  grep -Fq "ha_mcp_gateway_${gate}" "$playbook" \
    || fail "missing fail-closed ${gate} gate"
done
grep -Fq 'setup-unattended.sh' "$playbook" \
  || fail 'gateway must receive the shared security-only patch policy'
grep -Fq 'nologin system user with no supplementary groups' "$playbook" \
  || fail 'an existing static service account must be revalidated'
grep -Fq "ha_mcp_gateway_primary_group.stdout == 'ha-mcp-gateway'" "$playbook" \
  || fail 'the service account must have its exact dedicated primary group'
grep -Fq "(ha_mcp_gateway_passwd.stdout.split(':'))[2] | int > 0" "$playbook" \
  || fail 'the service account must never be UID 0'
grep -Fq 'systemctl, disable, --now, ha-mcp-gateway.service' "$playbook" \
  || fail 'staged mode must stop and disable the service'
grep -Fq 'not (ha_mcp_gateway_control_enabled | bool)' "$playbook" \
  || fail 'staged mode must reject control-capable configuration'
grep -Fq 'ha_mcp_gateway_source_stats.results[0].stat.checksum == ha_mcp_gateway_artifact_sha256' "$playbook" \
  || fail 'gateway artifact must be SHA-256 pinned'
grep -Fq 'ha_mcp_gateway_source_stats.results[1].stat.checksum == ha_mcp_gateway_semantic_manifest_sha256' "$playbook" \
  || fail 'private semantic manifest must be SHA-256 pinned'
grep -Fq 'semantic-manifest.schema.json' "$playbook" \
  || fail 'private semantic manifest must be machine-validated against the public boundary schema'
python3 - "$manifest_schema" <<'PY'
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

schema = json.loads(Path(sys.argv[1]).read_text())
validator = Draft202012Validator(schema)
base = {
    "schema_version": "1.0.0",
    "status": "approved",
    "control_enabled": False,
    "raw_passthrough_enabled": False,
    "semantic_mirrors": [],
    "intents": [],
}
validator.validate(base)
base["control_enabled"] = True
base["intents"] = [{
    "action": "unlock_front_door",
    "adapter": "access_security",
    "risk_class": "protected",
    "enabled": True,
}]
try:
    validator.validate(base)
except ValidationError:
    pass
else:
    raise SystemExit("protected or unbound intent passed the public semantic-manifest schema")
PY
grep -Fq 'runtime-approval.schema.json' "$playbook" \
  || fail 'runtime approval must be schema-validated'
grep -Fq 'expires_epoch' "$playbook" \
  || fail 'runtime approval must expire'
grep -Fq 'deployment_authority_sha256' "$playbook" \
  || fail 'approval must bind the entire effective placement/network/template authority'
grep -Fq "Target-host authority differs from the exact controller-approved deployment." "$playbook" \
  || fail 'target-host variables must be reasserted against controller preflight'
grep -Fq 'semantic-manifest.json' "$playbook" \
  || fail 'private semantic manifest must be installed explicitly'
grep -Fq 'ansible.builtin.tempfile:' "$playbook" \
  || fail 'sensitive staging must use an unpredictable root-only temporary directory'
grep -Fq 'Stop the gateway before changing any live path' "$playbook" \
  || fail 'a running gateway must be stopped before files are replaced'
grep -Fq 'Refuse a gateway in a transitional service state' "$playbook" \
  || fail 'deployment must not ignore an ambiguous service stop state'
grep -Fq 'Refuse mutation unless the gateway is independently proven inactive' "$playbook" \
  || fail 'deployment must prove the stopped state before replacing files'
grep -Fq 'Preserve the prior deployment in a root-only rollback archive' "$playbook" \
  || fail 'the prior gateway deployment must remain recoverable during mutation'
grep -Fq 'Restore the complete prior deployment after any failed acceptance step' "$playbook" \
  || fail 'every failed post-stop acceptance step must restore the prior gateway deployment'
grep -Fq 'Prove identity is derived from the attended client certificate' "$playbook" \
  || fail 'external identity acceptance must remain inside the deployment transaction'
grep -Fq 'Retain only the immediate prior root-only rollback archive after acceptance' "$playbook" \
  || fail 'secret-bearing rollback archives need bounded retention'
for state_fact in prior_deployment_present rollback_capture_succeeded mutation_started; do
  grep -Fq "ha_mcp_gateway_${state_fact}" "$playbook" \
    || fail "transaction must track explicit ${state_fact} state"
done
[[ "$(grep -Fc 'tar, -tzf, "{{ gateway_rollback_archive }}"' "$playbook")" -eq 2 ]] \
  || fail 'rollback archive integrity must be checked before mutation and extraction'
grep -Fq 'Remove the failed managed tree before extracting the prior deployment' "$playbook" \
  || fail 'rollback must remove newly introduced failed-deployment paths before extraction'
grep -Fq 'Rollback did not restore the prior gateway/firewall enablement state.' "$playbook" \
  || fail 'rollback must verify exact prior systemd enablement'
grep -Fq 'Remove the entire root-only stage from the Proxmox host' "$playbook" \
  || fail 'sensitive staging must have an always-path cleanup'
grep -Fq 'systemctl, restart, ha-mcp-gateway.service' "$playbook" \
  || fail 'production updates must restart onto the reviewed artifact and configuration'
grep -Fq 'systemctl, restart, ha-mcp-gateway-firewall.service' "$playbook" \
  || fail 'firewall convergence must reload changed rules'
grep -Fq 'Prove an anonymous client cannot spoof or read an identity' "$playbook" \
  || fail 'production must negatively test anonymous identity spoofing'
grep -Fq 'Prove identity is derived from the attended client certificate' "$playbook" \
  || fail 'production must test the certificate-derived identity'
grep -Fq 'stdout_lines == [ha_mcp_gateway_test_client_identity]' "$playbook" \
  || fail 'the attended client certificate must have exactly one reviewed SAN identity'
grep -Fq 'Prove the service account cannot reach an unrelated address' "$playbook" \
  || fail 'production staging must negatively test service-user egress'
[[ "$(grep -Fc 'no_log: true' "$playbook")" -ge 4 ]] \
  || fail 'credential staging and health paths must suppress logs'

for setting in User=ha-mcp-gateway Group=ha-mcp-gateway NoNewPrivileges=yes ProtectSystem=strict ProtectHome=yes \
  PrivateDevices=yes RestrictNamespaces=yes MemoryDenyWriteExecute=yes IPAddressDeny=any; do
  grep -Fq "$setting" "$unit" || fail "systemd unit missing ${setting}"
done
if grep -Fq 'DynamicUser=yes' "$unit"; then
  fail 'DynamicUser cannot consume the deliberately group-readable immutable policy files'
fi
grep -Fq 'LoadCredential=ha-token:/etc/ha-mcp-gateway/ha-token' "$unit" \
  || fail 'the HA token must enter the unprivileged process through systemd credentials'
grep -Fq 'LoadCredential=tls-key:/etc/ha-mcp-gateway/server-key.pem' "$unit" \
  || fail 'the TLS private key must enter the unprivileged process through systemd credentials'
grep -Fq 'IPAddressAllow={{ ha_mcp_gateway_ha_address }}' "$unit" \
  || fail 'service process must have an exact HA destination allow'
grep -Fq 'Requires=ha-mcp-gateway-firewall.service' "$unit" \
  || fail 'the service must depend on the port-scoped guest firewall'
grep -Fq 'ip saddr {{ client_cidr }} tcp dport {{ ha_mcp_gateway_port }}' "$firewall" \
  || fail 'guest ingress must be limited by client CIDR and exact gateway port'
grep -Fq 'meta skuid "ha-mcp-gateway" ip daddr {{ ha_mcp_gateway_ha_address }} tcp dport {{ ha_mcp_gateway_ha_port }}' "$firewall" \
  || fail 'service-user egress must be limited to the exact HA IP and port'
grep -Fq 'meta skuid "ha-mcp-gateway" reject' "$firewall" \
  || fail 'all other service-user initiated egress must be rejected'
grep -Fq 'retention_days: 90' "$config" \
  || fail 'structured audit must retain 90 days'
grep -Fq 'client_identity_source: verified_client_certificate_san' "$config" \
  || fail 'client identity must come from the verified mTLS certificate'
grep -Fq 'accept_client_supplied_identity: false' "$config" \
  || fail 'caller-supplied identities must be rejected'
grep -Fq 'unauthenticated_paths: [/healthz]' "$config" \
  || fail 'only the content-free health endpoint may be anonymous'
for forbidden in raw_entity_passthrough raw_service_passthrough rest_passthrough \
  template_passthrough configuration_passthrough; do
  grep -A8 '^authorization:' "$config" | grep -Fq "${forbidden}: false" \
    || fail "${forbidden} must fail closed"
done

grep -Fq 'blackbox-ha-mcp-gateway' "$monitoring" \
  || fail 'production gateway needs an external health probe'
grep -Fq 'http_2xx_ha_mcp_gateway' "$monitoring" \
  || fail 'gateway health probe must use its pinned TLS CA'
grep -Fq 'ca_file: /etc/prometheus/ha-mcp-gateway-server-ca.pem' "$monitoring" \
  || fail 'blackbox exporter must validate the gateway server certificate'
grep -Fq 'update-ca-certificates' "$glance" \
  || fail 'Glance must trust the pinned gateway CA before checking its HTTPS tile'
grep -Fq 'Remove stale HA MCP gateway CA trust while the gateway is disabled' "$glance" \
  || fail 'disabling the gateway must remove its CA from the global Glance trust store'
grep -Fq 'HomeAssistantMcpGatewayUnavailable' "$alerts" \
  || fail 'gateway process health needs a maintenance alert'
grep -Fq 'MCP is unavailable; Home Assistant automation and native controls should continue unchanged.' "$alerts" \
  || fail 'alert must state the isolation contract'

printf 'PASS: HA MCP gateway fail-closed design contract\n'
