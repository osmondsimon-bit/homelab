# Phase 6 — Media

**Closed:** 2026-06-28 via `/phase-gate`
**ADR:** ADR-021 (Accepted, infra-designer-reviewed)

## What shipped

| Service | Guest | Node | Key detail |
|---------|-------|------|------------|
| Jellyfin | CT 120 (Debian 12 unpriv LXC) | apophis | iGPU QuickSync (`/dev/dri` passthrough via single-GID idmap, render GID 993 `hostrender`); media on 500 GB USB-C SSD (`/mnt/usb-media`, ext4) |
| qBittorrent | CT 121 (Debian 12 unpriv LXC) | apophis | All egress via ProtonVPN WireGuard + nftables killswitch (default-drop output; wg0 + handshake only); qBit also binds torrents to wg0 (defence-in-depth); NAT-PMP port forward |

## Key decisions

- **Native WireGuard + nftables killswitch** chosen over Gluetun/Docker to keep service LXCs Docker-free (ADR-014 principle). Killswitch comes up before wg0 at boot — no startup window where traffic could leak.
- **Unprivileged LXC for Jellyfin** (not a VM) — iGPU passthrough proven via single-GID idmap carve-out (GID 993 mapped 1:1). Avoids the VM overhead.
- **Shared media group** (host gid 101000 = in-CT gid 1000, setgid `02775`, `UMask=0002`) so Jellyfin can read what qBittorrent writes without permission conflicts — and hardlinks work (same filesystem, same inode across mounts).
- **USB SSD not backed up** by design — media is re-downloadable; NAS deferred to new house. Risk explicitly accepted.
- **USB mount monitoring** uses node_exporter's built-in systemd collector, narrowly restricted to
  the generated Media USB mount unit. Prometheus combines the apophis target's stable `node` label
  with the unit's active state, so a missing mount is distinct from an unavailable host. Capacity
  is deliberately not probed after the 2026-07-17 host-lock incident.

## Verification

- Jellyfin WebUI: HTTP 200; `vainfo` inside CT confirms H264/HEVC decode+encode via VA-API (iGPU, jellyfin user).
- qBittorrent leak-test ✅ 2026-06-27: egress IP = ProtonVPN; `wg0` brought down → curl + DNS both blocked (killswitch holds; no fallback to home WAN).
- Media storage state: `node_systemd_unit_state` for
  `node="apophis",name="mnt-usb\x2dmedia.mount",state="active"`.

## Carry-forwards

- Reprovision drills for CT 120 + CT 121 pending (playbooks exist + recovery documented; actual RTO unverified).
- USB SSD is a single physical device — failure = all media lost until re-acquired (documented accepted risk).
