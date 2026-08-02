#!/usr/bin/env bash
# Regression contract for failure-only qBittorrent service monitoring and alerting.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
monitoring_playbook="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
monitoring_doc="${repo_root}/homelab/docs/components/monitoring.md"
qbittorrent_doc="${repo_root}/homelab/docs/components/qbittorrent.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

require_text() {
  local file="$1" text="$2" message="$3"
  grep -Fq -- "$text" "$file" || fail "$message"
}

require_text "$monitoring_playbook" 'http_2xx:' \
  'blackbox exporter must provide an HTTP success module'
require_text "$monitoring_playbook" 'job_name: blackbox-qbittorrent' \
  'Prometheus must scrape a dedicated qBittorrent blackbox job'
require_text "$monitoring_playbook" 'params: { module: ["http_2xx"] }' \
  'qBittorrent monitoring must validate an HTTP response rather than only an open socket'
require_text "$monitoring_playbook" 'http://{{ qbittorrent_ip | regex_replace('\''/.*$'\'', '\'''\'') }}:{{ qbittorrent_webui_port }}/' \
  'the probe target must use the inventory-managed qBittorrent Web UI address'
require_text "$monitoring_playbook" 'prometheus-blackbox-exporter --config.file=/etc/prometheus/blackbox.yml --config.check' \
  'blackbox configuration must be validated before service restart'

alert_block=$(awk '
  /- alert: QbittorrentUnavailable/ { found = 1 }
  found { print }
  found && /description:/ { exit }
' "$alerts")
[[ -n "$alert_block" ]] || fail 'QbittorrentUnavailable alert is missing'
grep -Fq 'probe_success{job="blackbox-qbittorrent"} == 0' <<<"$alert_block" \
  || fail 'qBittorrent alert must use blackbox probe failure'
grep -Fq 'for: 5m' <<<"$alert_block" \
  || fail 'qBittorrent alert must tolerate one automatic recovery cycle'
grep -Fq 'severity: warning' <<<"$alert_block" \
  || fail 'qBittorrent unavailability should be a warning, not a host-critical alert'

require_text "$monitoring_doc" 'QbittorrentUnavailable' \
  'monitoring documentation must describe the new alert'
require_text "$qbittorrent_doc" 'Alertmanager' \
  'qBittorrent operations must identify the external notification path'

printf 'PASS: qBittorrent failure-only monitoring is codified\n'
