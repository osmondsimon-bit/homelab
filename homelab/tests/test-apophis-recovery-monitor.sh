#!/usr/bin/env bash
# Regression checks for the temporary read-only Apophis post-recovery monitor.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
playbook="${repo_root}/homelab/ansible/playbooks/provision-apophis-recovery-monitor.yml"
script="${repo_root}/homelab/ansible/files/monitoring/apophis-recovery-monitor.sh"
runbook="${repo_root}/homelab/docs/operations/runbooks.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

[[ -f "$playbook" ]] || fail 'recovery-monitor playbook is missing'
[[ -f "$script" ]] || fail 'recovery-monitor script is missing'

grep -Fq 'hosts: apophis' "$playbook" \
  || fail 'the temporary monitor must target only Apophis'
grep -Fq 'mode: "0600"' "$playbook" \
  || fail 'the ntfy destination must be stored in a root-only environment file'
grep -Fq 'no_log: true' "$playbook" \
  || fail 'the ntfy destination must not appear in Ansible output'
grep -Fq 'OnCalendar=2026-07-24 09:00:00 Australia/Brisbane' "$playbook" \
  || fail 'the monitor must run Friday at 09:00 AEST'
grep -Fq 'OnCalendar=2026-07-25 09:00:00 Australia/Brisbane' "$playbook" \
  || fail 'the monitor must run Saturday at 09:00 AEST'
grep -Fq 'OnCalendar=2026-07-26 09:00:00 Australia/Brisbane' "$playbook" \
  || fail 'the monitor must run Sunday at 09:00 AEST'
grep -Fq 'Persistent=true' "$playbook" \
  || fail 'a missed fixed-date run must catch up when Apophis returns'

grep -Fq 'zpool get -H -o value health rpool' "$script" \
  || fail 'the monitor must check rpool health'
grep -Fq 'READ/WRITE/CKSUM' "$script" \
  || fail 'the monitor must enforce zero ZFS error counters'
grep -Fq 'SMART overall-health self-assessment test result: PASSED' "$script" \
  || fail 'the monitor must check NVMe overall health'
grep -Fq 'Media and Data Integrity Errors:' "$script" \
  || fail 'the monitor must check NVMe media-integrity errors'
grep -Fq "2026-07-23 07:34:23 UTC" "$script" \
  || fail 'kernel recurrence checks must cover the full post-recovery window'
grep -Fq '118-0 200-0' "$script" \
  || fail 'the monitor must check both recovery replication jobs'
grep -Fq '3145728' "$script" \
  || fail 'the monitor must enforce the 3 GiB MemAvailable guardrail'
grep -Fq 'send_notification high' "$script" \
  || fail 'failures must produce a high-priority notification'
grep -Fq 'send_notification default' "$script" \
  || fail 'successful daily checks must produce a confirmation notification'

if grep -Eq 'zpool (clear|scrub)|zfs destroy|pvesr (delete|create)|pvecm expected|qm (start|stop|destroy)|pct (start|stop|destroy)' "$script"; then
  fail 'the recovery monitor must not contain infrastructure-changing commands'
fi

grep -Fq 'Temporary Apophis post-recovery monitor' "$runbook" \
  || fail 'the deployment and interpretation procedure must be documented'

systemd-analyze calendar '2026-07-24 09:00:00 Australia/Brisbane' >/dev/null \
  || fail 'systemd must accept the fixed AEST calendar expression'

printf 'PASS: temporary Apophis recovery monitor is bounded and read-only\n'
