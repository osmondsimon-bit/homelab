#!/usr/bin/env bash
# git-precommit-scan.sh — staged/full-tree guard for the public homelab repo.
#
# Purpose : Block changes that would publish a secret or a real network address.
#           Committed files use YOUR_* placeholders only; real IPs/subnets/MACs
#           live only in gitignored config and never leave this machine (ADR-006).
# Modes   : --staged (default, pre-commit) or --full-tree (tracked-file audit/CI).
# Assumes : Run inside the repository; invoked by the pre-commit hook on mgmt-vm.
# Requires: git; gitleaks (PATH or ~/.local/bin) for the secret scan — optional.
# Exit    : 0 = clean; 1 = a leak, missing required dependency, or invalid usage.
# Escape  : false positive -> append '  # scan-allow' to the line, or use
#           'git commit --no-verify' to bypass the local hook (CI still scans).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: git-precommit-scan.sh [--staged|--full-tree] [--require-gitleaks]

  --staged            Scan staged secrets and added network-address lines (default).
  --full-tree         Scan all tracked files for secrets and network addresses.
  --require-gitleaks  Fail instead of warning when Gitleaks is unavailable.
EOF
}

mode="staged"
require_gitleaks=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --staged)
      mode="staged"
      ;;
    --full-tree)
      mode="full-tree"
      ;;
    --require-gitleaks)
      require_gitleaks=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "leak-scan: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "leak-scan: run this command inside a Git repository." >&2
  exit 1
}
cd "$repo_root"

fail=0

# 1) Secrets — delegate to gitleaks if available.
gitleaks_bin="$(command -v gitleaks || true)"
if [ -z "$gitleaks_bin" ] && [ -x "$HOME/.local/bin/gitleaks" ]; then
  gitleaks_bin="$HOME/.local/bin/gitleaks"
fi
if [ -n "$gitleaks_bin" ]; then
  if [ "$mode" = "staged" ]; then
    if ! "$gitleaks_bin" git --staged --redact --no-banner; then
      echo "leak-scan: gitleaks found a staged secret (see above)." >&2
      fail=1
    fi
  else
    # Scan an index snapshot so gitignored local credentials never enter the audit.
    tracked_tree="$(mktemp -d)"
    trap 'rm -rf "$tracked_tree"' EXIT
    git checkout-index --all --force --prefix="${tracked_tree}/"
    if ! "$gitleaks_bin" dir --redact --no-banner "$tracked_tree"; then
      echo "leak-scan: gitleaks found a secret in the tracked tree (see above)." >&2
      fail=1
    fi
  fi
elif [ "$require_gitleaks" -eq 1 ]; then
  echo "leak-scan: gitleaks is required but was not found in PATH or ~/.local/bin." >&2
  fail=1
else
  echo "leak-scan: WARNING - gitleaks not found; secret scan skipped." >&2
fi

# 2) Real network addresses — private IPv4 ranges and MAC addresses.
#    A line ending in 'scan-allow' is explicitly whitelisted.
priv_ip='(\b10\.([0-9]{1,3}\.){2}[0-9]{1,3}\b|\b172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3}\b|\b192\.168\.[0-9]{1,3}\.[0-9]{1,3}\b)'  # scan-allow
mac='\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'  # scan-allow

if [ "$mode" = "staged" ]; then
  network_input="$(git diff --cached --diff-filter=ACM -U0 --no-color \
    | grep -E '^\+[^+]' | sed 's/^\+//' || true)"
else
  network_input="$(git grep -nI -E "$priv_ip|$mac" || true)"
fi

hits="$(printf '%s\n' "$network_input" | grep -vE 'scan-allow$' \
  | grep -nE "$priv_ip|$mac" || true)"
if [ -n "$hits" ]; then
  echo "leak-scan: ${mode} content contains a real IP/MAC - ADR-006 says use YOUR_* placeholders:" >&2
  printf '%s\n' "$hits" >&2
  echo "  False positive? Append '  # scan-allow' to the line." >&2
  fail=1
fi

exit "$fail"
