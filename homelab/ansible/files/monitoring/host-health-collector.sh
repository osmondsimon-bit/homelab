#!/usr/bin/env bash
# Emit read-only ZFS, SMART/NVMe, and kernel hardware-failure metrics for PVE hosts.
set -euo pipefail

NODE_NAME="${NODE_NAME:-$(hostname -s)}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
ZPOOL_CMD="${ZPOOL_CMD:-/usr/sbin/zpool}"
SMARTCTL_CMD="${SMARTCTL_CMD:-/usr/sbin/smartctl}"
JOURNALCTL_CMD="${JOURNALCTL_CMD:-/usr/bin/journalctl}"
DATE_CMD="${DATE_CMD:-/usr/bin/date}"

out="${TEXTFILE_DIR}/homelab_host_health.prom"
mkdir -p "$TEXTFILE_DIR"
tmp="$(mktemp "${out}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

escape_label() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g; :a;N;$!ba;s/\n/\\n/g'
}

emit() {
  printf '%s\n' "$1" >> "$tmp"
}

attribute_raw_value() {
  local output="$1"
  local attribute_pattern="$2"
  awk -v pattern="$attribute_pattern" '
    $2 ~ pattern {
      value = $NF
      gsub(/[^0-9].*$/, "", value)
      print value
      exit
    }
  ' <<< "$output"
}

node_label="$(escape_label "$NODE_NAME")"

emit '# HELP homelab_zfs_pool_healthy Whether the ZFS pool state is ONLINE.'
emit '# TYPE homelab_zfs_pool_healthy gauge'
emit '# HELP homelab_zfs_pool_read_errors Aggregate ZFS pool read-error counter.'
emit '# TYPE homelab_zfs_pool_read_errors gauge'
emit '# HELP homelab_zfs_pool_write_errors Aggregate ZFS pool write-error counter.'
emit '# TYPE homelab_zfs_pool_write_errors gauge'
emit '# HELP homelab_zfs_pool_checksum_errors Aggregate ZFS pool checksum-error counter.'
emit '# TYPE homelab_zfs_pool_checksum_errors gauge'
emit '# HELP homelab_zfs_known_data_errors Whether ZFS reports known permanent data errors.'
emit '# TYPE homelab_zfs_known_data_errors gauge'
emit '# HELP homelab_zfs_last_scrub_timestamp_seconds Timestamp of the latest completed scrub.'
emit '# TYPE homelab_zfs_last_scrub_timestamp_seconds gauge'
emit '# HELP homelab_zfs_last_scrub_errors Error count reported by the latest completed scrub.'
emit '# TYPE homelab_zfs_last_scrub_errors gauge'

