# ADR-005: Activate Ansible as the provisioning layer

**Date:** 2026-06-14  
**Status:** Accepted

## Context

Phase 2 begins adding services (Tailscale, Technitium, then Plex, Monitoring,
Vaultwarden). The first attempt provisioned Tailscale with a bash script downloaded
to the Proxmox host and run as root. That works, but it's imperative, run-once, and
reintroduces the ad-hoc host-management the repo is meant to avoid. The roadmap has
always positioned Ansible as the infrastructure-as-code layer (inventory already
exists); the start of the build-out is the right moment to activate it, before more
services accumulate as bash scripts that later need converting.

## Decision

Ansible is now the primary provisioning and configuration layer. New services are
deployed via playbooks run from the **admin VM** (the control node), not by scripts
executed on the hosts.

**Auth / connectivity model (deliberately minimal for the first iteration):**

- The control node connects to the **Proxmox host over SSH as root** (one credential:
  an SSH key from the admin VM in `root@apophis`'s `authorized_keys`).
- LXC/VM lifecycle is driven via `pct` / `qm` commands over that SSH connection, with
  idempotency guards (existence checks, `blockinfile`, `creates`). This mirrors the
  verified manual steps exactly and keeps the dependency surface to a single credential.
- Container-internal configuration is done via `pct exec` from the host — so we don't
  need SSH into each container or per-container keys.
- Secrets (e.g. the Tailscale auth key) are **prompted at runtime** (`vars_prompt`)
  and never written to the repo. Persistent secrets will use `ansible-vault`.

**Repo layout:**

```
ansible/
  ansible.cfg                 # inventory path, no host-key prompt, pipelining
  inventory/hosts.ini         # apophis (root), admin (simon)
  group_vars/all.yml          # non-secret defaults (CTIDs, IPs, sizing)
  playbooks/<service>.yml     # one playbook per service
```

## Consequences

- **Bootstrap cost (one-time):** install Ansible on the admin VM; add the admin VM's
  SSH key to `root@apophis`. No Proxmox API token or per-container keys needed yet.
- Provisioning is now declarative, idempotent, version-controlled, and re-runnable.
  The curl-to-host pattern is retired as the primary path.
- The existing `homelab/scripts/tailscale-lxc-provision.sh` is kept as a documented
  manual fallback and as the reference the playbook encodes — not the primary path.
- **Known trade-off:** driving `pct` via shell is less idiomatic than the
  `community.general.proxmox` API modules and we manage idempotency ourselves.
  Accepted for now to keep the bootstrap to a single credential; migrating LXC/VM
  lifecycle to the API modules (with a Proxmox API token) is a planned refinement.
- Connecting as `root` over SSH is acceptable on the trusted management path for now;
  a dedicated provisioning user with scoped `sudo` is a later hardening step, tracked
  against the "disable root SSH everywhere" goal in PLAN.md.
- Playbooks should be tested against a Proxmox snapshot before running on production
  hosts (existing convention).
