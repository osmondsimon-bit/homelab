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
| tailscale | 110 | LXC (Debian 12, unpriv) | YOUR_TAILSCALE_LAN_IP | Running — subnet router, advertises YOUR_LAN_CIDR (ADR-003/005). To migrate onto the NUC. |

**Network note:** mgmt-vm is on the Home VLAN. VLAN tagging on the VM NIC is off for now — relying on UniFi to assign the correct VLAN via port profile.

## Hardware & cluster roadmap

Moving from a single host to a **3-node Proxmox cluster**, with local storage standardised on **ZFS** so HA failover works via replication (ADR-009). Still **all local storage** — no NAS/shared storage; HA comes from ZFS replication, not shared disks.

| Node | Role | Status | Intended to run |
|------|------|--------|-----------------|
| apophis | Compute-heavy | Live | Plex (QuickSync) + media stack; HA VM or its failover target |
| Intel NUC (name TBD) | Low-power, decent RAM | Soon | Simple services offloaded from apophis: Tailscale, Technitium, Homepage, Monitoring |
| 2nd ThinkCentre M920Q | Cluster + HA quorum | ~1 month | HA-failover target; extra capacity |

Offloading the simple services to the NUC frees apophis's CPU for Plex transcoding. Three nodes give clean cluster quorum. Mixed CPUs are fine for HA failover (restart-on-another-node); live migration between different CPU generations needs a compatible CPU type.

## Provisioning & tooling

- **Terraform** (`bpg/proxmox` provider) **creates** infrastructure — VMs/LXCs, disks, NICs (ADR-008). Scaffolded in `terraform/`; existing VMs to be imported.
- **Ansible** **configures** what Terraform creates — packages, services, app config (ADR-005). The `pct create`-via-Ansible lifecycle is superseded by Terraform; Ansible keeps the config role.
- Boundary: *Terraform = the box exists with the right shape; Ansible = the box is set up.*

## Planned VMs/LXCs

| Service | Type | Node (intended) | Purpose |
|---------|------|-----------------|---------|
| Technitium DNS | LXC | NUC | Ad/tracker blocking DNS for all VLANs, with blocklists |
| Monitoring (Prometheus + Grafana) | LXC/VM | NUC | Observability — scrapes Proxmox, UniFi, HA. **Prioritised first.** |
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

- UniFi firewall rules: block IoT → Home, Camera → LAN, Guest → LAN
- Lock Proxmox UI to VLAN 254 only
- Disable root SSH on all VMs, use key auth only
- Run fail2ban on SSH-exposed VMs
- No services exposed directly to internet — Tailscale for remote access

## Home Assistant expansion

- Install HACS
- Add Node-RED for automation logic
- ESPHome ready for future DIY sensors
- Wire HA stats into Grafana

## Phase order

1. VLAN-aware Proxmox + firewall rules — ✓ completed
2. Tailscale ✓ + **Technitium DNS** — Technitium next, completes Phase 2
3. **Foundation + observability:** adopt Terraform (import existing VMs) → **Monitoring** (Prometheus + Grafana) → **Homepage**
4. **Multi-node + HA:** Intel NUC joins the cluster → migrate simple services (Tailscale, Technitium) onto it (frees apophis); 2nd ThinkCentre → 3-node cluster on ZFS, replication + **HA for the Home Assistant VM**; stand up VM-level backups
5. **Media:** Plex (QuickSync) + qBittorrent/Gluetun on the freed-up apophis
6. **Secrets + HA expansion:** self-host Vaultwarden (now HA + backups exist); HACS, Node-RED, ESPHome, HA → Grafana
- Cross-cutting (designed early, not deferred to the end): VM-level backups, a patching approach
- Deferred to the new house: NAS / shared storage, cameras, Frigate

## Open tasks & decisions (carry-over)

Living backlog to pick up next session. Detail and rationale: `docs/reviews/2026-06-14-session-closeout.md`.

### Next build (Phase 2 → 3)
- [ ] **Technitium DNS** — write `provision-technitium.yml`, an ADR for the DNS-engine choice (Technitium vs Pi-hole/AdGuard), and a careful DHCP→DNS cutover plan. Completes Phase 2.
- [ ] **Terraform apply/import** — scaffold done (ADR-008, `terraform/`). Next: create a Proxmox API token, fill `terraform.tfvars`, `terraform import` the running VMs (mgmt-vm, HA, tailscale) into state — carefully, against live VMs.
- [ ] **Monitoring stack** (Prometheus + Grafana), then **Homepage** — Phase 3, intended on the NUC.

### Security / infra — needs hands on Proxmox/UniFi/Tailscale/GitHub
- [ ] **[High]** Replace root-over-SSH to apophis with a scoped `provision` user (sudo limited to `pct`/`qm`/`pveam`, connect via `become`); then disable root SSH. Confirm the mgmt-vm SSH key has a passphrase.
- [ ] **[High]** Restrict the Proxmox management plane now (don't wait for VLANs): firewall SSH (22) + UI (8006) to mgmt-vm + the Tailscale CGNAT range; add a non-root Proxmox admin with TOTP.
- [ ] **[Med]** Harden the GitHub token on mgmt-vm — fine-grained single-repo expiring PAT, or switch the remote to an SSH deploy key (replaces the cleartext `~/.git-credentials` token).
- [ ] **[Med]** Tailscale hardening: mint ephemeral single-use enrollment keys; pass the key via stdin/file not the `pct exec` argv; define + document a tailnet ACL and tag the node `tag:infra`; confirm node key-expiry is disabled.
- [x] **Back up the now-local-only config — layer (a) done (ADR-007).** Real config + `.claude/` agents/memory are backed up off-box to the private `homelab-private` repo via `scripts/backup-local-config.sh`. Credentials excluded by design.
- [ ] **[High] Proper VM-level backups — layer (b) still pending.** Set up **Proxmox Backup for the mgmt-vm** (+ home-assistant + new LXCs) — captures the OS, packages, SSH keys, everything in one shot. The private-repo backup (a) is only an interim config safety net. Needs a backup target (PBS or off-box storage); pull forward from Phase 3.

### Small / quick
- [ ] Drop `--accept-routes` from `provision-tailscale.yml` and re-run (unnecessary on a subnet router).
- [ ] Confirm `YOUR_TAILSCALE_LAN_IP` is reserved/excluded in UniFi (a fixed-IP entry or outside the DHCP pool).
- [ ] Document the cross-subnet Zigbee path: how HA on `the LAN subnet` reaches the SLZB-06 at `YOUR_ZIGBEE_COORD_IP` today (becomes a firewall/route rule once VLANs land).
- [ ] Convert the security-hardening list (fail2ban, VLAN firewall rules, Proxmox lockdown) into tracked tasks with owners/dates so they don't drift.

### Decisions to make
- [ ] **Patching/update approach** — settle the shape (unattended-upgrades on guests + rolling monthly Proxmox window with HA failover) and write the ADR.
- [ ] **Version the agents?** `.claude/agents/*.md` (infra-designer, infra-manager, doc-auditor) are gitignored / local-only, but index.md, CLAUDE.md, and the cloud routine reference them. Add a narrow `.gitignore` exception for `.claude/agents/*.md` only (transcripts/memory/settings stay private) to publish them to the repo? No secrets in them. Outward-facing — your call.

_Resolved this session:_ RAM trim (moot — services now spread across 3 nodes); Proxmox API Ansible modules (superseded by Terraform, ADR-008); drop the `100.x` IP (done — full decouple, ADR-006).
