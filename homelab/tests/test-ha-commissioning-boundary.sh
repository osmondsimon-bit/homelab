#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
runbook="$repo_root/homelab/docs/operations/runbooks.md"
adr="$repo_root/homelab/decisions/027-home-assistant-configuration-and-mcp-boundary.md"
plan="$repo_root/homelab/PLAN.md"

fail() {
  echo "HA commissioning boundary test failed: $*" >&2
  exit 1
}

grep -Fq 'Test→External = Block and Test→all internal = Block' "$runbook" \
  || fail "future restore must default-deny internal and external egress"
grep -Fq 'prove no USB, serial,' "$runbook" \
  || fail "recovery replica must prohibit hardware passthrough"
grep -Fq 'Never retain this VM as the HA' "$runbook" \
  || fail "recovery replica must not become the development baseline"
grep -Fq 'evidence, not standing placement' "$runbook" \
  || fail "historical host placement must not become ongoing approval"
grep -Fq 'pristine canary guest' "$runbook" \
  || fail "pre-restore network denial needs an executable canary proof"
grep -Fq 'Before uploading a backup, actively repeat the deny tests from this exact recovery VM' "$runbook" \
  || fail "the actual recovery VM must prove isolation before backup upload"
grep -Fq 'guest identity, DHCP assignment or a stale exception can differ' "$runbook" \
  || fail "recovery isolation must account for guest-specific policy drift"
grep -Fq 'verify its published SHA-256' "$runbook" \
  || fail "HAOS restore artifact must be version and digest pinned"
grep -Fq 'Do not expose it through an ad-hoc unauthenticated HTTP server' "$runbook" \
  || fail "backup staging must not use a broad unauthenticated listener"
grep -Fq 'fresh Synthetic HAOS VM' "$adr" \
  || fail "ADR must distinguish the synthetic HAOS environment"
grep -Fq 'recovery VM is externally isolated before' "$adr" \
  || fail "ADR must require pre-restore isolation"
grep -Fq 'Test/recovery VM placement is not yet approved' "$plan" \
  || fail "PLAN must not imply guest placement approval"

restore_section="$(sed -n '/\*\*HA native partial restore/,/^| Date |/p' "$runbook")"
if grep -Fq 'host_internet/supervisor_internet: true' <<<"$restore_section"; then
  fail "current recovery procedure must not require broad internet egress"
fi
if grep -Eq 'qm (create|destroy) 299|--bind 0\.0\.0\.0' <<<"$restore_section"; then
  fail "current procedure must not reuse the historical VMID or broad HTTP listener"
fi

echo "HA commissioning boundary contract passed"
