#!/usr/bin/env bash
# Regression test that keeps Ubuntu VM node-exporter targets out of the Proxmox Hosts widget.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
template="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

grep -Fq "set glance_host_instances = glance_hosts | map(attribute='node_exporter_instance') | map('regex_escape') | join('|')" \
  "$template" \
  || fail 'the template must derive an escaped Prometheus instance filter from glance_hosts'

for query in \
  'instance:node_cpu_util:percent{instance=~`<< glance_host_instances >>`}' \
  'max_over_time(instance:node_cpu_util:percent{instance=~`<< glance_host_instances >>`}[24h:5m])' \
  'instance:node_mem_util:percent{instance=~`<< glance_host_instances >>`}' \
  'max_over_time(instance:node_mem_util:percent{instance=~`<< glance_host_instances >>`}[24h:5m])'
do
  grep -Fq "query: ${query}" "$template" \
    || fail "missing filtered Proxmox host query: ${query}"
done

printf 'PASS: Glance Proxmox Hosts queries exclude non-host node targets\n'
