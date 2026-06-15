# ADR-007: Off-box backup of local-only config via a private repo

**Date:** 2026-06-14  
**Status:** Accepted

## Context

ADR-006 moved real config (IPs, inventory, `group_vars`) out of the public repo into gitignored
local files. Together with the already-local-only `.claude/` agents and memory, this means a set
of important, non-secret files now lives **only** on the mgmt-vm's disk. There is no VM-level
backup yet (Proxmox Backup is roadmapped for Phase 3), so a single disk failure would lose the
real inventory and the agent/memory state.

An immediate, no-new-infrastructure backup was needed. Options: ansible-vault-encrypt-and-commit
to the public repo, a private repo, or wait for Proxmox backups. The private repo is the simplest
off-box, off-site safety net available today.

## Decision

A **private** GitHub repo, `homelab-private`, holds off-box copies of local-only, **non-credential**
files. `homelab/scripts/backup-local-config.sh` performs the backup: it clones/pulls the private
repo into `~/homelab-private` (gitignored from the public repo), copies the configured paths in,
runs a credential-detection safety net, then commits and pushes.

Backed up:
- `homelab/ansible/inventory/hosts.ini` and `inventory/group_vars/all.yml` (real values)
- `.claude/agents/` (agent definitions)
- `.claude/projects/-home-simon/memory/` (auto-memory)

**Never backed up — regenerated/rotated on restore:** SSH private keys, `~/.git-credentials`,
GitHub/Tailscale tokens. The script aborts if it detects a private key or token in the backup set.

**Convention (standard part of the workflow for now):** run the backup script after changing local
config and at session close, until proper Proxmox VM backups exist.

## Consequences

- Restores the off-box safety net the decouple removed — real config + agents + memory survive a
  mgmt-vm disk loss.
- The private repo contains real IPs; that's acceptable because it's private.
- This is **not** a substitute for full VM backups (which also capture the OS, packages, and
  everything else). VM-level Proxmox Backup remains the proper fix, still tracked in PLAN.md.
- Restore procedure: clone `homelab-private`, copy files back to the same paths under `$HOME`,
  then regenerate the SSH key and mint a fresh GitHub token.
- Manual for now; could be automated later (cron or a git post-commit hook) — deferred to keep it
  simple while the cadence is low.
