#!/usr/bin/env bash
# Regression checks for truthful HAOS memory telemetry and dashboard semantics.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
monitoring="${repo_root}/homelab/ansible/playbooks/provision-monitoring.yml"
recording="${repo_root}/homelab/ansible/files/monitoring/recording-rules.yml"
alerts="${repo_root}/homelab/ansible/files/monitoring/alert-rules.yml"
glance="${repo_root}/homelab/ansible/templates/glance/glance.yml.j2"
docs="${repo_root}/homelab/docs/components/monitoring.md"
deploy="${repo_root}/homelab/ansible/playbooks/deploy-monitoring-rules.yml"

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
require_text() {
  grep -Fq -- "$2" "$1" || fail "$3"
}

require_text "$monitoring" 'sensor\.system_monitor_(memory_free|memory_use|memory_usage|swap_usage|memory_pressure_some_60s_average|memory_pressure_full_60s_average)' \
  'Prometheus must retain only the six approved HA System Monitor entities'
require_text "$recording" 'guest:ha_mem_util:percent' \
  'HAOS true memory utilization must have a stable recording rule'
require_text "$recording" 'entity="sensor.system_monitor_memory_usage"' \
  'the HAOS recording rule must use the System Monitor utilization entity'
require_text "$alerts" 'alert: HomeAssistantMemoryHigh' \
  'sustained true HAOS memory exhaustion must alert'
require_text "$alerts" 'alert: HomeAssistantMemoryPressure' \
  'sustained HAOS PSI must alert'
require_text "$glance" 'guest:ha_mem_util:percent' \
  'Glance must use true HAOS utilization for VM200'
require_text "$glance" 'RAM held' \
  'QEMU allocation/cache accounting must not be labelled as true RAM use'
require_text "$glance" 'HA uses System Monitor; other VM values include reclaimable guest cache.' \
  'the dashboard must disclose mixed guest-memory semantics'
require_text "$docs" 'HAOS memory semantics' \
  'operator interpretation and response must be documented'
require_text "$deploy" 'monitoring_recording_live' \
  'the focused deployment must promote recording rules'
require_text "$deploy" 'monitoring_config_ct_stage' \
  'the focused deployment must validate the scrape allow-list before promotion'

printf 'PASS: HAOS memory pressure is measured and guest RAM semantics are honest\n'
