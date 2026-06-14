# Technology Radar

Tracks capabilities evaluated for this homelab — what's adopted, what's deferred, and when to re-evaluate.
Reviewed at each phase boundary and by the infra-manager weekly routine.

Reference platform reviewed: [TadMSTR homelab-agent](https://github.com/TadMSTR/homelab-agent) — a mature multi-agent homelab platform. Useful as an aspirational reference; not all components are appropriate at this scale.

---

## Adopted

| Capability | Tool | Notes |
|------------|------|-------|
| AI coding agent | Claude Code | Primary tool, runs on mgmt-vm |
| On-demand infra review | `infra-designer` agent | Invoked before any new VM/LXC/network change |
| Scheduled status reports | `infra-manager` routine | Weekly, Mondays 08:00 UTC via Claude Code cloud |
| DNS + ad blocking | Technitium DNS | Phase 2 — LXC planned |
| Remote access (HA) | Cloudflare Tunnel (cloudflared add-on) | Already running for Home Assistant |
| Remote access (admin) | Tailscale | Phase 2 — LXC planned |
| Password manager | Vaultwarden | Phase 4 — LXC planned |
| Media server | Plex | Phase 3 — VM planned, QuickSync passthrough |
| Torrent client + VPN | qBittorrent + Gluetun + ProtonVPN Plus | Phase 3 — LXC planned |
| Monitoring | Prometheus + Grafana | Phase 3 — VM planned |
| Infrastructure as code | Ansible | Active (ADR-005) — control node = mgmt-vm; first playbook: Tailscale |
| Secret handling | Ansible Vault / env vars | Convention only — no tooling yet |

---

## Deferred — re-evaluate at phase boundary

| Capability | Tool | Defer until | Trigger |
|------------|------|------------|---------|
| Automated backups | Backrest / Proxmox Backup Server | Phase 3 | Before Plex goes live — media needs backup strategy |
| SSO / forward auth | Authentik | Phase 4+ | 4+ services with independent login |
| Self-hosted git | Gitea | New house | Second server + NAS available |
| CI/CD pipeline | Woodpecker CI | New house | Active Ansible pipeline needing automated testing |
| MCP server (Proxmox API) | Community / custom | Phase 3 | Ansible active, AI agents need infra control |
| MCP server (Grafana) | Grafana MCP | Phase 3 | Grafana deployed and being actively used |
| Infra agent tool access | scoped-MCP pattern (TadMSTR) | Phase 4 | More than 2 agents needing scoped tool sets |
| Workflow engine | Temporal | New house | Complex multi-step automation beyond Ansible |
| Dependency updates | Renovate | New house | Active container/package deployments to manage |

---

## Deferred — new house

These require more hardware (second server, NAS, more RAM) or are aspirational until the next build.

| Capability | Tool | Notes |
|------------|------|-------|
| Local LLM inference | Ollama | Needs dedicated GPU or high-RAM host |
| Private web search | SearXNG | Pairs with Ollama — defer together |
| Vector memory | Milvus / memsearch | Requires Ollama and a memory architecture decision |
| Knowledge graph | Graphiti / Neo4j | Advanced agent memory — long-term |
| LLM observability | Langfuse | Only useful when Ollama is running |
| APM / distributed tracing | SigNoz | Overkill until multiple networked services |
| Multi-agent message bus | Matrix + NATS | Requires 5+ concurrent specialised agents |
| Inter-agent event log | agent-bus (TadMSTR) | Follows from Matrix + NATS |
| Agent task queue | DragonflyDB + task-queue-mcp | Follows from multi-agent engine |
| NAS | TBD (Synology / TrueNAS) | New house — media + backups |
| Cameras + NVR | Frigate | New house — requires NAS |
| Second server | TBD | New house — enables Gitea, HA clustering |

---

## Skip / not applicable

| Capability | Reason |
|------------|--------|
| HashiCorp Vault | Vaultwarden is sufficient at this scale |
| PM2 process manager | Docker-centric; not applicable to Proxmox VM/LXC model |
| Docker Compose stacks | Services run as Proxmox VMs/LXCs, not containers |
| Btrfs snapshots (btrbk) | Proxmox uses ZFS/ext4; use Proxmox Backup Server instead |

---

## Review log

| Date | Phase | Outcome |
|------|-------|---------|
| 2026-06-14 | Phase 1 complete | Initial radar populated from TadMSTR reference review |
| 2026-06-14 | Phase 2 start | Ansible activated (ADR-005) as the provisioning layer; Tailscale is the first managed service |

*Add a row each time this radar is reviewed at a phase boundary.*