mapfile -t pools < <("$ZPOOL_CMD" list -H -o name)
((${#pools[@]} > 0))
for pool in "${pools[@]}"; do
  [[ -n "$pool" ]] || continue
  status="$("$ZPOOL_CMD" status -p "$pool")"
  pool_label="$(escape_label "$pool")"
  labels="node=\"${node_label}\",pool=\"${pool_label}\""

  state="$(awk '$1 == "state:" { print $2; exit }' <<< "$status")"
  healthy=0
  [[ "$state" == "ONLINE" ]] && healthy=1

  read_errors=0
  write_errors=0
  checksum_errors=0
  read -r read_errors write_errors checksum_errors < <(
    awk -v pool="$pool" '
      $1 == pool && $2 ~ /^(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL|REMOVED)$/ {
        print $3, $4, $5
        exit
      }
    ' <<< "$status"
  )
  [[ "$read_errors" =~ ^[0-9]+$ ]]
  [[ "$write_errors" =~ ^[0-9]+$ ]]
  [[ "$checksum_errors" =~ ^[0-9]+$ ]]

  known_data_errors=1
  grep -Fq 'errors: No known data errors' <<< "$status" && known_data_errors=0

  scrub_line="$(grep -E '^[[:space:]]*scan: scrub ' <<< "$status" | head -1 || true)"
  scrub_errors=0
  scrub_timestamp=0
  if [[ -n "$scrub_line" ]]; then
    parsed_scrub_errors="$(
      sed -nE 's/.* with ([0-9]+) errors.*/\1/p' <<< "$scrub_line"
    )"
    [[ -n "$parsed_scrub_errors" ]] && scrub_errors="$parsed_scrub_errors"

    scrub_date="${scrub_line##* on }"
    if [[ "$scrub_date" != "$scrub_line" ]]; then
      scrub_timestamp="$("$DATE_CMD" -d "$scrub_date" +%s 2>/dev/null || printf '0')"
    fi
  fi

  emit "homelab_zfs_pool_healthy{${labels}} ${healthy}"
  emit "homelab_zfs_pool_read_errors{${labels}} ${read_errors}"
  emit "homelab_zfs_pool_write_errors{${labels}} ${write_errors}"
  emit "homelab_zfs_pool_checksum_errors{${labels}} ${checksum_errors}"
  emit "homelab_zfs_known_data_errors{${labels}} ${known_data_errors}"
  emit "homelab_zfs_last_scrub_timestamp_seconds{${labels}} ${scrub_timestamp}"
  emit "homelab_zfs_last_scrub_errors{${labels}} ${scrub_errors}"
done

emit '# HELP homelab_smart_device_healthy Whether smartctl reports PASSED device health.'
emit '# TYPE homelab_smart_device_healthy gauge'
emit '# HELP homelab_smart_device_temperature_celsius Current device temperature reported by SMART.'
emit '# TYPE homelab_smart_device_temperature_celsius gauge'
emit '# HELP homelab_smart_reallocated_sectors Reallocated-sector count reported by ATA SMART.'
emit '# TYPE homelab_smart_reallocated_sectors gauge'
emit '# HELP homelab_smart_pending_sectors Current pending-sector count reported by ATA SMART.'
emit '# TYPE homelab_smart_pending_sectors gauge'
emit '# HELP homelab_smart_offline_uncorrectable Offline-uncorrectable count reported by ATA SMART.'
emit '# TYPE homelab_smart_offline_uncorrectable gauge'
emit '# HELP homelab_smart_crc_errors Interface CRC-error count reported by ATA SMART.'
emit '# TYPE homelab_smart_crc_errors gauge'
emit '# HELP homelab_nvme_critical_warning NVMe critical-warning bitmap.'
emit '# TYPE homelab_nvme_critical_warning gauge'
emit '# HELP homelab_nvme_media_errors NVMe media and data-integrity error count.'
emit '# TYPE homelab_nvme_media_errors gauge'
emit '# HELP homelab_nvme_percentage_used NVMe percentage-used value.'
emit '# TYPE homelab_nvme_percentage_used gauge'
emit '# HELP homelab_nvme_unsafe_shutdowns NVMe unsafe-shutdown count.'
emit '# TYPE homelab_nvme_unsafe_shutdowns gauge'

scan_output="$("$SMARTCTL_CMD" --scan-open)"
while read -r device _; do
  [[ -n "${device:-}" ]] || continue
  smart_output="$("$SMARTCTL_CMD" -H -A "$device" 2>/dev/null || true)"
  [[ -n "$smart_output" ]]

  device_label="$(escape_label "$device")"
  labels="node=\"${node_label}\",device=\"${device_label}\""
  smart_healthy=0
  grep -Fq 'SMART overall-health self-assessment test result: PASSED' <<< "$smart_output" \
    && smart_healthy=1
  emit "homelab_smart_device_healthy{${labels}} ${smart_healthy}"

  temperature="$(
    awk -F: '
      /^Temperature:/ {
        value = $2
        gsub(/^[[:space:]]+/, "", value)
        gsub(/[^0-9].*$/, "", value)
        print value
        exit
      }
    ' <<< "$smart_output"
  )"
  if [[ -z "$temperature" ]]; then
    temperature="$(attribute_raw_value "$smart_output" '^(Temperature_Celsius|Airflow_Temperature_Cel)$')"
  fi
  if [[ "$temperature" =~ ^[0-9]+$ ]]; then
    emit "homelab_smart_device_temperature_celsius{${labels}} ${temperature}"
  fi

  reallocated="$(attribute_raw_value "$smart_output" '^Reallocated_Sector_Ct$')"
  pending="$(attribute_raw_value "$smart_output" '^Current_Pending_Sector$')"
  uncorrectable="$(attribute_raw_value "$smart_output" '^Offline_Uncorrectable$')"
  crc_errors="$(attribute_raw_value "$smart_output" '^(UDMA_)?CRC_Error_Count$')"
  [[ "$reallocated" =~ ^[0-9]+$ ]] && emit "homelab_smart_reallocated_sectors{${labels}} ${reallocated}"
  [[ "$pending" =~ ^[0-9]+$ ]] && emit "homelab_smart_pending_sectors{${labels}} ${pending}"
  [[ "$uncorrectable" =~ ^[0-9]+$ ]] && emit "homelab_smart_offline_uncorrectable{${labels}} ${uncorrectable}"
  [[ "$crc_errors" =~ ^[0-9]+$ ]] && emit "homelab_smart_crc_errors{${labels}} ${crc_errors}"

  critical_warning="$(
    awk -F: '/^Critical Warning:/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' \
      <<< "$smart_output"
  )"
  if [[ "$critical_warning" =~ ^0x[0-9A-Fa-f]+$ ]]; then
    emit "homelab_nvme_critical_warning{${labels}} $((critical_warning))"
  fi

  media_errors="$(
    awk -F: '
      /^Media and Data Integrity Errors:/ {
        gsub(/[[:space:],]/, "", $2)
        print $2
        exit
      }
    ' <<< "$smart_output"
  )"
  [[ "$media_errors" =~ ^[0-9]+$ ]] && emit "homelab_nvme_media_errors{${labels}} ${media_errors}"

  percentage_used="$(
    awk -F: '
      /^Percentage Used:/ {
        gsub(/[%[:space:],]/, "", $2)
        print $2
        exit
      }
    ' <<< "$smart_output"
  )"
  [[ "$percentage_used" =~ ^[0-9]+$ ]] && emit "homelab_nvme_percentage_used{${labels}} ${percentage_used}"

  unsafe_shutdowns="$(
    awk -F: '
      /^Unsafe Shutdowns:/ {
        gsub(/[[:space:],]/, "", $2)
        print $2
        exit
      }
    ' <<< "$smart_output"
  )"
  [[ "$unsafe_shutdowns" =~ ^[0-9]+$ ]] && emit "homelab_nvme_unsafe_shutdowns{${labels}} ${unsafe_shutdowns}"
