# Homelab Plan

## Current infrastructure

### apophis (Proxmox host)
- Intel i7-8700T, 16 GB RAM, ~500 GB SSD
- IP: YOUR_PROXMOX_IP
- vmbr0 is VLAN-aware — completed

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| mgmt-vm | 100 | VM (Ubuntu Server) | YOUR_MGMT_VM_IP | Running — git, Claude Code, scripts, Ansible control node (ADR-005) |
| home-assistant | 200 | VM (HAOS) | YOUR_HA_IP | Running — Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP |
| tailscale | 110 | LXC (Debian 12, unpriv) | YOUR_TAILSCALE_LAN_IP | Running — subnet router, advertises YOUR_LAN_CIDR, Tailscale IP YOUR_TAILSCALE_IP (ADR-003/005) |

**Network note:** mgmt-vm is on the Home VLAN. VLAN tagging on the VM NIC is off for now — relying on UniFi to assign the correct VLAN via port profile.

## Planned VMs/LXCs

| Service | Type | RAM | Disk | Purpose |
|---------|------|-----|------|---------|
| Technitium DNS | LXC | 512 MB | 8 GB | Ad/tracker blocking DNS for all VLANs, with blocklist support |
| Plex | VM | 4 GB | 32 GB | Media server with Intel QuickSync GPU passthrough (media on NAS later) |
| qBittorrent + Gluetun | LXC | 512 MB | 16 GB | Torrent client behind Gluetun VPN killswitch, routed through ProtonVPN Plus |
| Monitoring | VM | 1 GB | 20 GB | Prometheus + Grafana, scraping Proxmox, UniFi, HA |
| Vaultwarden | LXC | 256 MB | 8 GB | Self-hosted password manager |

**RAM budget:** host (2 GB) + mgmt-vm (4 GB) + home-assistant (4 GB) + Plex (4 GB) + LXCs (Technitium 512 MB + Tailscale 256 MB + qBittorrent/Gluetun 512 MB + Vaultwarden 256 MB + Monitoring 1 GB) ≈ 16.5 GB — marginally over. Monitoring may need to drop to 768 MB, or mgmt-vm trimmed to 2 GB once Ansible is stable.

**Media stack:** qBittorrent + Gluetun in a single LXC. Gluetun handles the ProtonVPN Plus WireGuard tunnel and killswitch — all qBittorrent traffic exits through ProtonVPN, drops if the tunnel goes down. Plex serves media; download location shared between the two (bind mount or NFS, NAS deferred to new house).

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

1. VLAN-aware Proxmox + firewall rules — completed
2. Tailscale ✓ + Technitium DNS (security/access foundation) — Tailscale deployed (CT 110); Technitium next
3. Plex + Monitoring
4. Vaultwarden + HA expansion
5. Everything else waits until the new house (NAS, cameras, second server, Frigate)

## Open tasks & decisions (carry-over)

Living backlog to pick up next session. Detail and rationale: `docs/reviews/2026-06-14-session-closeout.md`.

### Next build
- [ ] **Technitium DNS** — write `provision-technitium.yml`, an ADR for the DNS-engine choice (Technitium vs Pi-hole/AdGuard), and a careful DHCP→DNS cutover plan. Completes Phase 2.

### Security / infra — needs hands on Proxmox/UniFi/Tailscale/GitHub
- [ ] **[High]** Replace root-over-SSH to apophis with a scoped `provision` user (sudo limited to `pct`/`qm`/`pveam`, connect via `become`); then disable root SSH. Confirm the mgmt-vm SSH key has a passphrase.
- [ ] **[High]** Restrict the Proxmox management plane now (don't wait for VLANs): firewall SSH (22) + UI (8006) to mgmt-vm + the Tailscale CGNAT range; add a non-root Proxmox admin with TOTP.
- [ ] **[Med]** Harden the GitHub token on mgmt-vm — fine-grained single-repo expiring PAT, or switch the remote to an SSH deploy key (replaces the cleartext `~/.git-credentials` token).
- [ ] **[Med]** Tailscale hardening: mint ephemeral single-use enrollment keys; pass the key via stdin/file not the `pct exec` argv; define + document a tailnet ACL and tag the node `tag:infra`; confirm node key-expiry is disabled.

### Small / quick
- [ ] Drop `--accept-routes` from `provision-tailscale.yml` and re-run (unnecessary on a subnet router).
- [ ] Confirm `YOUR_TAILSCALE_LAN_IP` is reserved/excluded in UniFi (a fixed-IP entry or outside the DHCP pool).
- [ ] Document the cross-subnet Zigbee path: how HA on `the LAN subnet` reaches the SLZB-06 at `YOUR_ZIGBEE_COORD_IP` today (becomes a firewall/route rule once VLANs land).
- [ ] Convert the security-hardening list (fail2ban, VLAN firewall rules, Proxmox lockdown) into tracked tasks with owners/dates so they don't drift.

### Decisions to make
- [ ] **RAM trim before Phase 3:** mgmt-vm 4→2 GB *or* Monitoring 1 GB→768 MB — then freeze the committed total here (currently ~16.5 GB vs 16 GB physical).
- [ ] **Proxmox API modules:** keep the `community.general.proxmox` migration deferred until Plex/Phase 3 forces it (recommended) — confirm.
- [ ] **Version the agents?** `.claude/agents/*.md` (infra-designer, infra-manager, doc-auditor) are gitignored / local-only, but index.md, CLAUDE.md, and the cloud routine reference them. Add a narrow `.gitignore` exception for `.claude/agents/*.md` only (transcripts/memory/settings stay private) to publish them to the repo? No secrets in them. Outward-facing — your call.
- [ ] Optional: drop the literal Tailscale `100.x` IP from this file (public-repo exposure, low).
