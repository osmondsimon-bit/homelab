#!/usr/bin/env bash
# Run bounded, read-only checks for recurrence after the 2026-07-23 Apophis ZFS recovery.
set -uo pipefail

readonly RECOVERY_BASELINE="2026-07-23 07:34:23 UTC"
readonly MIN_MEM_AVAILABLE_KIB=3145728
declare -a failures=()

add_failure() {
  failures+=("$1")
}

send_notification() {
  local priority="$1"
  local body="$2"

  curl -fsS --max-time 10 \
    -H "Title: Apophis recovery monitor" \
    -H "Priority: ${priority}" \
    -d "$body" \
    "$NTFY_URL" >/dev/null
}

if [[ -z "${NTFY_URL:-}" ]]; then
  printf 'Apophis recovery monitor: NTFY_URL is unavailable\n' >&2
  exit 2
fi

for required_command in awk curl grep journalctl pvesr smartctl zpool; do
  command -v "$required_command" >/dev/null 2>&1 \
    || add_failure "required command unavailable: ${required_command}"
done

zpool_status=""
if command -v zpool >/dev/null 2>&1; then
  if ! zpool_status="$(zpool status -p rpool 2>/dev/null)"; then
    add_failure "rpool status could not be read"
  else
    rpool_health="$(zpool get -H -o value health rpool 2>/dev/null || true)"
    [[ "$rpool_health" == "ONLINE" ]] || add_failure "rpool health is not ONLINE"

    grep -Fq 'errors: No known data errors' <<<"$zpool_status" \
      || add_failure "ZFS reports known data errors"
    grep -Eq 'scan: scrub repaired 0B .* with 0 errors' <<<"$zpool_status" \
      || add_failure "the clean recovery scrub result is no longer present"

    counter_rows=0
    while read -r _ state read_count write_count cksum_count _; do
      [[ "$state" =~ ^(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL|REMOVED)$ ]] || continue
      [[ "$read_count" =~ ^[0-9]+$ && "$write_count" =~ ^[0-9]+$ && "$cksum_count" =~ ^[0-9]+$ ]] \
        || continue
      counter_rows=$((counter_rows + 1))
      if ((read_count != 0 || write_count != 0 || cksum_count != 0)); then
        add_failure "a pool or device has non-zero ZFS READ/WRITE/CKSUM counters"
      fi
    done <<<"$zpool_status"
    ((counter_rows >= 2)) || add_failure "pool and device ZFS counters could not both be verified"
  fi
fi

smart_output=""
if command -v smartctl >/dev/null 2>&1; then
  if ! smart_output="$(smartctl -H -A /dev/nvme0n1 2>/dev/null)"; then
    add_failure "NVMe SMART data could not be read"
  else
    grep -Fq 'SMART overall-health self-assessment test result: PASSED' <<<"$smart_output" \
      || add_failure "NVMe overall health is not PASSED"

    critical_warning="$(
      awk -F: '/^Critical Warning:/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' <<<"$smart_output"
    )"
    [[ "$critical_warning" == "0x00" ]] || add_failure "NVMe critical warning is non-zero"

    media_errors="$(
      awk -F: '/^Media and Data Integrity Errors:/ {gsub(/[[:space:],]/, "", $2); print $2; exit}' \
        <<<"$smart_output"
    )"
    [[ "$media_errors" == "0" ]] || add_failure "NVMe media/data-integrity errors are non-zero"
  fi
fi

kernel_log=""
if command -v journalctl >/dev/null 2>&1; then
  if ! kernel_log="$(journalctl -k --since "$RECOVERY_BASELINE" --no-pager 2>/dev/null)"; then
    add_failure "post-recovery kernel log could not be read"
  elif grep -Eqi \
    'checksum|corrupt|I/O error|hardware error|machine check|mce:|edac|aer:.*(error|fault)|pcie.*(error|fault)|nvme.*(reset|timeout|abort|error|fail)|zfs.*(error|fault|checksum|corrupt)' \
    <<<"$kernel_log"; then
    add_failure "kernel log contains possible checksum, memory, PCIe, NVMe, or ZFS recurrence evidence"
  fi
fi

if command -v pvesr >/dev/null 2>&1; then
  if ! replication_status="$(pvesr status 2>/dev/null)"; then
    add_failure "replication status could not be read"
  else
    for job in 118-0 200-0; do
      job_line="$(awk -v job="$job" '$1 == job {print; exit}' <<<"$replication_status")"
      if [[ -z "$job_line" ]]; then
        add_failure "replication job ${job} is missing"
        continue
      fi

      read -r -a job_fields <<<"$job_line"
      job_field_count="${#job_fields[@]}"
      if ((job_field_count < 4)); then
        add_failure "replication job ${job} status is incomplete"
        continue
      fi

      job_enabled="${job_fields[1]}"
      job_fail_count="${job_fields[job_field_count - 2]}"
      job_state="${job_fields[job_field_count - 1]}"
      if [[ "$job_enabled" != "Yes" || "$job_fail_count" != "0" || "$job_state" != "OK" ]]; then
        add_failure "replication job ${job} is not enabled with FailCount 0 and State OK"
      fi
    done
  fi
fi

mem_available_kib="$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo)"
if [[ ! "$mem_available_kib" =~ ^[0-9]+$ ]]; then
  add_failure "MemAvailable could not be read"
  mem_available_gib="unknown"
else
  mem_available_gib="$(awk -v kib="$mem_available_kib" 'BEGIN {printf "%.1f", kib / 1048576}')"
  ((mem_available_kib >= MIN_MEM_AVAILABLE_KIB)) \
    || add_failure "MemAvailable is below the 3 GiB Apophis guardrail"
fi

if ((${#failures[@]} > 0)); then
  failure_summary="${failures[0]}"
  for ((index = 1; index < ${#failures[@]}; index++)); do
    failure_summary+="; ${failures[index]}"
  done
  message="FAILED: ${failure_summary}. Stop media workloads and inspect before making changes."
  if ! send_notification high "$message"; then
    printf 'Apophis recovery monitor: failure notification could not be delivered\n' >&2
    exit 2
  fi
  printf '%s\n' "$message" >&2
  exit 1
fi

message="PASS: rpool ONLINE with zero counters and no known data errors; NVMe health clean; replication healthy; no recurrence events; MemAvailable ${mem_available_gib} GiB."
if ! send_notification default "$message"; then
  printf 'Apophis recovery monitor: success notification could not be delivered\n' >&2
  exit 2
fi
printf '%s\n' "$message"
