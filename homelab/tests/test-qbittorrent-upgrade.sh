#!/usr/bin/env bash
# Regression contract for the rollback-protected Debian 13/qBittorrent 5 migration.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
upgrade_playbook="${repo_root}/homelab/ansible/playbooks/upgrade-qbittorrent-debian13.yml"
provision_playbook="${repo_root}/homelab/ansible/playbooks/provision-qbittorrent.yml"
vars="${repo_root}/homelab/ansible/inventory/group_vars/all.yml.example"
component="${repo_root}/homelab/docs/components/qbittorrent.md"
phase="${repo_root}/homelab/docs/phases/6-media.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_text() {
  local file="$1" text="$2" message="$3"
  grep -Fq -- "$text" "$file" || fail "$message"
}

[[ -f "$upgrade_playbook" ]] || fail 'the Debian 13 migration playbook is missing'
require_text "$vars" 'qbittorrent_lxc_template: debian-13-standard_13.6-1_amd64.tar.zst' \
  'future qBittorrent rebuilds must use the pinned Debian 13 template'
require_text "$provision_playbook" 'qbittorrent_lxc_template | default(lxc_template)' \
  'qBittorrent provisioning must consume its Debian 13 template override'
require_text "$provision_playbook" 'Session\Interface=wg0' \
  'new qBittorrent deployments must set the primary WireGuard interface key'
proton_natpmp_gateway='10.2.0.1'  # scan-allow
obsolete_natpmp_gateway='10.0.0.1'  # scan-allow
require_text "$provision_playbook" "GW=${proton_natpmp_gateway}" \
  'NAT-PMP must use Proton current WireGuard gateway'
if grep -Fq -- "GW=${obsolete_natpmp_gateway}" "$provision_playbook"; then
  fail 'the obsolete Proton NAT-PMP gateway must not return'
fi
require_text "$provision_playbook" 'timeout 10 natpmpc' \
  'NAT-PMP calls must not hang indefinitely when the tunnel is down'
require_text "$provision_playbook" 'grep -Fqx "Session\\Port=$port"' \
  'NAT-PMP renewal must detect when qBittorrent is listening on the wrong Proton port'
require_text "$provision_playbook" 'qBittorrent listening port synchronized to $port' \
  'NAT-PMP renewal must synchronize qBittorrent after Proton assigns a new port'
require_text "$provision_playbook" '/usr/local/bin/qbittorrent-vpn-ready.sh' \
  'provisioning must install a real WireGuard handshake gate'
require_text "$provision_playbook" 'wg show wg0 latest-handshakes' \
  'VPN readiness must inspect the remote handshake rather than local interface state'
require_text "$provision_playbook" 'ExecStartPre=/usr/local/bin/qbittorrent-vpn-ready.sh' \
  'qBittorrent must fail closed when the VPN endpoint does not answer after boot'
require_text "$provision_playbook" 'qbittorrent-vpn-health.timer' \
  'provisioning must monitor for a tunnel that dies after qBittorrent starts'
require_text "$upgrade_playbook" 'qbittorrent_upgrade_confirm | bool' \
  'the major distribution upgrade must require explicit confirmation'
require_text "$upgrade_playbook" 'qbittorrent_upgrade_dataset: rpool/data/subvol-121-disk-0' \
  'the migration must identify the qBittorrent rootfs dataset explicitly'
require_text "$upgrade_playbook" 'zfs snapshot {{ qbittorrent_upgrade_dataset }}@{{ qbittorrent_upgrade_snapshot }}' \
  'the migration must snapshot the rootfs directly before changing APT sources'
require_text "$upgrade_playbook" '/etc/pve/lxc/{{ qbittorrent_ctid }}.conf' \
  'the migration must preserve the Proxmox CT configuration outside its rootfs'
require_text "$upgrade_playbook" 'zfs rollback -r {{ qbittorrent_upgrade_dataset }}@{{ qbittorrent_upgrade_snapshot }}' \
  'the migration report must provide the direct ZFS rollback command'
require_text "$upgrade_playbook" 'Suites: trixie trixie-updates' \
  'the migration must configure the Debian 13 package suites'
require_text "$upgrade_playbook" 'Suites: trixie-security' \
  'the migration must retain Debian security updates'
require_text "$upgrade_playbook" 'apt-get -y upgrade' \
  'the migration must perform Debian recommended minimal upgrade first'
require_text "$upgrade_playbook" 'apt-get -y full-upgrade' \
  'the migration must perform the full distribution upgrade'
require_text "$upgrade_playbook" "version('5.0', '>=')" \
  'the migration must reject a qBittorrent version older than 5'
require_text "$upgrade_playbook" 'ip route get 1.1.1.1' \
  'the migration must verify that internet routing still selects wg0'
require_text "$upgrade_playbook" 'systemctl stop natpmp-renew.timer natpmp-renew.service' \
  'the leak test must quiesce the timer that can restart WireGuard'
require_text "$upgrade_playbook" 'systemctl stop qbittorrent-vpn-health.timer qbittorrent-vpn-health.service' \
  'the leak test must quiesce the VPN health monitor before deliberately dropping WireGuard'
require_text "$upgrade_playbook" 'systemctl start qbittorrent-vpn-health.timer' \
  'the leak test must restore VPN health monitoring afterward'
require_text "$upgrade_playbook" 'systemctl stop qbittorrent' \
  'the leak test must stop torrent activity before dropping WireGuard'
require_text "$upgrade_playbook" 'Session\\\\InterfaceName=wg0' \
  'the migration must enforce qBittorrent itself binding torrent traffic to wg0'
require_text "$upgrade_playbook" 'Session\\\\Interface=wg0' \
  'the migration must enforce the primary qBittorrent WireGuard interface key'
require_text "$upgrade_playbook" 'systemctl stop wg-quick@wg0' \
  'the migration must exercise the killswitch with WireGuard down'
require_text "$upgrade_playbook" 'Restart qBittorrent only after the killswitch test passes' \
  'qBittorrent must remain stopped when negative leak validation fails'
require_text "$component" 'Debian 13' \
  'component documentation must record the upgraded operating system'
require_text "$component" 'qBittorrent 5' \
  'component documentation must record the corrected qBittorrent baseline'
require_text "$component" 'qbittorrent-vpn-health.timer' \
  'component documentation must explain automatic fail-closed VPN recovery'
require_text "$component" "PROTON_NATPMP_GATEWAY=${proton_natpmp_gateway}" \
  'component documentation must record the Proton WireGuard NAT-PMP gateway'
require_text "$component" '.qbittorrent-wg0-new.conf' \
  'component documentation must preserve the safe Proton profile rotation workflow'
require_text "$phase" 'qBittorrent | CT 121 (Debian 13 unpriv LXC)' \
  'media-phase documentation must record the Debian 13 qBittorrent rebuild baseline'

printf 'PASS: qBittorrent Debian 13 migration contract\n'
