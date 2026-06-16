# Homelab Plan

## Current infrastructure

### apophis (Proxmox host)
- Intel i7-8700T, 16 GB RAM, ~500 GB SSD (LVM-thin today; migrating to ZFS — see Cluster & HA)
- IP: YOUR_PROXMOX_IP
- vmbr0 is VLAN-aware — completed

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| mgmt-vm | 100 | VM (Ubuntu Server) | YOUR_MGMT_VM_IP | Running — git, Claude Code, Terraform + Ansible control node |
| home-assistant | 200 | VM (HAOS) | YOUR_HA_IP | Running — Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP. HA-failover target once clustered. |
| tailscale | 110 | LXC (Debian 12, unpriv) | YOUR_TAILSCALE_LAN_IP | Running — subnet router, advertises YOUR_LAN_CIDR (ADR-003/005). To migrate onto oneill. |

### oneill (Intel NUC, Proxmox host)
- Intel N150, 4 cores / 4 threads, 16 GB RAM, single ~477 GB SSD (**ZFS-on-root**, `rpool` — ADR-009)
- IP: YOUR_NUC_IP — Proxmox VE 9.2, standalone (joins the cluster in Phase 4)
- The low-power "simple services" node, offloading apophis (ADR-009 hardware roadmap)

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| technitium | 111 | LXC (Debian 12, unpriv) | YOUR_TECHNITIUM_IP | Running — DNS-only resolver, OISD blocklist + DoH forwarders (ADR-011). **Live** — DHCP serves it on home/IoT/guest VLANs (camera + management excluded, no internet). |

**Network note:** mgmt-vm is on the Home VLAN. VLAN tagging on the VM NIC is off for now — relying on UniFi to assign the correct VLAN via port profile.

## Hardware & cluster roadmap

Moving from a single host to a **3-node Proxmox cluster**, with local storage standardised on **ZFS** so HA failover works via replication (ADR-009). Still **all local storage** — no NAS/shared storage; HA comes from ZFS replication, not shared disks.

| Node | Role | Status | Intended to run |
|------|------|--------|-----------------|
| apophis | Compute-heavy | Live | Plex (QuickSync) + media stack; HA VM or its failover target |
| Intel NUC (**oneill**, N150 / 16 GB / ZFS) | Low-power | **Live (standalone)** — running Technitium | Simple services offloaded from apophis: Technitium ✓, then Monitoring, Homepage, Tailscale |
| 2nd ThinkCentre M920Q | Cluster + HA quorum | ~1 month | HA-failover target; extra capacity |

Offloading the simple services to the NUC frees apophis's CPU for Plex transcoding. Three nodes give clean cluster quorum. Mixed CPUs are fine for HA failover (restart-on-another-node); live migration between different CPU generations needs a compatible CPU type.

## Provisioning & tooling

- **Ansible currently creates *and* configures** the LXCs — `pct create` + config in the `provision-*.yml` playbooks (ADR-005). This is the interim mechanism and recovers cleanly by re-running.
- **Terraform** (`bpg/proxmox`, ADR-008) is scaffolded but its **import is deferred to cluster scale** — it will take over the *create* role then. Target boundary: *Terraform = box exists with the right shape; Ansible = box is set up.*

## Planned VMs/LXCs

| Service | Type | Node (intended) | Purpose |
|---------|------|-----------------|---------|
| ~~Technitium DNS~~ | LXC | **oneill** | ✅ Live — CT 111 on oneill (see Current infrastructure). DNS-only, OISD blocklist + DoH (ADR-011). UniFi keeps DHCP, serves it on home/IoT/guest VLANs. |
| Monitoring (Prometheus + Grafana + Alertmanager) | LXC | oneill (CT 114, `.9`) | Observability + alerting — scrapes Proxmox, UniFi, HA (ADR-013). Dashboards/alerts as code; apophis dead-man's-switch. **Next build, in 2 steps.** |
| Homepage | LXC | NUC | Service dashboard (gethomepage.dev). After Monitoring. |
| Plex | VM | apophis | Media server, Intel QuickSync passthrough |
| qBittorrent + Gluetun | LXC | apophis | Torrent client behind Gluetun killswitch → ProtonVPN Plus |
| Vaultwarden | LXC | cluster (HA) | Self-hosted password manager — **sequenced after the HA cluster + backups** (ADR-010) |

