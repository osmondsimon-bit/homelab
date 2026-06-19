#!/usr/bin/env bash
# Backup-freshness textfile collector for the homelab backup hub (oneill) — ADR-016/017.
# Scans the PBS datastore + the HA native-backup share on disk and writes a node_exporter
# textfile (.prom) so Prometheus surfaces "when did each backup last succeed / how stale".
# Run by a systemd timer (provision-backup-monitoring.yml). Pure filesystem reads — no
# PBS auth needed. Emits, per backup group:
#   homelab_backup_last_success_timestamp_seconds  (epoch of newest snapshot/file)
#   homelab_backup_count                           (snapshots/files retained)
#   homelab_backup_max_age_seconds                 (staleness budget; powers BackupStale)
# Anything missing simply isn't emitted -> BackupAbsent catches it.
set -euo pipefail

PBS_DATASTORE="${PBS_DATASTORE:-/rpool/data/pbs-datastore}"
HA_SHARE="${HA_SHARE:-/rpool/data/ha-backup-share}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}"
MAX_AGE="${BACKUP_STALE_MAX_AGE:-129600}"   # 36h default

out="${TEXTFILE_DIR}/homelab_backups.prom"
tmp="$(mktemp "${out}.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

emit() { printf '%s\n' "$1" >> "$tmp"; }

emit '# HELP homelab_backup_last_success_timestamp_seconds Epoch of the most recent backup for a group.'
emit '# TYPE homelab_backup_last_success_timestamp_seconds gauge'
emit '# HELP homelab_backup_count Number of retained backups for a group.'
emit '# TYPE homelab_backup_count gauge'
emit '# HELP homelab_backup_max_age_seconds Staleness budget for a group (alert if exceeded).'
emit '# TYPE homelab_backup_max_age_seconds gauge'

emit_group() {  # type group newest_epoch count
  local type="$1" group="$2" epoch="$3" count="$4"
  emit "homelab_backup_last_success_timestamp_seconds{type=\"${type}\",group=\"${group}\"} ${epoch}"
  emit "homelab_backup_count{type=\"${type}\",group=\"${group}\"} ${count}"
  emit "homelab_backup_max_age_seconds{type=\"${type}\",group=\"${group}\"} ${MAX_AGE}"
}

# --- PBS: <datastore>/{vm,ct}/<id>/<ISO8601>Z/ ; newest child dir = last backup ---
if [[ -d "$PBS_DATASTORE" ]]; then
  for kind in vm ct; do
    [[ -d "${PBS_DATASTORE}/${kind}" ]] || continue
    for grpdir in "${PBS_DATASTORE}/${kind}"/*/; do
      [[ -d "$grpdir" ]] || continue
      id="$(basename "$grpdir")"
      newest=""; count=0
      for snap in "$grpdir"*/; do
        [[ -d "$snap" ]] || continue
        count=$((count + 1))
        name="$(basename "$snap")"                       # e.g. 2026-06-18T16:30:06Z
        ep="$(date -u -d "$name" +%s 2>/dev/null || stat -c %Y "$snap")"
        [[ -z "$newest" || "$ep" -gt "$newest" ]] && newest="$ep"
      done
      [[ -n "$newest" ]] && emit_group "pbs" "${kind}/${id}" "$newest" "$count"
    done
  done
fi

# --- HA native partial backups: newest Automatic_backup_*.tar mtime ---
if [[ -d "$HA_SHARE" ]]; then
  newest=""; count=0
  shopt -s nullglob
  for f in "$HA_SHARE"/Automatic_backup_*.tar; do
    count=$((count + 1))
    ep="$(stat -c %Y "$f")"
    [[ -z "$newest" || "$ep" -gt "$newest" ]] && newest="$ep"
  done
  shopt -u nullglob
  [[ -n "$newest" ]] && emit_group "ha" "home-assistant" "$newest" "$count"
fi

chmod 0644 "$tmp"
mv -f "$tmp" "$out"
trap - EXIT
