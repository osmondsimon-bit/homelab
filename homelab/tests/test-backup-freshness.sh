#!/usr/bin/env bash
# Regression tests for backup freshness discovery and explicit one-off PBS exclusions.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
collector="${repo_root}/homelab/ansible/files/monitoring/backup-freshness.sh"
test_dir="$(mktemp -d)"
ha_share="${test_dir}/ha-share"
pbs_datastore="${test_dir}/pbs-datastore"
textfile_dir="${test_dir}/textfiles"

cleanup() {
  rm -rf "$test_dir"
}
trap cleanup EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

mkdir -p \
  "$ha_share" \
  "$textfile_dir" \
  "${pbs_datastore}/ct/124/2026-09-10T03:19:08Z" \
  "${pbs_datastore}/vm/100/2026-09-13T02:30:00Z"
touch -d '2026-08-06 04:55:57 UTC' \
  "${ha_share}/Automatic_backup_2026.7.4_2026-08-06_04.55_57001532.tar"
touch -d '2026-08-09 05:29:48 UTC' \
  "${ha_share}/automatic_backup_2026_8_0_2026-08-09_05.29_48001886.tar"

PBS_DATASTORE="$pbs_datastore" \
HA_SHARE="$ha_share" \
TEXTFILE_DIR="$textfile_dir" \
BACKUP_STALE_MAX_AGE=129600 \
PBS_IGNORE_GROUPS='ct/124' \
  bash "$collector"

metrics="${textfile_dir}/homelab_backups.prom"
expected_epoch="$(date -u -d '2026-08-09 05:29:48 UTC' +%s)"

grep -Fq "homelab_backup_last_success_timestamp_seconds{type=\"ha\",group=\"home-assistant\"} ${expected_epoch}" "$metrics" \
  || fail 'the newest lowercase Home Assistant backup must set the HA freshness timestamp'
grep -Fq 'homelab_backup_count{type="ha",group="home-assistant"} 2' "$metrics" \
  || fail 'both legacy and lowercase Home Assistant backup filenames must be counted'
grep -Fq 'homelab_backup_count{type="pbs",group="vm/100"} 1' "$metrics" \
  || fail 'recurring PBS groups must still be emitted'
if grep -Fq 'group="ct/124"' "$metrics"; then
  fail 'explicitly ignored one-off PBS groups must not be emitted'
fi

printf 'PASS: backup freshness recognizes HA filenames and excludes one-off PBS groups\n'
