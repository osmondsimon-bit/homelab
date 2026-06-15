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
| Provisioning (create) | Terraform (`bpg/proxmox`) | Adopted (ADR-008) — scaffolded in `terraform/`; import existing VMs next |
| Provisioning (configure) | Ansible | Active (ADR-005) — config role; VM/LXC lifecycle now via Terraform |
| Multi-node cluster + HA | Proxmox cluster + ZFS replication | Accepted direction (ADR-009) — 3 nodes (apophis + NUC + ThinkCentre), executed as hardware lands |
| DNS + ad blocking | Technitium DNS | Phase 2 — next; intended on the NUC |
| Remote access (HA) | Cloudflare Tunnel (cloudflared add-on) | Already running for Home Assistant |
| Remote access (admin) | Tailscale | Deployed — CT 110; to migrate to the NUC |
| Monitoring | Prometheus + Grafana | Phase 3 — prioritised first; intended on the NUC |
| Service dashboard | Homepage | Phase 3 — after Monitoring; intended on the NUC |
| Media server | Plex | Phase 5 — apophis, QuickSync passthrough |
| Torrent client + VPN | qBittorrent + Gluetun + ProtonVPN Plus | Phase 5 — apophis |
| Password manager | Vaultwarden (self-hosted) | Phase 6 (ADR-010) — sequenced after HA + backups; Bitwarden cloud bridges now |
| Secret handling | Ansible Vault | Infra/machine secrets; human passwords → Vaultwarden |
| Local config backup | Private repo + `backup-local-config.sh` | Adopted (ADR-007) — interim off-box backup |

---

## Deferred — re-evaluate at phase boundary

| Capability | Tool | Defer until | Trigger |
|------------|------|------------|---------|
| VM-level backups | Proxmox Backup Server / Backrest | Phase 3 (pull fwd) | Config layer done (ADR-007); VM/OS backup still needed — pull forward, config is single-disk |
| Updates / patching | unattended-upgrades + rolling Proxmox window | Phase 3–4 | Design the ADR (guests auto-patch; nodes patched rolling with HA failover) |
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
| NAS / shared storage | TBD (Synology / TrueNAS) | New house — media + backups (HA uses ZFS replication on local disks until then, ADR-009) |
| Cameras + NVR | Frigate | New house — requires NAS |

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
| 2026-06-14 | Phase 2 | Tailscale deployed (CT 110) via Ansible — first fully Ansible-provisioned service, validated remotely |
| 2026-06-14 | Phase 2 | Config decoupled from public repo (ADR-006); local-only config backed up to private repo (ADR-007) |
| 2026-06-14 | Phase 2/3 planning | Adopted Terraform (ADR-008); 3-node cluster + HA via ZFS replication (ADR-009); Vaultwarden self-hosted, sequenced after HA+backups (ADR-010); Monitoring→Homepage prioritised; patching to design |

*Add a row each time this radar is reviewed at a phase boundary.*
