# Phase 7 — Media Automation

**Closed:** 2026-06-28 via `/phase-gate`
**ADR:** ADR-022 (Accepted, infra-designer-reviewed; revised ×2 — Prowlarr behind VPN, ByParr added)

## What shipped

| Service | Guest | Node | Key detail |
|---------|-------|------|------------|
| Sonarr | CT 123 (Debian 12 unpriv LXC) | apophis | Native Servarr install; TV automation → qBittorrent → hardlink-import into `/media/library/tv` |
| Radarr | CT 124 (Debian 12 unpriv LXC) | apophis | Native Servarr install; movie automation → `/media/library/movies` |
| Jellyseerr | VM 125 (Ubuntu 24.04, Docker) | apophis | Request UI — auths via Jellyfin, hands requests to Sonarr/Radarr; LAN-only on `:5055` |
| Prowlarr | VM 125 (Docker, `network_mode: service:gluetun`) | apophis | Indexer manager; **behind Gluetun** on a 2nd ProtonVPN WireGuard exit — see below |
| ByParr | VM 125 (Docker, `network_mode: service:gluetun`) | apophis | CF solver (FlareSolverr-compatible); shares Prowlarr's VPN netns; listens on `localhost:8191` |
| Gluetun | VM 125 (Docker, VPN gateway) | apophis | 2nd ProtonVPN exit (no port-forwarding); LAN reachback via `FIREWALL_OUTBOUND_SUBNETS` |

## Key decisions

- **Sonarr/Radarr as native Servarr installs** (not Docker) in unprivileged LXCs — consistent with ADR-014 (Docker confined to VMs). Co-located on apophis so downloads + library share the USB SSD (hardlinks work; link count ≥ 2 verified).
- **Shared media group** (phase 6 foundation) lets Sonarr/Radarr write to the same directories Jellyfin reads, with `UMask=0002` ensuring group-writable hardlinks.
- **Prowlarr moved behind a VPN** (original native CT 122 LAN-only plan failed): AU ISPs site-block indexer domains before Cloudflare even applies. Co-locating Prowlarr as a Docker container on the Jellyseerr VM (already Docker) behind Gluetun fixes the block without a new guest. CT 122 retired.
- **ByParr added** for 1337x specifically (Cloudflare-gated; TPB/LimeTorrents are not). Shares Gluetun's network namespace so the `cf_clearance` cookie IP matches Prowlarr's egress — this is the key constraint (solver and indexer client must use the same exit IP).
- **Jellyseerr on LAN-direct** (not behind the VPN) — request UI only; no indexer traffic.

## Verification

- Sonarr/Radarr: hardlink verified (`stat` shows same inode, link count ≥ 2 for an imported file).
- Prowlarr VPN egress: `docker exec gluetun wget -qO- https://api.ipify.org` returns ProtonVPN IP.
- ByParr: 1337x indexer test passed in Prowlarr (~15–40 s for CF solve, cookie then cached).
- Jellyseerr: HTTP 200 on `:5055/api/v1/status`; Jellyfin sign-in working.

## Carry-forwards

- Reprovision drills for CT 123, CT 124, VM 125 pending (playbooks exist; actual RTOs unverified).
- Sonarr/Radarr monitored-series/movie lists live in SQLite only — a reprovision loses them (accepted; use the in-app backup export at Settings → System → Backup before any planned reprovision).
- Prowlarr indexer credentials (registered-site logins) must be re-entered from Vaultwarden after a VM 125 reprovision.