Per-service RAM/disk sizing is set when each is built; with services spread across three nodes the old single-16 GB-host budget no longer binds. Plex stays on apophis for the iGPU.

**Media stack:** qBittorrent + Gluetun in one LXC — Gluetun runs the ProtonVPN Plus tunnel + killswitch (all torrent traffic exits via ProtonVPN, drops if the tunnel dies). Plex serves media; shared download path via bind mount (NAS deferred to new house).

**Password manager (ADR-010):** self-host **Vaultwarden** (local Bitwarden-compatible). It's zero-knowledge — the server stores only ciphertext, so theft of a node never exposes passwords and encrypted backups are safe to store anywhere. Sequenced *after* the HA cluster (solves availability) and the backup story (solves durability). **Bridge with Bitwarden's cloud now**; migration to Vaultwarden is a trivial export/import. Infra/machine secrets stay in `ansible-vault`, not Vaultwarden.

## Updates & patching

Keeping nodes + guests patched is an open design item (ADR pending). Likely shape: `unattended-upgrades` for security patches on Debian/Ubuntu guests; a deliberate **monthly Proxmox update window**, rolling one node at a time once clustered, with HA failover covering the reboot. Revisit dedicated tooling (a patch dashboard) later.

## Security hardening

Standard practices: network segmentation, least-privilege access, and no direct internet exposure.

## Home Assistant expansion

- Install HACS
- Add Node-RED for automation logic
- ESPHome ready for future DIY sensors
- Wire HA stats into Grafana

## Phase order

1. VLAN-aware Proxmox + firewall rules — ✓ completed
2. Tailscale ✓ (CT 110) + Technitium DNS ✓ (CT 111 on oneill, live on home/IoT/guest VLANs) — **✓ completed**
3. **Foundation + observability:** **VM-level backups first** (entry task) → **Monitoring** (Prometheus + Grafana) → **Homepage**. (Terraform import deferred to cluster scale — ADR-008; Ansible-pct creates the boxes for now.)
4. **Multi-node + HA:** Intel NUC (oneill) joins the cluster → migrate remaining simple services (Tailscale) onto it (Technitium already there); 2nd ThinkCentre → 3-node cluster on ZFS, replication + **HA for the Home Assistant VM**; a 2nd Technitium instance removes the DNS SPOF
5. **Media:** Plex (QuickSync) + qBittorrent/Gluetun on the freed-up apophis
6. **Secrets + HA expansion:** self-host Vaultwarden (now HA + backups exist); HACS, Node-RED, ESPHome, HA → Grafana
- Cross-cutting (designed early, not deferred to the end): VM-level backups, a patching approach
- Deferred to the new house: NAS / shared storage, cameras, Frigate

## Open tasks & decisions (carry-over)

Living backlog to pick up next session.