done <<< "$scan_output"

emit '# HELP homelab_kernel_hardware_error_events Hardware/storage failure events in the current kernel boot.'
emit '# TYPE homelab_kernel_hardware_error_events gauge'
kernel_log="$("$JOURNALCTL_CMD" -k -b --no-pager 2>/dev/null)"
kernel_matches="$(
  grep -Eai \
    'I/O error|buffer I/O|blk_update_request|hardware error|machine check|mce:.*(error|fail)|EDAC.*(uncorrected|corrected error|error count| UE | CE )|AER:.*(error|fault|failed)|PCIe Bus Error|nvme.*(reset|timeout|abort|I/O error|failed)|watchdog: BUG|soft lockup|hard lockup|blocked for more than|out of memory|oom-kill' \
    <<< "$kernel_log" || true
)"
kernel_error_count=0
if [[ -n "$kernel_matches" ]]; then
  kernel_error_count="$(wc -l <<< "$kernel_matches")"
fi
emit "homelab_kernel_hardware_error_events{node=\"${node_label}\"} ${kernel_error_count}"

emit '# HELP homelab_host_health_last_check_timestamp_seconds Timestamp of the latest successful host health collection.'
emit '# TYPE homelab_host_health_last_check_timestamp_seconds gauge'
emit "homelab_host_health_last_check_timestamp_seconds{node=\"${node_label}\"} $("$DATE_CMD" +%s)"

chmod 0644 "$tmp"
mv -f "$tmp" "$out"
trap - EXIT
