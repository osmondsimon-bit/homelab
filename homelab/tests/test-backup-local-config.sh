#!/usr/bin/env bash
# Regression test for token-free GitHub authentication in the local-config backup workflow.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backup_script="${repo_root}/homelab/scripts/backup-local-config.sh"

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

printf 'PASS: local-config backup uses SSH authentication\n'
