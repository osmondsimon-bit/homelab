#!/usr/bin/env bash
# git-precommit-scan.sh — pre-commit guard for the public homelab repo.
#
# Purpose : Block a commit that would publish a secret or a real network address.
#           Committed files use YOUR_* placeholders only; real IPs/subnets/MACs
#           live only in gitignored config and never leave this machine (ADR-006).
# Assumes : Invoked by the git pre-commit hook (cwd = repo root). Run on mgmt-vm.
# Requires: git; gitleaks (PATH or ~/.local/bin) for the secret scan — optional.
# Exit    : 0 = clean; 1 = something staged that must not be published.
# Escape  : false positive -> append '  # scan-allow' to the line, or use
#           'git commit --no-verify' to bypass all checks.
set -euo pipefail

fail=0

# 1) Secrets — delegate to gitleaks if available.
gitleaks_bin="$(command -v gitleaks || true)"
if [ -z "$gitleaks_bin" ] && [ -x "$HOME/.local/bin/gitleaks" ]; then
  gitleaks_bin="$HOME/.local/bin/gitleaks"
fi
if [ -n "$gitleaks_bin" ]; then
  if ! "$gitleaks_bin" git --staged --redact --no-banner; then
    echo "pre-commit: gitleaks found a staged secret (see above)." >&2
    fail=1
  fi
else
  echo "pre-commit: WARNING - gitleaks not found; secret scan skipped." >&2
fi

# 2) Real network addresses — private IPv4 ranges and MAC addresses.
#    Scan only staged ADDED lines; a line ending in 'scan-allow' is whitelisted.
added="$(git diff --cached --diff-filter=ACM -U0 --no-color \
  | grep -E '^\+[^+]' | sed 's/^\+//' || true)"

priv_ip='(\b10\.([0-9]{1,3}\.){2}[0-9]{1,3}\b|\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b|\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b)'  # scan-allow
mac='\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'  # scan-allow

hits="$(printf '%s\n' "$added" | grep -vE 'scan-allow$' \
  | grep -nE "$priv_ip|$mac" || true)"
if [ -n "$hits" ]; then
  echo "pre-commit: staged change contains a real IP/MAC - ADR-006 says use YOUR_* placeholders:" >&2
  printf '%s\n' "$hits" >&2
  echo "  False positive? Append '  # scan-allow' to the line, or 'git commit --no-verify'." >&2
  fail=1
fi

exit "$fail"
