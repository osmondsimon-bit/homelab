#!/usr/bin/env bash
# Regression contract for the private Carter-hosted Minecraft Bedrock service.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-minecraft-bedrock.yml"
stage_playbook="${repo_root}/homelab/ansible/playbooks/stage-minecraft-bedrock.yml"
example_vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
acl_reference="${repo_root}/homelab/ansible/files/tailscale-acl.hujson"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
health_script="${repo_root}/homelab/ansible/files/minecraft/minecraft-health.py"
service_unit="${repo_root}/homelab/ansible/files/minecraft/minecraft-bedrock.service"
component_doc="${repo_root}/homelab/docs/components/minecraft-bedrock.md"
adr="${repo_root}/homelab/decisions/027-minecraft-bedrock-server.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_text() {
  local file="$1" text="$2" message="$3"
  grep -Fq -- "$text" "$file" || fail "$message"
}

for file in "$playbook" "$stage_playbook" "$health_script" "$service_unit" "$component_doc" "$adr"; do
  [[ -f "$file" ]] || fail "required Minecraft artifact is missing: ${file#"$repo_root"/}"
done

require_text "$example_vars" 'minecraft_ctid: 129' 'Minecraft must use the preflighted free CTID 129'
require_text "$example_vars" 'minecraft_ram_mb: 4096' 'Minecraft must start at the official 4 GiB baseline'
require_text "$example_vars" 'minecraft_cores: 2' 'Minecraft must start with two Carter cores'
require_text "$example_vars" 'minecraft_disk_gb: 32' 'Minecraft must have room for the world and upgrades'
require_text "$example_vars" 'minecraft_bds_version: "1.26.44.3"' 'BDS must use the resolved stable version'
require_text "$example_vars" 'minecraft_bds_sha256: "a6d85efb2d72588b725afc12588bb1aab57547252ff1f84e7f9c3646816438c1"' \
  'BDS must verify the official artifact checksum'
require_text "$example_vars" 'minecraft_port: 19132' 'Bedrock IPv4 must use the LAN-discovery default port'

require_text "$playbook" 'hosts: carter' 'the Minecraft LXC must be Carter-only'
require_text "$stage_playbook" 'ip=dhcp,firewall=1' 'staging must generate a MAC without using a fixed address'
require_text "$stage_playbook" '--onboot 0' 'the allocation must remain stopped until its reservation exists'
require_text "$stage_playbook" "'status: stopped'" 'staging must prove the guest was not booted'
if grep -Fq 'pct start' "$stage_playbook"; then
  fail 'the MAC-allocation staging play must never boot CT 129'
fi
require_text "$playbook" 'ubuntu-24.04-standard_24.04-2_amd64.tar.zst' 'the guest must use supported Ubuntu 24.04'
require_text "$playbook" 'Pin the reserved MAC and static Home-LAN address before first boot' \
  'production provisioning must replace staging DHCP with the reservation before boot'
require_text "$playbook" '--unprivileged 1' 'the Minecraft LXC must be unprivileged'
require_text "$playbook" 'firewall=1' 'the Proxmox NIC firewall flag must be enabled'
require_text "$playbook" 'online-mode=true' 'Xbox authentication must remain enabled'
require_text "$playbook" 'allow-list=true' 'the Bedrock allow list must be enabled explicitly'
require_text "$playbook" 'default-player-permission-level=member' 'ordinary players must not be operators'
require_text "$playbook" 'allow-cheats=false' 'cheats must be disabled by default'
require_text "$playbook" 'enable-lan-visibility=true' 'Switch LAN discovery must remain enabled'
require_text "$playbook" 'ip saddr {{ lan_cidr }} udp dport {{ minecraft_port }} accept' \
  'the guest firewall must allow Bedrock only from the Home LAN/subnet-router SNAT range'
require_text "$playbook" 'policy drop' 'the guest inbound firewall must default deny'
require_text "$service_unit" 'User=minecraft' 'BDS must run under a dedicated service account'
require_text "$service_unit" 'NoNewPrivileges=true' 'the systemd service must prohibit privilege gain'
require_text "$service_unit" 'ProtectSystem=strict' 'the BDS filesystem view must default read-only'
require_text "$playbook" 'ldd /opt/minecraft/current/bedrock_server' 'the native release must verify runtime libraries before start'
require_text "$playbook" 'minecraft-console allowlist add' 'provisioning must manage the allow list through the server console'
require_text "$playbook" 'minecraft-console op' 'only declared parent accounts may become operators'
[[ "$(grep -A9 -F 'Add the declared Xbox gamertags' "$playbook" | grep -Fc 'no_log: true')" -eq 1 ]] \
  || fail 'allowlist task output must hide private gamertags'
[[ "$(grep -A9 -F 'Grant operator only' "$playbook" | grep -Fc 'no_log: true')" -eq 1 ]] \
  || fail 'operator task output must hide private gamertags'
require_text "$playbook" 'Read resolved operator permission count without exposing XUIDs' \
  'provisioning must report that Bedrock cannot resolve offline operator XUIDs'
require_text "$playbook" '--mode stop' 'PBS backups must stop the small stateful guest for consistency'
require_text "$playbook" 'keep-daily=7,keep-weekly=4' 'PBS retention must match the local continuity policy'

require_text "$health_script" 'bedrock_server' 'health must check the native BDS process'
require_text "$health_script" '19132' 'health must check the Bedrock UDP listener'
if grep -Fq 'systemctl' "$health_script"; then
  fail 'the DynamicUser health process cannot query systemd private control transport'
fi
require_text "$health_script" 'pgrep' 'health must confirm the minecraft-owned Bedrock process without systemd privileges'
require_text "${repo_root}/homelab/ansible/files/minecraft/minecraft-health.service" 'DynamicUser=true' \
  'the health endpoint must not run as a persistent privileged user'
require_text "$monitoring_playbook" 'job_name: blackbox-minecraft' 'Prometheus must probe Minecraft health'
require_text "$alerts" 'alert: MinecraftUnavailable' 'Alertmanager must cover a live guest with a dead BDS process'
require_text "$acl_reference" 'group:minecraft' 'the versioned tailnet policy must define restricted players'
require_text "$acl_reference" 'udp:19132' 'the tailnet policy must grant only the Bedrock UDP port'

if grep -Fq 'server-port=25565' "$playbook"; then
  fail 'Java Edition TCP port 25565 must not appear in the Bedrock deployment'
fi
if grep -Fq 'online-mode=false' "$playbook"; then
  fail 'offline authentication must never be enabled'
fi

printf 'PASS: Minecraft Bedrock deployment regression contract\n'
