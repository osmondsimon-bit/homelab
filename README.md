# Simon's Homelab

Infrastructure documentation, provisioning scripts, and configuration for a Proxmox-based home server.

**Host:** apophis — Intel i7-8700T, 16 GB RAM, ~500 GB SSD, running Proxmox VE at `YOUR_PROXMOX_IP`

**mgmt-vm:** Ubuntu Server at `YOUR_MGMT_VM_IP` — git, Claude Code, scripts, Ansible control node

## Key docs

| Doc | Purpose |
|-----|---------|
| [homelab/PLAN.md](homelab/PLAN.md) | Services, RAM budget, phase order |
| [homelab/decisions/](homelab/decisions/) | Architecture Decision Records |
| [homelab/docs/tech-radar.md](homelab/docs/tech-radar.md) | Capabilities evaluated, deferred, or planned |
| [homelab/docs/operations/runbooks.md](homelab/docs/operations/runbooks.md) | Common operational procedures |
| [AGENTS.md](AGENTS.md) | AI agent behaviour rules |
| [CLAUDE.md](CLAUDE.md) | Claude Code specific guidance |
| [index.md](index.md) | AI agent navigation map |

## Current phase

**Phases 3–7 complete** — foundation + observability, multi-node cluster + HA, secrets (Vaultwarden), media (Jellyfin/qBittorrent), and media automation (the *arr stack) are all live. **Next: Phase 8 — resilience + off-site recovery** ("close silent-failure blind spots": off-site backup, DNS failover, leak scanning/CI, and intent-compliance auditing). The 2-node cluster deliberately keeps manual quorum recovery and manual failover; no QDevice or automatic HA manager is planned.

**[PLAN.md](homelab/PLAN.md) is the single source of truth** for phase/status and the service inventory — this line is a pointer, not a duplicate (keep it that way to avoid drift).
