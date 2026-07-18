# Technology Radar

Tracks capabilities evaluated for this homelab — what's adopted, what's deferred, and when to re-evaluate.
Reviewed at each phase boundary and by the infra-manager weekly routine.

Reference platform reviewed: [TadMSTR homelab-agent](https://github.com/TadMSTR/homelab-agent) — a mature multi-agent homelab platform. Useful as an aspirational reference; not all components are appropriate at this scale.

---

## Adopted

| Capability | Tool | Notes |
|------------|------|-------|
| AI coding agent | Claude Code | Primary tool on mgmt-vm; independent cold control node `mgmt-vm2` on Carter provides an Ansible/Git recovery workspace without copying agent credentials |
| On-demand infra review | `infra-designer` agent | Invoked before any new VM/LXC/network change |
| Scheduled status reports | `infra-manager` routine | Weekly, Mondays 08:00 UTC via Claude Code cloud |
| Provisioning (create + configure) | Ansible (`pct` in playbooks) | Interim mechanism — `provision-*.yml` pct-create + configure the LXCs and recover cleanly (ADR-005) |
| Provisioning (declarative IaC) | Terraform (`bpg/proxmox`) | Scaffolded (ADR-008) — **import deferred to cluster scale**; will take over the create role then |
| Multi-node cluster + manual failover | Proxmox cluster + ZFS replication (`pvesr`) | **Phase 4 ✓ 2026-06-25** — **2-node** cluster `homelab` (apophis + carter); oneill stays standalone (ADR-009, revised from 3-node). `pvesr` job 200-0 replicates VM 200 every 15 min; **manual failover, NO HA manager/fencing** (single-NIC network isn't HA-grade). Corosync 10s token ride-out; replication-health alerts live. |
| DNS + ad blocking | Technitium DNS | Phase 2 ✓ — CT 111 on **oneill**. DNS-only, UniFi keeps DHCP (ADR-011); OISD Big + DoH, config automated via API. Serves the **home VLAN**; IoT/guest use the gateway (DNS-by-VLAN-role). **Phase 4 ✓ 2026-06-25: DNS redundancy** — 2nd resolver CT 117 `technitium2` on **carter** (config-identical via the `technitium_instances` playbook loop), independent node from CT 111, removes the DNS SPOF. (Operator: hand both out as DHCP DNS servers.) |
| Remote access (HA) | Cloudflare Tunnel (cloudflared add-on) | Already running for Home Assistant |
| Remote access (admin) | Tailscale | HA subnet-router pair live — CT 110 on **apophis** + CT 126 on **oneill**, both advertising the LAN; Tailscale selects/fails over the route (ADR-003). |
| Monitoring | Prometheus + Grafana + Alertmanager | Phase 3 ✓ — live on **oneill**, CT 114. Scrapes node/pve/UniFi/HA; Alertmanager → am-ntfy bridge → ntfy, starter rules + apophis dead-man's-switch (ADR-013) |
| Service dashboard | **Glance** (was Homepage) | Phase 3 ✓ — front-door live on **oneill**, CT 115. Native Go binary (no Docker), links to Grafana; Homepage rejected as Docker-first (ADR-014). Wall-tablet UI is HA's job (Phase 5 HA-expansion) |
| VM/CT backups | Proxmox Backup Server (CT 112, oneill) | Phase 3 ✓ — PBS live, mgmt-vm imaged daily off-box; CTs rebuild from Ansible (ADR-012). HA native backup ✅ landing on share (CT 113); restore drill ✅ PASS 2026-06-18. Off-site copy deferred. |
| Media server | Jellyfin (was Plex) | **Phase 6 ✓ 2026-06-27** — CT 120 on **apophis**, unprivileged LXC, iGPU QuickSync (`/dev/dri` passthrough) proven; media on 500 GB USB-C SSD. ADR-021. |
| Torrent client + VPN | qBittorrent + **native WireGuard + nftables killswitch** + ProtonVPN Plus | **Phase 6 ✓ 2026-06-27** — CT 121 on **apophis**; leak-test ✅ (Gluetun/Docker rejected — native WG keeps service LXCs Docker-free). ADR-021. |
| Media automation | Sonarr + Radarr + Prowlarr + Jellyseerr + ByParr | **Phase 7 ✓ 2026-06-28** — Sonarr CT 123 + Radarr CT 124 (native Servarr, hardlinks via shared media-group); Prowlarr + ByParr (CF solver for 1337x) behind Gluetun on VM 125 (2nd ProtonVPN exit — bypasses AU ISP blocks + keeps consistent CF egress IP); Jellyseerr request UI on VM 125. ADR-022. |
| Password manager | Vaultwarden (self-hosted) | **Phase 5 ✓ 2026-06-26** — VM 118 on apophis, Ubuntu 24.04 + Docker container (native-LXC plan OOMed), Tailscale-Serve TLS, tailnet-only; `pvesr` to carter + PBS daily; tailnet ACL locks it to operator devices. ADR-010/014/018. |
| Secret handling | Tier 3 env files + Vaultwarden (Tier 1) | ADR-018 (revised 2026-06-25): **ansible-vault dropped** as never-wired-in. Machine tokens → gitignored `~/.*.env` on mgmt-vm; human-typed admin passwords → Vaultwarden. Tier 2 anchors (PBS/HA keys, 2FA recovery codes) → Keychain, outside the lab. |
| Local config backup | Private repo + `backup-local-config.sh` | Adopted (ADR-007) — interim off-box backup |
| Updates / patching | unattended-upgrades + maintenance intent metrics | ADR-015 live. Debian LXCs + Ubuntu VMs: security auto-patch at midday, no auto-reboot; other packages and reboots stay monthly/manual. PVE hosts remain manual. Glance shows pending/reboot/enrollment state; ntfy alerts only for overdue/security failures. Docker pins: Renovate proposals, manual deployment. |
| Dependency updates | Renovate | Docker-image proposals only: custom manager watches committed Ansible defaults; no automerge or automatic deployment. Broader package automation remains deferred. |
| Infra portal | Python + D2 generator → CT 116 nginx | Phase 3 ✓ — `infra-portal-generate.py` on mgmt-vm, daily systemd timer, rsync to CT 116 via restricted deploy key. Switch VLAN/PoE view, rack layout, network topology SVG (ADR-020). |

---

## Deferred — re-evaluate at phase boundary

| Capability | Tool | Defer until | Trigger |
|------------|------|------------|---------|
| SSO / forward auth | Authentik | Phase 4+ | 4+ services with independent login |
| Self-hosted git | Gitea | New house | Second server + NAS available |
| CI/CD pipeline | Woodpecker CI | New house | Active Ansible pipeline needing automated testing |
| MCP server (Proxmox API) | Community / custom | Phase 4+ | Parked — Ansible covers current needs; revisit when agent tool-use is a regular workflow |
| MCP server (Grafana) | Grafana MCP | Phase 4+ | Parked — Grafana live but read-via-browser; revisit if agent-driven dashboard work becomes common |
| Infra agent tool access | scoped-MCP pattern (TadMSTR) | Phase 5+ | Still parked — 4 agents exist (infra-designer, infra-manager, doc-auditor, continuity-reviewer) but each is narrow + manually-invoked; scoped-MCP plumbing not yet worth the overhead. Reassess Phase 5. |
| Workflow engine | Temporal | New house | Complex multi-step automation beyond Ansible |

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
| Docker Compose stacks | Services run as native packages/binaries on LXC service nodes (oneill stays Docker-free). **Contained exceptions, each isolated to its own VM:** Vaultwarden (VM 118, Phase 5 — container-only upstream; ADR-014 revised 2026-06-26) and the Gluetun/media-automation stack on apophis (VM 125, Phase 7 — Jellyseerr + Prowlarr + ByParr). The no-Docker principle for the LXC service nodes is intact. |
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
| 2026-06-17 | Phase 3 | Monitoring stack live incl. Alertmanager→ntfy (ADR-013). Dashboard: **Homepage → Glance** (ADR-014) to keep oneill Docker-free; wall-tablet UI reassigned to HA (HA-expansion phase); Docker deferred to the media phase/Gluetun |
| 2026-06-19 | Phase 3 ✓ CLOSED | Phase 3 fully complete. Backups tested (PBS + HA native, restore drill ✅). Patching adopted (ADR-015). Infra portal live (ADR-020). MCP rows parked. Plex renamed Jellyfin. |
| 2026-06-25 | Phase 4 ✓ CLOSED | 2-node cluster `homelab` (apophis + carter) live; apophis rebuilt on ZFS; `pvesr` replication + **manual failover** for VM 200 (no HA manager); 2nd Technitium (CT 117 on carter) removes the DNS SPOF; corosync 10s ride-out; monitoring deduped for clustered `pve_*` + replication-health alerts. Radar updated: Multi-node cluster, Technitium, Tailscale, Infra-agent-tool-access rows. Carry-forward: VM 200 failover drill + carter-rebuild runbook + off-site backup. |
| 2026-06-26 | Phase 5 Secrets ✓ CLOSED | Vaultwarden deployed (VM 118, Ubuntu 24.04 + Docker — native-LXC plan OOMed) → moved to Adopted; **Docker exception** moved Phase 6 → Phase 5 (each in its own VM; ADR-014 revised); **ansible-vault dropped** as never-wired-in (ADR-018) → Secret-handling row corrected; tailnet ACL + secrets-register added. VM 200 manual-failover drill ✅ PASS, VM 118 restore drill ✅ PASS, carter-rebuild runbook ✅ written, 2FA recovery codes → Keychain ✅ (carry-forwards cleared). Outstanding: off-site backup; CT 111/117 reprovision drills; node-down alert drill. |
| 2026-06-27 | Phase 6 ✓ CLOSED | Jellyfin (CT 120, iGPU QuickSync proven) + qBittorrent (CT 121, native WireGuard killswitch → ProtonVPN Plus, leak-test ✅) live on apophis; 500 GB USB-C SSD as shared media store. ADR-021 accepted. Media-server + Torrent-client rows updated to live. |
| 2026-06-28 | Phase 7 ✓ CLOSED | Sonarr CT 123 + Radarr CT 124 (native Servarr, hardlinks via shared media-group) + Jellyseerr + Prowlarr + ByParr on VM 125 (Prowlarr behind Gluetun / 2nd ProtonVPN exit to bypass AU ISP blocking; ByParr CF solver for 1337x). ADR-022 accepted + revised ×2. Media-automation row added. |

*Add a row each time this radar is reviewed at a phase boundary.*
