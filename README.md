# Simon's Homelab

Infrastructure documentation, provisioning scripts, and configuration for a Proxmox-based home server.

**Host:** apophis — Intel i7-8700T, 16 GB RAM, ~500 GB SSD, running Proxmox VE at `YOUR_PROXMOX_IP`  
**mgmt-vm:** Ubuntu Server at `YOUR_MGMT_VM_IP` — git, Claude Code, scripts, Ansible control node

## Key docs

| Doc | Purpose |
|-----|---------|
| [homelab/PLAN.md](homelab/PLAN.md) | Services, RAM budget, phase order |
| [homelab/decisions/](homelab/decisions/) | Architecture Decision Records |
| [docs/tech-radar.md](docs/tech-radar.md) | Capabilities evaluated, deferred, or planned |
| [docs/operations/runbooks.md](docs/operations/runbooks.md) | Common operational procedures |
| [AGENTS.md](AGENTS.md) | AI agent behaviour rules |
| [CLAUDE.md](CLAUDE.md) | Claude Code specific guidance |
| [index.md](index.md) | AI agent navigation map |

## Current phase

Phase 2 — Technitium DNS + Tailscale (security/access foundation)

See [PLAN.md](homelab/PLAN.md) for full phase order and service inventory.
