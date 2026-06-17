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
| Provisioning (create + configure) | Ansible (`pct` in playbooks) | Interim mechanism — `provision-*.yml` pct-create + configure the LXCs and recover cleanly (ADR-005) |
| Provisioning (declarative IaC) | Terraform (`bpg/proxmox`) | Scaffolded (ADR-008) — **import deferred to cluster scale**; will take over the create role then |
| Multi-node cluster + HA | Proxmox cluster + ZFS replication | Accepted direction (ADR-009) — 3 nodes (apophis + NUC + ThinkCentre), executed as hardware lands |
| DNS + ad blocking | Technitium DNS | Phase 2 ✓ — live on **oneill** (NUC), CT 111. DNS-only, UniFi keeps DHCP (ADR-011); OISD Big + DoH, config automated via API. Serves the **home VLAN**; IoT/guest use the gateway (DNS-by-VLAN-role). |
| Remote access (HA) | Cloudflare Tunnel (cloudflared add-on) | Already running for Home Assistant |
| Remote access (admin) | Tailscale | Deployed — CT 110; to migrate to the NUC |
| Monitoring | Prometheus + Grafana + Alertmanager | Phase 3 ✓ — live on **oneill**, CT 114. Scrapes node/pve/UniFi/HA; Alertmanager → am-ntfy bridge → ntfy, starter rules + apophis dead-man's-switch (ADR-013) |
| Service dashboard | **Glance** (was Homepage) | Phase 3 — front-door on **oneill**, CT 115. Native Go binary (no Docker), links to Grafana; Homepage rejected as Docker-first (ADR-014). Wall-tablet UI is HA's job (Phase 6) |
| Media server | Plex | Phase 5 — apophis, QuickSync passthrough |
| Torrent client + VPN | qBittorrent + Gluetun + ProtonVPN Plus | Phase 5 — apophis |
| Password manager | Vaultwarden (self-hosted) | Phase 6 (ADR-010) — sequenced after HA + backups; Bitwarden cloud bridges now |
| Secret handling | Ansible Vault | Infra/machine secrets; human passwords → Vaultwarden |
| Local config backup | Private repo + `backup-local-config.sh` | Adopted (ADR-007) — interim off-box backup |

---

## Deferred — re-evaluate at phase boundary

| Capability | Tool | Defer until | Trigger |
|------------|------|------------|---------|
| VM-level backups | Proxmox Backup Server (on oneill) + HA native partial | Phase 3 entry task | **Approach decided (ADR-012):** oneill as backup hub — PBS for VM/CT images (cross-host) + HA partial backups to an oneill SMB/NFS share. Local-only for now; cloud off-site deferred. Build gated by infra-designer. |
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
| Docker Compose stacks | Services run as native packages/binaries in Proxmox VMs/LXCs, not containers. **Exception coming in Phase 5:** Gluetun is container-only, so Docker arrives then — confined to apophis for the media stack (ADR-014 rationale) |
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
| 2026-06-17 | Phase 3 | Monitoring stack live incl. Alertmanager→ntfy (ADR-013). Dashboard: **Homepage → Glance** (ADR-014) to keep oneill Docker-free; wall-tablet UI reassigned to HA (Phase 6); Docker deferred to Phase 5/Gluetun |

*Add a row each time this radar is reviewed at a phase boundary.*
