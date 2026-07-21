#!/usr/bin/env bash
# Regression test for local-config backup authentication and security classification.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_script="${repo_root}/homelab/scripts/backup-local-config.sh"
backup_readme="${repo_root}/homelab/scripts/README.md"
agent_policy="${repo_root}/AGENTS.md"
claude_policy="${repo_root}/CLAUDE.md"
backup_adr="${repo_root}/homelab/decisions/007-local-config-backup.md"
plan="${repo_root}/homelab/PLAN.md"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

grep -Fq 'PRIVATE_REPO_URL="git@github.com:osmondsimon-bit/homelab-private.git"' \
  "$backup_script" \
  || fail 'the backup script must clone homelab-private over SSH'

if grep -Fq 'https://github.com/osmondsimon-bit/homelab-private.git' "$backup_script"; then
  fail 'the backup script must not depend on an HTTPS personal access token'
fi

grep -Fq 'Authoritative working and deployment tree: `/home/simon`' "$agent_policy" \
  || fail 'AGENTS.md must identify the authoritative working and deployment tree'

grep -Fq '`/home/simon/homelab-private` is a separate private backup repository' "$agent_policy" \
  || fail 'AGENTS.md must identify homelab-private as a separate backup repository'

grep -Fq 'must not be used as a working tree or deployment source' "$agent_policy" \
  || fail 'AGENTS.md must prohibit work and deployment from the private backup snapshot'

for policy_file in "$agent_policy" "$claude_policy" "$backup_adr" "$backup_script" "$backup_readme"; do
  grep -Fiq 'credential-bearing' "$policy_file" \
    || fail "$(basename "$policy_file") must classify the private backup as credential-bearing"
done

grep -Fq 'Resolve private config backup secret handling' "$plan" \
  || fail 'PLAN.md must track resolution of private-backup secret handling'

if grep -Fqi 'Never back up credentials' "$claude_policy" "$backup_adr" "$backup_script" "$backup_readme"; then
  fail 'backup documentation must not claim that credentials are never backed up'
fi

printf 'PASS: local-config backup uses SSH and has consistent security classification\n'
