# ADR-007: Off-box backup of local-only config via a private repo

**Date:** 2026-06-14  
**Status:** Accepted — implementation drift and remediation tracked

## Context

ADR-006 moved real config (IPs, inventory, `group_vars`) out of the public repo into gitignored
local files. Together with local Claude/Codex agent configuration and memory, this means a set
of important, non-secret files lives outside the public repo. PBS now covers the mgmt-vm, but the
private repo remains the quick off-box copy for restoring local configuration without restoring
the whole VM.

An immediate, no-new-infrastructure backup was needed. Options: ansible-vault-encrypt-and-commit
to the public repo, a private repo, or wait for Proxmox backups. The private repo is the simplest
off-box, off-site safety net available today.

## Decision

A **private** GitHub repo, `homelab-private`, was intended to hold off-box copies of local-only,
**non-credential** files. `homelab/scripts/backup-local-config.sh` performs the backup: it
clones/pulls the private repo into `~/homelab-private` (gitignored from the public repo), copies
the configured paths in, runs a limited high-risk-pattern safety check, then commits and pushes.

Backed up:
- `homelab/ansible/inventory/hosts.ini` and `inventory/group_vars/all.yml` (real values)
- `.claude/agents/` (agent definitions)
- `.claude/skills/` (local Claude skills, including `phase-gate`)
- `.claude/projects/-home-simon/memory/` (auto-memory)
- `.codex/AGENTS.md` and `.codex/config.toml` (non-secret Codex local config)

**Credential policy at acceptance:** SSH private keys and recognizable GitHub/Tailscale tokens
were excluded. GitHub access uses a dedicated `~/.ssh/id_ed25519_github` key rather than a
plaintext PAT; the key is present in the full mgmt-vm PBS image but excluded from this private
config repo. The script's pattern check detects only a narrow set of private-key and token formats;
it is not a general secret scanner and cannot establish that the backup is non-credential.

**Convention (standard part of the workflow for now):** run the backup script after changing local
config and at session close. The private repo complements PBS by keeping the small, portable local
config set easy to inspect and restore.

## Consequences

- Restores the off-box safety net the decouple removed — real config + agents + memory survive a
  mgmt-vm disk loss.
- The private repo contains real IPs; that's acceptable because it's private.
- This is **not** a substitute for full VM backups (which also capture the OS, packages, and
  everything else). PBS now covers the mgmt-vm; the private repo remains the portable config layer.
- Restore procedure: after a full mgmt-vm image restore, use the restored dedicated GitHub SSH key
  to clone `homelab-private` and copy files back under `$HOME`. On a fresh build, generate and
  register a new dedicated GitHub SSH key first.
- Manual for now; could be automated later (cron or a git post-commit hook) — deferred to keep it
  simple while the cadence is low.

## Implementation reality and interim handling — 2026-07-21

The original non-credential classification no longer matches the backup set. The copied
`ansible/inventory/group_vars/all.yml` contains machine credentials, including VPN configuration
and service API keys. Those values are ignored by the public repository but tracked in the private
repository, including its Git history. `homelab-private` is therefore **credential-bearing in
practice**. Its private GitHub visibility reduces public exposure but is not encryption and does
not make it a general-purpose secret store.

Until the PLAN backlog selects and implements a durable model:

- `/home/simon` is the authoritative working and deployment tree.
- `/home/simon/homelab-private` is a separate backup repository; its nested `homelab/` is a
  restore snapshot and must never be edited or used for deployment.
- Treat access to the private repository and every clone as access to recovery credentials. Do
  not print, paste, log, or expose values from the copied secret-bearing files.
- Deleting a value from the current file does not remove it from Git history. Any migration away
  from plaintext tracking must include an explicit history and credential-rotation decision.

This section documents a known security gap; it does not supersede the original goal. Resolution
is tracked as **Resolve private config backup secret handling** in `PLAN.md`.