### Next build (Phase 3)
- [x] **Technitium DNS** — ✅ done. Deployed on **oneill** (CT 111, `YOUR_TECHNITIUM_IP`): DNS-only, OISD Big blocklist + DoH forwarders, console secured. Config applied declaratively by `provision-technitium.yml` via the Technitium API (from group_vars). DHCP cutover live on home/IoT/guest VLANs (camera + management intentionally excluded — no internet). Old apophis CT 111 destroyed; `.5` freed.
- [~] **[High] VM-level backups — Phase 3 ENTRY task** (**ADR-012**, infra-designer reviewed). oneill is the backup hub. **PBS done** (images of mgmt-vm + CTs, scheduled, see Backups below). **Remaining: HA native backup** — Samba share (`provision-ha-backup-share.yml`) + HAOS partial backup, then remove the interim safety net (see Backups). Must be complete before any stateful service lands on oneill.
- [ ] **Terraform import — DEFERRED to cluster scale** (ADR-008). Ansible (`pct`) creates + configures the LXCs for now and recovers cleanly; scaffold kept in `terraform/`. Revisit when the 3-node cluster lands (then: PVE API token, import live guests, refactor playbooks to config-only).
- [ ] **Monitoring stack** (Prometheus + Grafana), then **Homepage** — Phase 3, on oneill.

### Backups
- [x] Local config backup — done (ADR-007); now includes ansible inventory + host_vars.
- [x] **VM images via PBS** — PBS on oneill (CT 112), apophis wired (scoped token), scheduled daily (**VM 100 mgmt-vm** → keep 7d/4w), GC daily. (ADR-012) CTs excluded — reproducible from playbooks (mgmt-vm is the only guest not in code).
- [ ] **[High] HA native backup — NOT set up yet.** Run `provision-ha-backup-share.yml --limit oneill` (Samba CT 113), then in HAOS add the CIFS share + schedule a **PARTIAL** backup (HA + Zigbee2MQTT + add-ons; **exclude media**; tune recorder `purge_keep_days`). This is HA's primary protection (whole-VM HA is intentionally excluded from PBS).
- [ ] **Then remove the interim safety net** — once an HA native partial backup is verified landing on the share, delete the stale local `vzdump-qemu-200` (HA) image on apophis `local` (and the redundant local `vzdump-qemu-100` images, now covered off-box by PBS). Until then, **keep them** — they're HA's only backup in the gap.
- [ ] **CT 111 reprovision drill** — destroy + re-run `provision-technitium.yml`, record actual RTO. Converts the "Ansible-rebuild is sufficient" claim into a tested fact before the lab grows.
- [ ] **Off-site copy (this is how we "back up oneill") — deferred (ADR-012).** oneill's services rebuild from code, but the backup *data* (PBS datastore + HA share) is a single copy until an encrypted off-site sync (cloud) exists. Don't copy it to apophis (circular/same-site). Recovery model in `docs/operations/runbooks.md`.

### Small / quick
- [ ] Drop `--accept-routes` from `provision-tailscale.yml` and re-run (unnecessary on a subnet router).
- [ ] Confirm/reserve these in UniFi (fixed-IP entries or outside the DHCP pool): `YOUR_TAILSCALE_LAN_IP` (.4), and the monitoring CT `.9` (ADR-013, before/with that build).
- [ ] Document the cross-subnet Zigbee path: how HA on `the LAN subnet` reaches the SLZB-06 at `YOUR_ZIGBEE_COORD_IP` today (becomes a firewall/route rule once VLANs land).

### Decisions to make
- [ ] **Patching/update approach** — settle the shape (unattended-upgrades on guests + rolling monthly Proxmox window with HA failover) and write the ADR. Fold in a **host-prep step/playbook** (fresh PVE nodes ship enterprise repos that 401 without a sub → switch to `pve-no-subscription`; done manually on oneill 2026-06-16) so new nodes are reproducible.
- [ ] **Version the agents?** `.claude/agents/*.md` (infra-designer, infra-manager, doc-auditor) are gitignored / local-only, but index.md, CLAUDE.md, and the cloud routine reference them. Add a narrow `.gitignore` exception for `.claude/agents/*.md` only (transcripts/memory/settings stay private) to publish them to the repo? No secrets in them. Outward-facing — your call.

_Resolved this session:_ RAM trim (moot — services now spread across 3 nodes); Proxmox API Ansible modules (superseded by Terraform, ADR-008); drop the `100.x` IP (done — full decouple, ADR-006).
