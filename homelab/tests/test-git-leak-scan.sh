#!/usr/bin/env bash
# Regression tests for staged and full-tree public-repository leak scanning.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
scanner="${repo_root}/homelab/scripts/git-precommit-scan.sh"
workflow="${repo_root}/.github/workflows/leak-scan.yml"
private_ip='192.168.44.8' # scan-allow
private_mac='02:42:ac:11:00:02' # scan-allow
tmp_root="$(mktemp -d)"
trap 'rm -rf "$tmp_root"' EXIT

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

new_repo() {
  local name="$1" test_repo
  test_repo="${tmp_root}/${name}"

  mkdir -p "${test_repo}/homelab/scripts" "${test_repo}/bin"
  cp "$scanner" "${test_repo}/homelab/scripts/git-precommit-scan.sh"
  chmod +x "${test_repo}/homelab/scripts/git-precommit-scan.sh"
  printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "$GITLEAKS_LOG"\n' > "${test_repo}/bin/gitleaks"
  chmod +x "${test_repo}/bin/gitleaks"
  git -C "$test_repo" init -q
  git -C "$test_repo" config user.name 'Leak Scan Test'
  git -C "$test_repo" config user.email 'leak-scan@example.invalid'
  printf 'safe\n' > "${test_repo}/safe.txt"
  git -C "$test_repo" add .
  git -C "$test_repo" commit -qm 'Initial test fixture'
  printf '%s\n' "$test_repo"
}

run_scanner() {
  local test_repo="$1"
  shift
  (
    cd "$test_repo"
    PATH="${test_repo}/bin:${PATH}" \
      GITLEAKS_LOG="${test_repo}/gitleaks.log" \
      homelab/scripts/git-precommit-scan.sh "$@"
  )
}

# A leak already in the repository is invisible to the staged-only hook.
test_repo="$(new_repo staged)"
printf '%s\n' "$private_ip" > "${test_repo}/existing.txt"
git -C "$test_repo" add existing.txt
git -C "$test_repo" commit -qm 'Add historical fixture'
printf 'safe staged change\n' >> "${test_repo}/safe.txt"
git -C "$test_repo" add safe.txt
run_scanner "$test_repo" \
  || fail 'default staged mode must ignore unchanged historical lines'

if run_scanner "$test_repo" --full-tree >"${test_repo}/output" 2>&1; then
  fail 'full-tree mode must reject a private IP already present in a tracked file'
fi
grep -Fq 'existing.txt' "${test_repo}/output" \
  || fail 'full-tree IP failure must identify the tracked file'
grep -Fq 'dir --redact --no-banner' "${test_repo}/gitleaks.log" \
  || fail 'full-tree mode must ask Gitleaks to scan a tracked-tree snapshot'

# Full-tree mode detects MAC addresses and respects an explicit line allow marker.
test_repo="$(new_repo mac)"
printf '%s\n' "$private_mac" > "${test_repo}/device.txt"
git -C "$test_repo" add device.txt
git -C "$test_repo" commit -qm 'Add MAC fixture'
if run_scanner "$test_repo" --full-tree >"${test_repo}/output" 2>&1; then
  fail 'full-tree mode must reject a MAC in a tracked file'
fi
grep -Fq 'device.txt' "${test_repo}/output" \
  || fail 'full-tree MAC failure must identify the tracked file'

test_repo="$(new_repo allow)"
printf '%s  # scan-allow\n' "$private_ip" > "${test_repo}/example.txt"
git -C "$test_repo" add example.txt
git -C "$test_repo" commit -qm 'Add explicitly allowed fixture'
run_scanner "$test_repo" --full-tree \
  || fail 'full-tree mode must respect a line ending in scan-allow'

# CI can require Gitleaks instead of silently degrading to the network-only scan.
test_repo="$(new_repo required)"
if (
  cd "$test_repo"
  HOME="${test_repo}/empty-home" PATH='/usr/bin:/bin' \
    homelab/scripts/git-precommit-scan.sh --full-tree --require-gitleaks
) >"${test_repo}/output" 2>&1; then
  fail '--require-gitleaks must fail when Gitleaks is unavailable'
fi
grep -Fq 'gitleaks is required but was not found' "${test_repo}/output" \
  || fail 'missing required Gitleaks must produce an actionable error'

if "$scanner" --not-a-mode >"${tmp_root}/invalid-output" 2>&1; then
  fail 'an unknown scanner option must fail'
fi

# The server-side gate must exercise the strict full-tree path on every entry point.
[ -f "$workflow" ] || fail 'the GitHub Actions leak-scan workflow must exist'
grep -Fq 'push:' "$workflow" || fail 'CI must scan pushes'
grep -Fq 'pull_request:' "$workflow" || fail 'CI must scan pull requests'
grep -Fq 'workflow_dispatch:' "$workflow" || fail 'CI must support manual scans'
grep -Fq 'schedule:' "$workflow" || fail 'CI must schedule a recurring full-tree scan'
grep -Fq 'homelab/scripts/git-precommit-scan.sh --full-tree --require-gitleaks' "$workflow" \
  || fail 'CI must invoke the strict full-tree scanner mode'
grep -Fq 'GITLEAKS_VERSION: 8.30.1' "$workflow" \
  || fail 'CI must pin the tested Gitleaks release'
grep -Fq '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb' "$workflow" \
  || fail 'CI must verify the pinned Linux x64 release checksum'

printf 'PASS: staged and full-tree leak scanning regression tests\n'
