#!/usr/bin/env bash
# Back up local-only homelab config to the private `homelab-private` GitHub repo.
# Run from the mgmt-vm:  bash homelab/scripts/backup-local-config.sh
#
# Why: the public repo intentionally excludes real IPs/config (ADR-006) and the
# local Claude/Codex config. Those live only on this machine — this script gives
# them an off-box, off-site backup alongside the mgmt-vm PBS image (ADR-007).
#
# SECURITY CLASSIFICATION: group_vars/all.yml now contains machine credentials, so
# homelab-private is credential-bearing recovery material in practice. The guard
# below excludes a narrow set of high-risk key/token formats; it is not proof that
# the backup is non-secret. See ADR-007 and the remediation backlog in PLAN.md.
# GitHub uses a dedicated SSH key that stays on the mgmt-vm (and in its PBS image).
#
# Restore: clone homelab-private and copy the files back to the same paths under $HOME.

set -euo pipefail

PRIVATE_REPO_URL="git@github.com:osmondsimon-bit/homelab-private.git"
WORKDIR="$HOME/homelab-private"     # gitignored by the public repo
SRC="$HOME"

# Local-only paths to back up (relative to $HOME). Add new sensitive/local-only
# files only after classifying them under ADR-007. Do not add SSH private keys.
PATHS=(
  "homelab/ansible/inventory/hosts.ini"
  "homelab/ansible/inventory/group_vars/all.yml"
  "homelab/ansible/inventory/host_vars"
  ".claude/agents"
  ".claude/skills"
  ".claude/projects/-home-simon/memory"
  ".codex/AGENTS.md"
  ".codex/config.toml"
)

echo "==> Syncing private backup repo..."
if [[ -d "$WORKDIR/.git" ]]; then
  git -C "$WORKDIR" pull --quiet --ff-only 2>/dev/null || true
else
  git clone --quiet "$PRIVATE_REPO_URL" "$WORKDIR"
fi

echo "==> Copying local-only config in..."
for p in "${PATHS[@]}"; do
  if [[ -e "$SRC/$p" ]]; then
    mkdir -p "$WORKDIR/$(dirname "$p")"
    cp -a "$SRC/$p" "$WORKDIR/$(dirname "$p")/"
    echo "    + $p"
  else
    echo "    (skip, not found) $p"
  fi
done

# Narrow safety net: reject selected high-risk private-key and token formats. This
# does not detect generic API keys or embedded VPN configuration.
if grep -rIlE 'BEGIN (OPENSSH|RSA|EC) PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|tskey-' "$WORKDIR" \
    --exclude-dir=.git 2>/dev/null; then
  echo "ERROR: a credential-like value was found in the backup set above — aborting."
  echo "Remove it from the PATHS list; credentials must not be backed up to a repo."
  exit 1
fi

cd "$WORKDIR"
git add -A
if git diff --cached --quiet; then
  echo "==> No changes — backup already current."
else
  git commit -q -m "Backup local config $(date -u +%Y-%m-%dT%H:%MZ)"
  git push -q -u origin HEAD
  echo "==> Backed up to $PRIVATE_REPO_URL"
fi
