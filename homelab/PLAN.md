# Homelab Plan

## Current infrastructure

### apophis (Proxmox host)
- Intel i7-8700T, 16 GB RAM, ~500 GB SSD
- IP: YOUR_PROXMOX_IP
- vmbr0 is VLAN-aware — completed

| VM/LXC | VMID | Type | IP | Status |
|--------|------|------|----|--------|
| mgmt-vm | — | VM (Ubuntu Server) | YOUR_MGMT_VM_IP | Running — git, Claude Code, scripts, Ansible control node (ADR-005) |
| home-assistant | 200 | VM (HAOS) | YOUR_HA_IP | Running — Zigbee2MQTT, SLZB-06 at YOUR_ZIGBEE_COORD_IP |

**Network note:** mgmt-vm is on the Home VLAN. VLAN tagging on the VM NIC is off for now — relying on UniFi to assign the correct VLAN via port profile.

## Planned VMs/LXCs

| Service | Type | RAM | Disk | Purpose |
|---------|------|-----|------|---------|
| Technitium DNS | LXC | 512 MB | 8 GB | Ad/tracker blocking DNS for all VLANs, with blocklist support |
| Tailscale | LXC | 256 MB | 4 GB | Remote access into homelab with subnet routing |
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
2. Technitium DNS + Tailscale (security/access foundation)
3. Plex + Monitoring
4. Vaultwarden + HA expansion
5. Everything else waits until the new house (NAS, cameras, second server, Frigate)
